from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.providers import LocalAuthProvider
from app.auth.security import JWTError, decode_access_token

_bearer = HTTPBearer(auto_error=False)
_local_provider = LocalAuthProvider()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> Dict[str, Any]:
    """
    Decodes the bearer JWT and loads the live user record from SQLite (not
    from the token payload alone) so a role change or account removal takes
    effect immediately rather than persisting until token expiry.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token. Log in via POST /v1/auth/login.")
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session token is invalid or expired. Log in again.")

    user = _local_provider.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Account for this session no longer exists.")
    return user


def require_role(*allowed_roles: str):
    def _check(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' cannot perform this action — requires one of {list(allowed_roles)}.",
            )
        return user

    return _check
