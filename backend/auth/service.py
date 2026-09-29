import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.context import OrgContext, pick_default_org_id, resolve_org_context
from backend.auth.sessions import IssuedSession, create_session, rotate_session
from backend.auth.tokens import create_access_token
from backend.db.models import Session, User, UserStatus
from backend.errors import AuthenticationError


@dataclass(frozen=True)
class AuthResult:
    user: User
    session: Session
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    org_context: OrgContext | None


def ensure_user_can_authenticate(user: User) -> None:
    if user.status != UserStatus.active:
        raise AuthenticationError("Account is suspended", code="account_suspended")


async def mint_access_token(
    db: AsyncSession, user: User, session: Session
) -> tuple[str, datetime, OrgContext | None]:
    ctx = await resolve_org_context(db, user, session.active_org_id)
    if ctx is None and session.active_org_id is not None:
        session.active_org_id = None
        await db.flush()
    token, expires_at = create_access_token(
        user_id=user.id,
        session_id=session.id,
        org_id=ctx.org.id if ctx else None,
        role=ctx.role_key if ctx else None,
        permissions=ctx.permissions if ctx else frozenset(),
        is_super_admin=user.is_super_admin,
    )
    return token, expires_at, ctx


async def start_session(
    db: AsyncSession,
    user: User,
    *,
    user_agent: str | None,
    ip_address: str | None,
    org_id: uuid.UUID | None = None,
) -> AuthResult:
    ensure_user_can_authenticate(user)
    active_org_id = org_id if org_id is not None else await pick_default_org_id(db, user)
    issued: IssuedSession = await create_session(
        db, user, active_org_id=active_org_id, user_agent=user_agent, ip_address=ip_address
    )
    token, expires_at, ctx = await mint_access_token(db, user, issued.session)
    return AuthResult(
        user=user,
        session=issued.session,
        access_token=token,
        access_expires_at=expires_at,
        refresh_token=issued.refresh_token,
        org_context=ctx,
    )


async def refresh_session(
    db: AsyncSession,
    raw_refresh_token: str,
    *,
    user_agent: str | None,
    ip_address: str | None,
) -> AuthResult:
    issued = await rotate_session(
        db, raw_refresh_token, user_agent=user_agent, ip_address=ip_address
    )
    user = await db.get(User, issued.session.user_id)
    if user is None:
        raise AuthenticationError("User no longer exists", code="user_missing")
    ensure_user_can_authenticate(user)
    token, expires_at, ctx = await mint_access_token(db, user, issued.session)
    return AuthResult(
        user=user,
        session=issued.session,
        access_token=token,
        access_expires_at=expires_at,
        refresh_token=issued.refresh_token,
        org_context=ctx,
    )
