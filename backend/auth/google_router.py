import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from backend.audit import record_audit
from backend.auth import google
from backend.auth.cookies import set_auth_cookies
from backend.auth.deps import Client
from backend.auth.service import start_session
from backend.config import get_settings
from backend.db.session import DbSession
from backend.errors import AppError

router = APIRouter(prefix="/auth/google", tags=["auth"])
log = logging.getLogger("gatewise.google")

FLOW_COOKIE = "gw_oauth"
FLOW_COOKIE_PATH = "/api/auth/google"


def _app_redirect(path: str, **query: str) -> RedirectResponse:
    base = get_settings().app_url.rstrip("/")
    url = f"{base}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return RedirectResponse(url, status_code=303)


def _login_error(code: str) -> RedirectResponse:
    response = _app_redirect("/login", error=code)
    response.delete_cookie(FLOW_COOKIE, path=FLOW_COOKIE_PATH)
    return response


@router.get("/start")
async def start(request: Request, next: str | None = None) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_enabled:
        return _login_error("google_disabled")

    flow = google.begin_flow(next)
    response = RedirectResponse(google.authorization_url(flow), status_code=303)
    response.set_cookie(
        FLOW_COOKIE,
        google.encode_flow(flow),
        max_age=int(google.OAUTH_STATE_TTL.total_seconds()),
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=FLOW_COOKIE_PATH,
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    db: DbSession,
    client: Client,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        return _login_error("google_denied" if error == "access_denied" else "google_error")

    raw_flow = request.cookies.get(FLOW_COOKIE)
    if not raw_flow or not code or not state:
        return _login_error("oauth_state_missing")

    try:
        flow = google.decode_flow(raw_flow)
        if flow.state != state:
            raise AppError("State mismatch", code="oauth_state_mismatch", status_code=401)

        id_token = await google.exchange_code(code, flow.code_verifier)
        identity = await google.verify_id_token(id_token, nonce=flow.nonce)
        user, created = await google.resolve_google_user(db, identity)
        result = await start_session(
            db, user, user_agent=client.user_agent, ip_address=client.ip_address
        )
        await record_audit(
            db,
            action="auth.google_signup" if created else "auth.google_login",
            actor_user_id=user.id,
            org_id=result.session.active_org_id,
            target_type="session",
            target_id=result.session.id,
            ip_address=client.ip_address,
        )
        await db.commit()
    except AppError as exc:
        await db.rollback()
        log.info("google sign-in failed: %s", exc.code)
        return _login_error(exc.code)

    response = _app_redirect(flow.next_path)
    response.delete_cookie(FLOW_COOKIE, path=FLOW_COOKIE_PATH)
    set_auth_cookies(response, access_token=result.access_token, refresh_token=result.refresh_token)
    return response
