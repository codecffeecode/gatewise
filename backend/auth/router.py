import uuid

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from backend.audit import record_audit
from backend.auth.accounts import authenticate_with_password, register_with_new_org
from backend.auth.context import resolve_org_context
from backend.auth.cookies import (
    clear_auth_cookies,
    read_access_token,
    read_refresh_token,
    set_access_cookie,
    set_auth_cookies,
)
from backend.auth.deps import Client, CurrentPrincipal
from backend.auth.presenters import present_auth, present_me
from backend.auth.service import mint_access_token, refresh_session, start_session
from backend.auth.sessions import (
    get_live_session,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
    revoke_session_by_refresh_token,
    set_session_active_org,
)
from backend.auth.tokens import decode_access_token
from backend.config import get_settings
from backend.db.models import Session
from backend.db.session import DbSession
from backend.errors import AppError, AuthenticationError, NotFoundError, PermissionDeniedError
from backend.org.presenters import present_session
from backend.schemas.auth import (
    AuthConfig,
    AuthResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    SwitchOrgRequest,
)
from backend.schemas.org import SessionOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfig)
async def auth_config() -> AuthConfig:
    settings = get_settings()
    return AuthConfig(
        google_enabled=settings.google_enabled,
        email_enabled=settings.email_enabled,
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, response: Response, db: DbSession, client: Client
) -> AuthResponse:
    registration = await register_with_new_org(
        db, email=body.email, password=body.password, name=body.name, org_name=body.org_name
    )
    result = await start_session(
        db,
        registration.user,
        user_agent=client.user_agent,
        ip_address=client.ip_address,
        org_id=registration.org.id,
    )
    await record_audit(
        db,
        action="auth.register",
        actor_user_id=registration.user.id,
        org_id=registration.org.id,
        target_type="user",
        target_id=registration.user.id,
        ip_address=client.ip_address,
    )
    await db.commit()

    set_auth_cookies(response, access_token=result.access_token, refresh_token=result.refresh_token)
    return await present_auth(
        db,
        user=result.user,
        session=result.session,
        org_context=result.org_context,
        access_token=result.access_token,
        access_expires_at=result.access_expires_at,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest, response: Response, db: DbSession, client: Client
) -> AuthResponse:
    user = await authenticate_with_password(db, email=body.email, password=body.password)
    result = await start_session(
        db, user, user_agent=client.user_agent, ip_address=client.ip_address
    )
    await record_audit(
        db,
        action="auth.login",
        actor_user_id=user.id,
        org_id=result.session.active_org_id,
        target_type="session",
        target_id=result.session.id,
        ip_address=client.ip_address,
    )
    await db.commit()

    set_auth_cookies(response, access_token=result.access_token, refresh_token=result.refresh_token)
    return await present_auth(
        db,
        user=result.user,
        session=result.session,
        org_context=result.org_context,
        access_token=result.access_token,
        access_expires_at=result.access_expires_at,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, response: Response, db: DbSession, client: Client):
    raw = read_refresh_token(request)
    if not raw:
        raise AuthenticationError("No refresh token", code="refresh_missing")

    try:
        result = await refresh_session(
            db, raw, user_agent=client.user_agent, ip_address=client.ip_address
        )
    except AppError as exc:
        await db.commit()
        failed = JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer"},
        )
        clear_auth_cookies(failed)
        return failed

    await db.commit()
    set_auth_cookies(response, access_token=result.access_token, refresh_token=result.refresh_token)
    return await present_auth(
        db,
        user=result.user,
        session=result.session,
        org_context=result.org_context,
        access_token=result.access_token,
        access_expires_at=result.access_expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, db: DbSession, client: Client) -> Response:
    revoked_session_id = None
    raw_refresh = read_refresh_token(request)
    if raw_refresh:
        await revoke_session_by_refresh_token(db, raw_refresh, reason="logout")

    access = read_access_token(request)
    if access:
        try:
            claims = decode_access_token(access)
        except AuthenticationError:
            claims = None
        if claims is not None:
            session = await db.get(Session, claims.session_id)
            if session is not None:
                await revoke_session(db, session, reason="logout")
                revoked_session_id = session.id
                await record_audit(
                    db,
                    action="auth.logout",
                    actor_user_id=claims.user_id,
                    org_id=session.active_org_id,
                    target_type="session",
                    target_id=revoked_session_id,
                    ip_address=client.ip_address,
                )
    await db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(principal: CurrentPrincipal, db: DbSession, client: Client) -> Response:
    count = await revoke_all_user_sessions(db, principal.user.id, reason="logout_all")
    await record_audit(
        db,
        action="auth.logout_all",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        metadata={"revoked_sessions": count},
        ip_address=client.ip_address,
    )
    await db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response)
    return response


@router.get("/sessions", response_model=list[SessionOut])
async def my_sessions(principal: CurrentPrincipal, db: DbSession) -> list[SessionOut]:
    sessions = await list_user_sessions(db, principal.user.id)
    return [present_session(s, current_session_id=principal.session.id) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_my_session(
    session_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, client: Client
) -> Response:
    session = await db.get(Session, session_id)
    if session is None or session.user_id != principal.user.id:
        raise NotFoundError("Session not found", code="session_not_found")
    await revoke_session(db, session, reason="revoked_by_user")
    await record_audit(
        db,
        action="sessions.revoke_own",
        actor_user_id=principal.user.id,
        org_id=principal.org_id,
        target_type="session",
        target_id=session_id,
        ip_address=client.ip_address,
    )
    await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    if session_id == principal.session.id:
        clear_auth_cookies(response)
    return response


@router.get("/me", response_model=MeResponse)
async def me(principal: CurrentPrincipal, db: DbSession) -> MeResponse:
    return await present_me(
        db,
        user=principal.user,
        session=principal.session,
        org_context=principal.org,
        access_expires_at=principal.claims.expires_at,
    )


@router.post("/switch-org", response_model=AuthResponse)
async def switch_org(
    body: SwitchOrgRequest,
    principal: CurrentPrincipal,
    response: Response,
    db: DbSession,
    client: Client,
) -> AuthResponse:
    ctx = await resolve_org_context(db, principal.user, body.org_id)
    if ctx is None:
        raise PermissionDeniedError(
            "You do not have access to this organization", code="org_access_denied"
        )

    session = await get_live_session(db, principal.session.id)
    if session is None:
        raise AuthenticationError("Session is no longer active", code="session_revoked")

    await set_session_active_org(db, session, ctx.org.id)
    token, expires_at, ctx = await mint_access_token(db, principal.user, session)
    await record_audit(
        db,
        action="auth.switch_org",
        actor_user_id=principal.user.id,
        org_id=ctx.org.id if ctx else None,
        target_type="org",
        target_id=body.org_id,
        ip_address=client.ip_address,
    )
    await db.commit()

    set_access_cookie(response, token)
    return await present_auth(
        db,
        user=principal.user,
        session=session,
        org_context=ctx,
        access_token=token,
        access_expires_at=expires_at,
    )
