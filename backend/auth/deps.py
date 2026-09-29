from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.context import OrgContext, resolve_org_context
from backend.auth.cookies import client_ip, client_user_agent, read_access_token
from backend.auth.sessions import get_live_session
from backend.auth.tokens import AccessClaims, decode_access_token
from backend.db.models import Session, User, UserStatus
from backend.db.session import DbSession
from backend.errors import AuthenticationError, PermissionDeniedError


@dataclass(frozen=True)
class ClientInfo:
    ip_address: str | None
    user_agent: str | None


def get_client_info(request: Request) -> ClientInfo:
    return ClientInfo(ip_address=client_ip(request), user_agent=client_user_agent(request))


Client = Annotated[ClientInfo, Depends(get_client_info)]


@dataclass
class Principal:
    user: User
    session: Session
    claims: AccessClaims
    org: OrgContext | None

    @property
    def org_id(self):
        return self.org.org.id if self.org else None

    def has(self, permission: str) -> bool:
        if self.user.is_super_admin:
            return True
        return self.org is not None and permission in self.org.permissions

    def require(self, *permissions: str) -> None:
        if self.org is None and not self.user.is_super_admin:
            raise PermissionDeniedError("Select an organization first", code="org_required")
        missing = [p for p in permissions if not self.has(p)]
        if missing:
            raise PermissionDeniedError(
                f"Missing permission: {', '.join(missing)}", code="permission_denied"
            )


def get_claims(request: Request) -> AccessClaims:
    token = read_access_token(request)
    if not token:
        raise AuthenticationError("Sign in required", code="unauthenticated")
    return decode_access_token(token)


bearer_scheme = HTTPBearer(
    auto_error=False, description="Access token (or use the gw_access cookie)"
)


async def get_principal(
    request: Request,
    db: DbSession,
    _: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> Principal:
    claims = get_claims(request)

    session = await get_live_session(db, claims.session_id)
    if session is None:
        raise AuthenticationError("Session is no longer active", code="session_revoked")

    user = await db.get(User, claims.user_id)
    if user is None:
        raise AuthenticationError("User no longer exists", code="user_missing")
    if user.status != UserStatus.active:
        raise AuthenticationError("Account is suspended", code="account_suspended")

    org = await resolve_org_context(db, user, session.active_org_id)
    return Principal(user=user, session=session, claims=claims, org=org)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_org_principal(principal: CurrentPrincipal) -> Principal:
    if principal.org is None:
        raise PermissionDeniedError("Select an organization first", code="org_required")
    return principal


OrgPrincipal = Annotated[Principal, Depends(get_org_principal)]


def require_permission(
    *permissions: str,
) -> Callable[..., Coroutine[Any, Any, Principal]]:
    async def dependency(principal: CurrentPrincipal) -> Principal:
        principal.require(*permissions)
        return principal

    return dependency
