"""Authentication endpoints: register, log in, and get the current user."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.dependencies import get_current_user

# prefix: every route below starts with /auth. tags: groups them in /docs.
router = APIRouter(prefix="/auth", tags=["auth"])


# response_model=UserOut filters the returned User object, so fields like
# password_hash are never sent to the client.
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new customer account and return it (without the password)."""
    # Lower-case emails so "Bob@x.com" and "bob@x.com" count as the same account.
    email = payload.email.lower()
    # 409 Conflict: the request is valid, but clashes with an existing account.
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        # Always "customer" here, so nobody can sign themselves up as an admin.
        role="customer",
    )
    db.add(user)
    db.commit()
    # refresh() reloads DB-generated values (id, created_at) onto the object.
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Check email and password and return a JWT access token.

    Uses the standard OAuth2 form (fields named username/password, sent as form
    data, not JSON) so Swagger UI's "Authorize" button works out of the box.
    """
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    # Same message whether the email or the password is wrong, so attackers
    # can't use this endpoint to find out which emails are registered.
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))

@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Return the user who owns the token, e.g. so the frontend can show their name."""
    return current_user