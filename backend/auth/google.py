import asyncio
import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.accounts import find_user_by_email, get_role_by_key, unique_org_slug
from backend.config import get_settings
from backend.db.models import (
    Invitation,
    MembershipStatus,
    OAuthAccount,
    OAuthProvider,
    Org,
    User,
    UserRole,
)
from backend.errors import AuthenticationError

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
OAUTH_STATE_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


@dataclass(frozen=True)
class OAuthFlow:
    state: str
    nonce: str
    code_verifier: str
    next_path: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def safe_next_path(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def begin_flow(next_path: str | None) -> OAuthFlow:
    return OAuthFlow(
        state=secrets.token_urlsafe(24),
        nonce=secrets.token_urlsafe(24),
        code_verifier=secrets.token_urlsafe(64),
        next_path=safe_next_path(next_path),
    )


def encode_flow(flow: OAuthFlow) -> str:
    now = datetime.now(UTC)
    payload = {
        "st": flow.state,
        "n": flow.nonce,
        "cv": flow.code_verifier,
        "nx": flow.next_path,
        "iat": int(now.timestamp()),
        "exp": int((now + OAUTH_STATE_TTL).timestamp()),
        "purpose": "google_oauth",
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def decode_flow(token: str) -> OAuthFlow:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Sign-in attempt expired", code="oauth_state_invalid") from exc
    if payload.get("purpose") != "google_oauth":
        raise AuthenticationError("Sign-in attempt invalid", code="oauth_state_invalid")
    return OAuthFlow(
        state=payload["st"],
        nonce=payload["n"],
        code_verifier=payload["cv"],
        next_path=safe_next_path(payload.get("nx")),
    )


def authorization_url(flow: OAuthFlow) -> str:
    settings = get_settings()
    challenge = _b64url(hashlib.sha256(flow.code_verifier.encode()).digest())
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "state": flow.state,
        "nonce": flow.nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str) -> str:
    settings = get_settings()
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_callback_url,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(GOOGLE_TOKEN_URL, data=data)
    except httpx.HTTPError as exc:
        raise AuthenticationError("Could not reach Google", code="google_unreachable") from exc
    if res.status_code != 200:
        raise AuthenticationError("Google rejected the sign-in code", code="google_code_rejected")
    id_token = res.json().get("id_token")
    if not id_token:
        raise AuthenticationError("Google did not return an identity", code="google_no_id_token")
    return id_token


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)


async def verify_id_token(id_token: str, *, nonce: str) -> GoogleIdentity:
    settings = get_settings()
    try:
        signing_key = await asyncio.to_thread(_jwks_client().get_signing_key_from_jwt, id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError(
            "Google identity could not be verified", code="google_token_invalid"
        ) from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise AuthenticationError("Unexpected token issuer", code="google_token_invalid")
    if claims.get("nonce") != nonce:
        raise AuthenticationError("Sign-in attempt mismatch", code="google_nonce_mismatch")
    email = claims.get("email")
    if not email:
        raise AuthenticationError("Google account has no email", code="google_no_email")
    return GoogleIdentity(
        sub=claims["sub"],
        email=email.lower(),
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


async def _activate_pending_invitations(db: AsyncSession, user: User) -> None:
    now = datetime.now(UTC)
    memberships = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id, UserRole.status == MembershipStatus.invited
            )
        )
    ).scalars()
    org_ids = []
    for m in memberships:
        m.status = MembershipStatus.active
        org_ids.append(m.org_id)
    if org_ids:
        await db.execute(
            update(Invitation)
            .where(
                Invitation.email == user.email.lower(),
                Invitation.org_id.in_(org_ids),
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
            )
            .values(accepted_at=now)
        )
    await db.flush()


async def _create_user_with_workspace(db: AsyncSession, identity: GoogleIdentity) -> User:
    name = identity.name or identity.email.split("@")[0]
    user = User(
        email=identity.email,
        name=name,
        password_hash=None,
        avatar_url=identity.picture,
        email_verified_at=datetime.now(UTC),
    )
    org_label = f"{name.split()[0]}'s Workspace"
    org = Org(name=org_label, slug=await unique_org_slug(db, org_label))
    db.add_all([user, org])
    await db.flush()
    admin_role = await get_role_by_key(db, "admin")
    db.add(
        UserRole(
            user_id=user.id, org_id=org.id, role_id=admin_role.id, status=MembershipStatus.active
        )
    )
    await db.flush()
    return user


async def resolve_google_user(db: AsyncSession, identity: GoogleIdentity) -> tuple[User, bool]:
    linked = (
        await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == OAuthProvider.google,
                OAuthAccount.provider_account_id == identity.sub,
            )
        )
    ).scalar_one_or_none()

    if linked is not None:
        user = await db.get(User, linked.user_id)
        if user is None:
            await db.delete(linked)
            await db.flush()
        else:
            if identity.picture and not user.avatar_url:
                user.avatar_url = identity.picture
            await _activate_pending_invitations(db, user)
            return user, False

    if not identity.email_verified:
        raise AuthenticationError(
            "Google account email is not verified", code="google_email_unverified"
        )

    user = await find_user_by_email(db, identity.email)
    created = False
    if user is None:
        user = await _create_user_with_workspace(db, identity)
        created = True
    else:
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        if identity.picture and not user.avatar_url:
            user.avatar_url = identity.picture
        if identity.name and user.password_hash is None:
            user.name = identity.name

    db.add(
        OAuthAccount(
            user_id=user.id, provider=OAuthProvider.google, provider_account_id=identity.sub
        )
    )
    await db.flush()
    await _activate_pending_invitations(db, user)
    return user, created
