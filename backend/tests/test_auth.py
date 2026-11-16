from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.models import User

NEW_USER = {"email": "new@gmail.com", "password": "password123", "full_name": "New User"}


def test_register_returns_user_without_password(client):
    r = client.post("/auth/register", json=NEW_USER)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@gmail.com"
    assert body["role"] == "customer"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_is_conflict(client):
    client.post("/auth/register", json=NEW_USER)
    r = client.post("/auth/register", json=NEW_USER)
    assert r.status_code == 409


def test_register_email_is_case_insensitive(client):
    client.post("/auth/register", json={**NEW_USER, "email": "New@Gmail.com"})
    r = client.post("/auth/register", json=NEW_USER)
    assert r.status_code == 409


def test_register_cannot_choose_role(client):
    r = client.post("/auth/register", json={**NEW_USER, "role": "admin"})
    assert r.status_code == 201
    assert r.json()["role"] == "customer"


def test_register_rejects_short_password(client):
    r = client.post("/auth/register", json={**NEW_USER, "password": "short"})
    assert r.status_code == 422


def test_login_returns_token(client):
    client.post("/auth/register", json=NEW_USER)
    r = client.post(
        "/auth/login", data={"username": "new@gmail.com", "password": "password123"}
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_errors_do_not_reveal_which_part_was_wrong(client):
    client.post("/auth/register", json=NEW_USER)
    wrong_password = client.post(
        "/auth/login", data={"username": "new@gmail.com", "password": "wrongwrong"}
    )
    unknown_email = client.post(
        "/auth/login", data={"username": "nobody@gmail.com", "password": "password123"}
    )
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_seeded_placeholder_account_cannot_log_in(client, session_factory):
    with session_factory() as db:
        db.add(
            User(
                email="user1@example.com",
                password_hash="!seeded-account-no-login",
                full_name="Seeded",
            )
        )
        db.commit()
    r = client.post(
        "/auth/login", data={"username": "user1@example.com", "password": "anything123"}
    )
    assert r.status_code == 401  # a clean 401, not a 500 crash


def test_me_requires_a_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_the_logged_in_user(client, make_headers):
    headers = make_headers("me@gmail.com")
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "me@gmail.com"


def test_token_signed_with_wrong_secret_is_rejected(client):
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "not-the-real-secret-not-the-real-secret",
        algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_expired_token_is_rejected(client):
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401