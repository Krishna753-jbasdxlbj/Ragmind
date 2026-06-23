"""auth.py - verify Supabase JWT, derive user_id.

Supabase access tokens are HS256-signed with SUPABASE_JWT_SECRET, audience
'authenticated'. The raw token is also forwarded to PostgREST so RLS scopes the
user's reads (see vector_store.user_client).
"""
import os

import jwt
from fastapi import Header, HTTPException

JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]


class AuthContext:
    def __init__(self, user_id: str, token: str):
        self.user_id = user_id
        self.token = token


def require_auth(authorization: str = Header(None)) -> AuthContext:
    """FastAPI dependency: validate the Bearer token, return AuthContext."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject.")
    return AuthContext(user_id=user_id, token=token)
