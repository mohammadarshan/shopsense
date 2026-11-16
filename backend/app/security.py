"""Password hashing and JWT access-token creation."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Turn a plain password into a bcrypt hash that is safe to store.

    bcrypt is deliberately slow and adds a random salt, so two users with the
    same password get different hashes and leaked hashes are hard to crack.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a login attempt against a stored hash.

    We can't "decrypt" a hash, so bcrypt re-hashes the attempt using the salt
    stored inside the hash and compares the results.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Not a valid bcrypt hash, e.g. the "!seeded-account-no-login" placeholder
        return False


def create_access_token(user_id: int) -> str:
    """Create a signed JWT that proves who the user is on later requests.

    The token is signed (not encrypted): anyone can read it, but it can't be
    changed without the secret key, so the server can trust its contents.
    """
    # Always use UTC so expiry doesn't depend on the server's time zone.
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    # "sub" (subject) and "exp" (expiry) are standard JWT claim names; the
    # spec expects "sub" to be a string, and PyJWT checks "exp" automatically.
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)