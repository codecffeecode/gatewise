import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.tokens import generate_opaque_token, hash_token, refresh_token_expiry
from backend.db.models import Session, User
from backend.errors import AuthenticationError

REUSE_REASON = "refresh_token_reuse"


@dataclass(frozen=True)
class IssuedSession:
    session: Session
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


def is_session_live(session: Session, now: datetime | None = None) -> bool:
    now = now or _now()
    return session.revoked_at is None and session.expires_at > now


async def create_session(
    db: AsyncSession,
    user: User,
    *,
    active_org_id: uuid.UUID | None,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedSession:
    raw = generate_opaque_token()
    session = Session(
        user_id=user.id,
        refresh_token_hash=hash_token(raw),
        active_org_id=active_org_id,
        user_agent=(user_agent or "")[:512] or None,
        ip_address=ip_address,
        expires_at=refresh_token_expiry(),
    )
    db.add(session)
    user.last_login_at = _now()
    await db.flush()
    return IssuedSession(session=session, refresh_token=raw)


async def rotate_session(
    db: AsyncSession,
    raw_refresh_token: str,
    *,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedSession:
    presented = hash_token(raw_refresh_token)
    now = _now()

    session = (
        await db.execute(select(Session).where(Session.refresh_token_hash == presented))
    ).scalar_one_or_none()

    if session is None:
        reused = (
            await db.execute(
                select(Session).where(Session.previous_refresh_token_hash == presented)
            )
        ).scalar_one_or_none()
        if reused is not None and reused.revoked_at is None:
            reused.revoked_at = now
            reused.revoked_reason = REUSE_REASON
            await db.flush()
        raise AuthenticationError("Refresh token is not valid", code="refresh_invalid")

    if session.revoked_at is not None:
        raise AuthenticationError("Session has been revoked", code="session_revoked")
    if session.expires_at <= now:
        raise AuthenticationError("Session has expired", code="session_expired")

    new_raw = generate_opaque_token()
    session.previous_refresh_token_hash = session.refresh_token_hash
    session.refresh_token_hash = hash_token(new_raw)
    session.last_used_at = now
    if user_agent:
        session.user_agent = user_agent[:512]
    if ip_address:
        session.ip_address = ip_address
    await db.flush()
    return IssuedSession(session=session, refresh_token=new_raw)


async def get_live_session(db: AsyncSession, session_id: uuid.UUID) -> Session | None:
    session = await db.get(Session, session_id)
    if session is None or not is_session_live(session):
        return None
    return session


async def revoke_session(db: AsyncSession, session: Session, *, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = _now()
        session.revoked_reason = reason
        await db.flush()


async def revoke_session_by_refresh_token(
    db: AsyncSession, raw_refresh_token: str, *, reason: str
) -> bool:
    presented = hash_token(raw_refresh_token)
    session = (
        await db.execute(select(Session).where(Session.refresh_token_hash == presented))
    ).scalar_one_or_none()
    if session is None:
        return False
    await revoke_session(db, session, reason=reason)
    return True


async def revoke_all_user_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    reason: str,
    except_session_id: uuid.UUID | None = None,
) -> int:
    stmt = (
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=_now(), revoked_reason=reason)
    )
    if except_session_id is not None:
        stmt = stmt.where(Session.id != except_session_id)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount or 0


async def list_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, *, include_revoked: bool = False
) -> list[Session]:
    stmt = select(Session).where(Session.user_id == user_id)
    if not include_revoked:
        stmt = stmt.where(Session.revoked_at.is_(None), Session.expires_at > _now())
    stmt = stmt.order_by(Session.last_used_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def set_session_active_org(
    db: AsyncSession, session: Session, org_id: uuid.UUID | None
) -> None:
    session.active_org_id = org_id
    await db.flush()
