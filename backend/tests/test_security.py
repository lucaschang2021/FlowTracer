from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    create_refresh_value,
    decode_access_token,
    hash_password,
    hash_refresh_value,
    parse_refresh_token,
    password_needs_rehash,
    verify_password,
)


def test_argon2id_password_contract() -> None:
    value = "correct horse battery staple"
    password_hash = hash_password(value)
    assert password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert verify_password(password_hash, value)
    assert not verify_password(password_hash, "wrong password")
    assert not password_needs_rehash(password_hash)


def test_refresh_value_and_hash_contract() -> None:
    token_id = uuid4()
    value = create_refresh_value(token_id)
    assert parse_refresh_token(value) == token_id
    assert len(hash_refresh_value(value)) == 64
    with pytest.raises(ValueError):
        parse_refresh_token("malformed")


@pytest.mark.parametrize(
    "mutation",
    ["expired", "issuer", "audience", "type", "tampered"],
)
def test_access_token_rejects_invalid_claims(mutation: str) -> None:
    settings = Settings()
    user_id = uuid4()
    now = datetime.now(UTC)
    if mutation == "expired":
        token = create_access_token(user_id, settings, now - timedelta(hours=1))
    else:
        payload = {
            "sub": str(user_id),
            "jti": str(uuid4()),
            "type": "refresh" if mutation == "type" else "access",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=15),
            "iss": "wrong" if mutation == "issuer" else settings.jwt_issuer,
            "aud": "wrong" if mutation == "audience" else settings.jwt_audience,
        }
        token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
        if mutation == "tampered":
            token += "x"
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token, settings)


def test_access_token_accepts_frozen_claims() -> None:
    settings = Settings()
    user_id = uuid4()
    assert decode_access_token(create_access_token(user_id, settings), settings) == user_id
