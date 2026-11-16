"""Shared pytest fixtures.

Tests run against a separate database (<POSTGRES_DB>_test) that is built from
db/schema.sql and wiped before every test. The real database is never touched.

The _test database must already exist on the same Postgres server (these
fixtures only rebuild its tables), e.g.:
    docker exec shopsense-db createdb -U <POSTGRES_USER> <POSTGRES_DB>_test
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

# Same connection settings as app/database.py, but pointed at TEST_DB.
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
    """Rebuild the test database's tables once per run, from db/schema.sql.

    session scope + autouse: runs once before the first test, without any test
    asking for it. Dropping the whole schema first means CREATE TABLE never
    hits a table left over from an earlier run or an older schema.sql. Using
    the real schema file (not the ORM models) means the tests also exercise
    its CHECK constraints and foreign keys.
    """
    assert TEST_DB.endswith("_test")  # safety: never wipe a real database
    # utf-8-sig strips a byte-order mark, which some Windows editors add and
    # Postgres would reject as a syntax error.
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8-sig")
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        # exec_driver_sql hands the file to psycopg2 untouched; text() would
        # try to read any ":word" in the SQL as a bind parameter.
        conn.exec_driver_sql(schema)


@pytest.fixture(autouse=True)
def clean_tables():
    """Empty every table before each test, so tests can't affect each other.

    autouse: applies to every test without being requested. RESTART IDENTITY
    resets the id counters, so the first user and product in each test get id 1.
    """
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, products, orders, order_items, reviews, cart_items "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def client():
    """An HTTP client that calls the app in-process, with the test database swapped in.

    dependency_overrides makes every route that asks for get_db get a session
    on the test database instead. The override is removed after the test so
    it can't leak into other tests or into the app object.
    """

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
    """The test database's session factory, for setting up or checking data directly.

    Use it as `with session_factory() as db:` to bypass the API, e.g. to
    simulate another shopper changing stock, or to confirm what a request
    actually wrote.
    """
    return TestSession


@pytest.fixture
def make_product(session_factory):
    """Factory: make_product(name=..., price=..., stock=..., category=...) -> new product id.

    Inserts straight into the database, so tests don't need an admin login just
    to have something to buy. Call it several times for several products.
    """

    def _make(name="Test Mug", price=10, stock=5, category="housewares"):
        with session_factory() as db:
            product = Product(
                # str() first, so 12.5 becomes Decimal("12.5") rather than
                # carrying float rounding error into the price.
                name=name, price=Decimal(str(price)), stock=stock, category=category
            )
            db.add(product)
            db.commit()
            return product.id

    return _make


@pytest.fixture
def make_headers(client, session_factory):
    """Factory: make_headers(email=..., role=...) -> {"Authorization": "Bearer ..."}.

    Registers and logs in through the real API, so every authenticated test
    also covers the sign-up and login flow. Pass role="admin" for an admin. Each
    call needs a different email, since an email can only register once.
    """

    def _make(email="shopper@gmail.com", role="customer"):
        password = "password123"
        r = client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": "Test User"},
        )
        assert r.status_code == 201, r.text
        if role != "customer":
            # The API always registers customers, so promote the user in the
            # database before logging in.
            with session_factory() as db:
                db.execute(update(User).where(User.email == email).values(role=role))
                db.commit()
        r = client.post("/auth/login", data={"username": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make