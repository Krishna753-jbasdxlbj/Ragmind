"""auth.py - verify Supabase access token, derive user_id.

Supabase projects with the new API-key system sign access tokens with an
asymmetric key (ES256), verified against the project's JWKS. Older projects use
a symmetric HS256 secret. We support both: read the token's alg and verify
accordingly. The raw token is also forwarded to PostgREST so RLS scopes reads.

When the Space is private and reached through the Vercel proxy, the HF gating
token occupies the `Authorization` header, so the Supabase JWT arrives in
`X-Supabase-Auth`. Prefer that; fall back to `Authorization` for direct calls.
"""
import os

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")  # legacy HS256 (optional)
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

# Caches keys in-process and refreshes on unknown kid.
_jwk_client = PyJWKClient(JWKS_URL)


class AuthContext:
    def __init__(self, user_id: str, token: str):
        self.user_id = user_id
        self.token = token


def _verify(token: str) -> dict:
    alg = jwt.get_unverified_header(token).get("alg", "")
    opts = {"verify_aud": True}
    if alg == "HS256":
        if not JWT_SECRET:
            raise HTTPException(status_code=500, detail="HS256 token but no JWT secret configured.")
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"], audience="authenticated", options=opts)
    # Asymmetric (ES256/RS256): verify against the project JWKS.
    key = _jwk_client.get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["ES256", "RS256"], audience="authenticated", options=opts)


def require_auth(
    authorization: str = Header(None),
    x_supabase_auth: str = Header(None),
) -> AuthContext:
    """FastAPI dependency: validate the Supabase Bearer token, return AuthContext."""
    raw = x_supabase_auth or authorization
    if not raw or not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = raw.split(" ", 1)[1].strip()
    try:
        payload = _verify(token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject.")
    return AuthContext(user_id=user_id, token=token)
