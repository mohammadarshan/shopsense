"""Reusable FastAPI dependencies for authentication and authorization.

Routes add these with Depends(...), so the login and admin checks are written
once here instead of being copied into every endpoint.
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# Reads the "Authorization: Bearer <token>" header (and returns 401 if it's
# missing). tokenUrl also tells Swagger UI where its "Authorize" button logs in.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Return the logged-in user from the request's JWT, or raise 401.

    Depends chains: FastAPI first runs oauth2_scheme and get_db, then passes
    their results into this function.
    """
    # 401 means "we don't know who you are": the client should log in again.
    # The WWW-Authenticate header is required by the HTTP spec for 401s.
    credentials_error = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # decode() also verifies the signature and expiry. Passing an explicit
        # algorithms list stops attackers from picking a weaker algorithm.
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
    # One generic error for every failure, so attackers learn nothing about
    # why their token was rejected.
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise credentials_error

    # A valid token can still point at a user who has since been deleted.
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Allow the request only if the logged-in user is an admin.

    Builds on get_current_user, so a missing or bad token still gets a 401.
    """
    if user.role != "admin":
        # 403, not 401: we know who you are, you just aren't allowed to do this.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user