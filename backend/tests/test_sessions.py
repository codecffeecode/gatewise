import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import sessions
from backend.auth.tokens import hash_token
from backend.db.models import User
from backend.errors import AuthenticationError

UA = "pytest/1.0"
IP = "203.0.113.10"


async def test_create_and_rotate_session(db: AsyncSession, temp_user: User):
    issued = await sessions.create_session(
        db, temp_user, active_org_id=None, user_agent=UA, ip_address=IP
    )
    assert issued.session.refresh_token_hash == hash_token(issued.refresh_token)
    assert issued.session.previous_refresh_token_hash is None
    assert sessions.is_session_live(issued.session)

    rotated = await sessions.rotate_session(db, issued.refresh_token, user_agent=UA, ip_address=IP)
    assert rotated.session.id == issued.session.id
    assert rotated.refresh_token != issued.refresh_token
    assert rotated.session.refresh_token_hash == hash_token(rotated.refresh_token)
    assert rotated.session.previous_refresh_token_hash == hash_token(issued.refresh_token)


async def test_reusing_rotated_token_revokes_the_session(db: AsyncSession, temp_user: User):
    issued = await sessions.create_session(
        db, temp_user, active_org_id=None, user_agent=UA, ip_address=IP
    )
    rotated = await sessions.rotate_session(db, issued.refresh_token, user_agent=UA, ip_address=IP)

    with pytest.raises(AuthenticationError) as exc:
        await sessions.rotate_session(db, issued.refresh_token, user_agent=UA, ip_address=IP)
    assert exc.value.code == "refresh_invalid"

    await db.refresh(rotated.session)
    assert rotated.session.revoked_at is not None
    assert rotated.session.revoked_reason == sessions.REUSE_REASON

    with pytest.raises(AuthenticationError) as exc:
        await sessions.rotate_session(db, rotated.refresh_token, user_agent=UA, ip_address=IP)
    assert exc.value.code == "session_revoked"


async def test_unknown_refresh_token_is_rejected(db: AsyncSession):
    with pytest.raises(AuthenticationError) as exc:
        await sessions.rotate_session(db, "definitely-not-a-token", user_agent=UA, ip_address=IP)
    assert exc.value.code == "refresh_invalid"


async def test_revoke_all_except_current(db: AsyncSession, temp_user: User):
    first = await sessions.create_session(
        db, temp_user, active_org_id=None, user_agent="laptop", ip_address=IP
    )
    second = await sessions.create_session(
        db, temp_user, active_org_id=None, user_agent="phone", ip_address=IP
    )
    third = await sessions.create_session(
        db, temp_user, active_org_id=None, user_agent="tablet", ip_address=IP
    )

    live = await sessions.list_user_sessions(db, temp_user.id)
    assert {s.id for s in live} == {first.session.id, second.session.id, third.session.id}

    count = await sessions.revoke_all_user_sessions(
        db, temp_user.id, reason="user_logout_all", except_session_id=second.session.id
    )
    assert count == 2

    live_after = await sessions.list_user_sessions(db, temp_user.id)
    assert [s.id for s in live_after] == [second.session.id]

    everything = await sessions.list_user_sessions(db, temp_user.id, include_revoked=True)
    assert len(everything) == 3


async def test_revoke_by_refresh_token(db: AsyncSession, temp_user: User):
    issued = await sessions.create_session(
        db, temp_user, active_org_id=None, user_agent=UA, ip_address=IP
    )
    assert await sessions.revoke_session_by_refresh_token(db, issued.refresh_token, reason="logout")
    assert not await sessions.revoke_session_by_refresh_token(db, "nope", reason="logout")
    with pytest.raises(AuthenticationError) as exc:
        await sessions.rotate_session(db, issued.refresh_token, user_agent=UA, ip_address=IP)
    assert exc.value.code == "session_revoked"
