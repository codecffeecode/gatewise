import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from backend.auth import tokens
from backend.config import get_settings
from backend.errors import AuthenticationError


def _mint(**overrides):
    params = dict(
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role="manager",
        permissions={"users:read", "users:invite"},
        is_super_admin=False,
    )
    params.update(overrides)
    return params, tokens.create_access_token(**params)


def test_access_token_round_trip():
    params, (token, expires_at) = _mint()
    claims = tokens.decode_access_token(token)

    assert claims.user_id == params["user_id"]
    assert claims.session_id == params["session_id"]
    assert claims.org_id == params["org_id"]
    assert claims.role == "manager"
    assert claims.permissions == frozenset({"users:read", "users:invite"})
    assert claims.is_super_admin is False
    assert claims.expires_at == expires_at.replace(microsecond=0)
    assert claims.has("users:read")
    assert not claims.has("users:delete")


def test_super_admin_has_every_permission():
    _, (token, _) = _mint(is_super_admin=True, permissions=set(), org_id=None, role=None)
    claims = tokens.decode_access_token(token)
    assert claims.org_id is None
    assert claims.has("anything:at-all")


def test_expired_token_is_rejected():
    past = datetime.now(UTC) - timedelta(seconds=get_settings().access_token_ttl_seconds + 60)
    _, (token, _) = _mint(now=past)
    with pytest.raises(AuthenticationError) as exc:
        tokens.decode_access_token(token)
    assert exc.value.code == "token_expired"


def test_tampered_signature_is_rejected():
    _, (token, _) = _mint()
    forged = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}),
        "another-secret-that-is-definitely-not-the-real-one",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError) as exc:
        tokens.decode_access_token(forged)
    assert exc.value.code == "token_invalid"


def test_wrong_audience_is_rejected():
    payload = jwt.decode(_mint()[1][0], options={"verify_signature": False})
    payload["aud"] = "someone-else"
    token = jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")
    with pytest.raises(AuthenticationError):
        tokens.decode_access_token(token)


def test_opaque_tokens_are_unique_and_hash_deterministically():
    a, b = tokens.generate_opaque_token(), tokens.generate_opaque_token()
    assert a != b
    assert len(a) >= 40
    assert tokens.hash_token(a) == tokens.hash_token(a)
    assert tokens.hash_token(a) != tokens.hash_token(b)
    assert len(tokens.hash_token(a)) == 64
