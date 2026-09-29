from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.context import OrgContext, list_memberships
from backend.auth.permissions import PERMISSIONS
from backend.db.models import Session, User
from backend.schemas.auth import (
    ActiveOrgOut,
    AuthResponse,
    MembershipOut,
    MeResponse,
    SessionSummary,
    UserOut,
)


def present_active_org(user: User, ctx: OrgContext | None) -> ActiveOrgOut | None:
    if ctx is None:
        return None
    perms = set(ctx.permissions)
    if user.is_super_admin:
        perms |= set(PERMISSIONS)
    return ActiveOrgOut(
        id=ctx.org.id,
        name=ctx.org.name,
        slug=ctx.org.slug,
        role=ctx.role.key if ctx.role else None,
        role_name=ctx.role.name if ctx.role else None,
        permissions=sorted(perms),
    )


async def present_me(
    db: AsyncSession,
    *,
    user: User,
    session: Session,
    org_context: OrgContext | None,
    access_expires_at: datetime,
) -> MeResponse:
    memberships = await list_memberships(db, user.id)
    return MeResponse(
        user=UserOut.model_validate(user),
        org=present_active_org(user, org_context),
        orgs=[
            MembershipOut(
                org_id=m.org.id,
                org_name=m.org.name,
                org_slug=m.org.slug,
                org_enabled=m.org.enabled,
                role=m.role.key,
                role_name=m.role.name,
                status=m.status,
            )
            for m in memberships
        ],
        session=SessionSummary(
            id=session.id, expires_at=session.expires_at, access_expires_at=access_expires_at
        ),
    )


async def present_auth(
    db: AsyncSession,
    *,
    user: User,
    session: Session,
    org_context: OrgContext | None,
    access_token: str,
    access_expires_at: datetime,
) -> AuthResponse:
    me = await present_me(
        db,
        user=user,
        session=session,
        org_context=org_context,
        access_expires_at=access_expires_at,
    )
    return AuthResponse(**me.model_dump(), access_token=access_token)
