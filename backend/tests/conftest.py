"""Shared pytest fixtures.

Tests run against a separate database (<POSTGRES_DB>_test) that is built from
db/schema.sql and wiped before every test. The real database is never touched.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.config import ROOT, settings
from app.database import get_db
from app.main import app
from app.models import Product, User

TEST_DB = f"{settings.postgres_db}_test"

test_engine = create_engine(
    URL.create(
        "postgresql+psycopg2",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_host_port,
        database=TEST_DB,
    ),
    pool_pre_ping=True,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Build the tables once per test run, from the real schema file."""
    assert TEST_DB.endswith("_test")  # safety: never wipe a real database
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8-sig")
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.exec_driver_sql(schema)


@pytest.fixture(autouse=True)
def clean_tables():
    """Empty every table before each test, so tests can't affect each other."""
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, products, orders, order_items, reviews, cart_items "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def client():
    """A test client whose database dependency points at the test database."""

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def session_factory():
    """Lets a test read or change the test database directly."""
    return TestSession


@pytest.fixture
def make_product(session_factory):
    """Factory: make_product(name=..., price=..., stock=...) returns the new id."""

    def _make(name="Test Mug", price=10, stock=5, category="housewares"):
        with session_factory() as db:
            product = Product(
                name=name, price=Decimal(str(price)), stock=stock, category=category
            )
            db.add(product)
            db.commit()
            return product.id

    return _make


@pytest.fixture
def make_headers(client, session_factory):
    """Factory: registers and logs in a user, returns the Authorization header."""

    def _make(email="shopper@gmail.com", role="customer"):
        password = "password123"
        r = client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": "Test User"},
        )
        assert r.status_code == 201, r.text
        if role != "customer":
            # Admins can only be made in the database, never through the API
            with session_factory() as db:
                db.execute(update(User).where(User.email == email).values(role=role))
                db.commit()
        r = client.post("/auth/login", data={"username": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make