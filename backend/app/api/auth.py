from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.providers import LocalAuthProvider, get_auth_provider
from app.auth.security import create_access_token
from app.deps import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login_endpoint(payload: LoginRequest):
    provider = get_auth_provider()
    user = provider.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password.")

    token = create_access_token(user["user_id"], user["username"], user["role"])
    auth_method = "argon2_local" if isinstance(provider, LocalAuthProvider) else "ldap"
    return {"status": "authenticated", "auth_method": auth_method, "user": user, "access_token": token, "token_type": "bearer"}


@router.get("/auth/me")
def me_endpoint(user: dict = Depends(get_current_user)):
    return {"user": user}
