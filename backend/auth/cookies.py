from fastapi import Request, Response

from backend.config import get_settings

ACCESS_COOKIE = "gw_access"
REFRESH_COOKIE = "gw_refresh"
SESSION_HINT_COOKIE = "gw_session"
REFRESH_COOKIE_PATH = "/api/auth"


def _secure() -> bool:
    return get_settings().is_production


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    refresh_max_age = settings.refresh_token_ttl_days * 24 * 60 * 60
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        SESSION_HINT_COOKIE,
        "1",
        max_age=refresh_max_age,
        httponly=False,
        secure=_secure(),
        samesite="lax",
        path="/",
    )


def set_access_cookie(response: Response, access_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", httponly=True, secure=_secure(), samesite="lax")
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, secure=_secure(), samesite="lax"
    )
    response.delete_cookie(SESSION_HINT_COOKIE, path="/", secure=_secure(), samesite="lax")


def read_access_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token:
            return token
    return request.cookies.get(ACCESS_COOKIE)


def read_refresh_token(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE)


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


def client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")
