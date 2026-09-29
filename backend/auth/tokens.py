import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import jwt

from backend.config import get_settings
from backend.errors import AuthenticationError

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "gatewise"
JWT_AUDIENCE = "gatewise-web"


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    org_id: uuid.UUID | None
    role: str | None
    permissions: frozenset[str]
    is_super_admin: bool
    issued_at: datetime
    expires_at: datetime
    raw: dict = field(repr=False, compare=False, default_factory=dict)

    def has(self, permission: str) -> bool:
        return self.is_super_admin or permission in self.permissions


def create_access_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    org_id: uuid.UUID | None,
    role: str | None,
    permissions: set[str] | frozenset[str],
    is_super_admin: bool,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    settings = get_settings()
    now = now or datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user_id),
        "sid": str(session_id),
        "org": str(org_id) if org_id else None,
        "role": role,
        "perms": sorted(permissions),
        "sa": is_super_admin,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> AccessClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "sid"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Access token expired", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid access token", code="token_invalid") from exc

    try:
        return AccessClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            org_id=uuid.UUID(payload["org"]) if payload.get("org") else None,
            role=payload.get("role"),
            permissions=frozenset(payload.get("perms") or ()),
            is_super_admin=bool(payload.get("sa", False)),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            raw=payload,
        )
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Malformed access token", code="token_invalid") from exc


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_token_expiry(now: datetime | None = None) -> datetime:
    settings = get_settings()
    return (now or datetime.now(UTC)) + timedelta(days=settings.refresh_token_ttl_days)
