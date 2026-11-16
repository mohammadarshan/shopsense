from sqlalchemy import select, update

from app.models import Order, Product


def add(client, headers, product_id, quantity=1):
    return client.post(
        "/cart/items",
        json={"product_id": product_id, "quantity": quantity},
        headers=headers,
    )


def stock_of(session_factory, product_id):
    with session_factory() as db:
        return db.scalar(select(Product.stock).where(Product.id == product_id))


def count_orders(session_factory):
    with session_factory() as db:
        return len(db.scalars(select(Order)).all())


def test_cart_requires_login(client):
    assert client.get("/cart").status_code == 401


def test_new_cart_is_empty(client, make_headers):
    r = client.get("/cart", headers=make_headers())
    assert r.json() == {"items": [], "total": 0}


def test_adding_the_same_product_twice_adds_quantities(client, make_headers, make_product):
    pid = make_product(stock=10)
    headers = make_headers()
    add(client, headers, pid, 2)
    r = add(client, headers, pid, 3)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 5


def test_cart_totals_use_database_prices(client, make_headers, make_product):
    pid = make_product(price=10, stock=10)
    r = add(client, make_headers(), pid, 3)
    body = r.json()
    assert body["items"][0]["line_total"] == 30
    assert body["total"] == 30


def test_cannot_add_more_than_stock(client, make_headers, make_product):
    pid = make_product(stock=2)
    assert add(client, make_headers(), pid, 5).status_code == 409


def test_cannot_add_unknown_product(client, make_headers):
    assert add(client, make_headers(), 999999).status_code == 404


def test_checkout_creates_order_reduces_stock_and_empties_cart(
    client, make_headers, make_product, session_factory
):
    pid = make_product(price=10, stock=5)
    headers = make_headers()
    add(client, headers, pid, 3)

    r = client.post("/orders", headers=headers)

    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "pending"
    assert order["total"] == 30
    assert order["items"][0]["quantity"] == 3
    assert stock_of(session_factory, pid) == 2
    assert client.get("/cart", headers=headers).json()["items"] == []


def test_checkout_with_empty_cart_is_rejected(client, make_headers):
    assert client.post("/orders", headers=make_headers()).status_code == 400


def test_checkout_fails_cleanly_when_stock_ran_out(
    client, make_headers, make_product, session_factory
):
    pid = make_product(stock=5)
    headers = make_headers()
    add(client, headers, pid, 3)
    # someone else buys most of the stock after this user filled the cart
    with session_factory() as db:
        db.execute(update(Product).where(Product.id == pid).values(stock=1))
        db.commit()

    r = client.post("/orders", headers=headers)

    assert r.status_code == 409
    assert count_orders(session_factory) == 0  # nothing was created
    assert stock_of(session_factory, pid) == 1  # stock untouched
    assert len(client.get("/cart", headers=headers).json()["items"]) == 1  # cart kept


def test_order_keeps_the_price_it_was_bought_at(client, make_headers, make_product):
    admin = make_headers("boss@gmail.com", role="admin")
    shopper = make_headers("shopper@gmail.com")
    pid = make_product(price=10, stock=5)
    add(client, shopper, pid, 1)
    order_id = client.post("/orders", headers=shopper).json()["id"]

    client.patch(f"/products/{pid}", json={"price": 99}, headers=admin)

    order = client.get(f"/orders/{order_id}", headers=shopper).json()
    assert order["items"][0]["unit_price"] == 10
    assert order["total"] == 10


def test_user_cannot_read_someone_elses_order(client, make_headers, make_product):
    alice = make_headers("alice@gmail.com")
    bob = make_headers("bob@gmail.com")
    pid = make_product(stock=5)
    add(client, alice, pid, 1)
    order_id = client.post("/orders", headers=alice).json()["id"]

    assert client.get(f"/orders/{order_id}", headers=alice).status_code == 200
    assert client.get(f"/orders/{order_id}", headers=bob).status_code == 404
    assert client.get("/orders", headers=bob).json() == []


def test_order_history_lists_newest_first(client, make_headers, make_product):
    pid = make_product(stock=10)
    headers = make_headers()
    add(client, headers, pid, 1)
    first = client.post("/orders", headers=headers).json()["id"]
    add(client, headers, pid, 1)
    second = client.post("/orders", headers=headers).json()["id"]

    ids = [o["id"] for o in client.get("/orders", headers=headers).json()]
    assert ids == [second, first]