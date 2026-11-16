def test_list_is_public_and_paginated(client, make_product):
    for i in range(5):
        make_product(name=f"Mug {i}", price=10 + i)
    r = client.get("/products", params={"page": 1, "page_size": 2})
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1


def test_pages_do_not_overlap(client, make_product):
    for i in range(5):
        make_product(name=f"Mug {i}")
    page1 = client.get("/products", params={"page": 1, "page_size": 3}).json()["items"]
    page2 = client.get("/products", params={"page": 2, "page_size": 3}).json()["items"]
    ids1 = {p["id"] for p in page1}
    ids2 = {p["id"] for p in page2}
    assert len(page1) == 3 and len(page2) == 2
    assert ids1.isdisjoint(ids2)


def test_search_and_category_filter(client, make_product):
    make_product(name="Red Mug", category="housewares")
    make_product(name="Blue Toy", category="toys")
    by_search = client.get("/products", params={"search": "mug"}).json()
    by_category = client.get("/products", params={"category": "toys"}).json()
    assert [p["name"] for p in by_search["items"]] == ["Red Mug"]
    assert [p["name"] for p in by_category["items"]] == ["Blue Toy"]


def test_price_filter_and_sort(client, make_product):
    make_product(name="Cheap", price=5)
    make_product(name="Middle", price=50)
    make_product(name="Pricey", price=500)
    r = client.get("/products", params={"min_price": 10, "sort": "price_desc"})
    assert [p["name"] for p in r.json()["items"]] == ["Pricey", "Middle"]


def test_price_is_a_json_number(client, make_product):
    make_product(price=12.5)
    price = client.get("/products").json()["items"][0]["price"]
    assert isinstance(price, float)
    assert price == 12.5


def test_page_size_over_limit_is_rejected_by_the_server(client):
    assert client.get("/products", params={"page_size": 500}).status_code == 422


def test_get_product_and_missing_product(client, make_product):
    pid = make_product(name="Real Mug")
    assert client.get(f"/products/{pid}").json()["name"] == "Real Mug"
    assert client.get("/products/999999").status_code == 404


def test_categories_route_is_not_mistaken_for_an_id(client, make_product):
    make_product(category="toys")
    make_product(category="housewares")
    r = client.get("/products/categories")
    assert r.status_code == 200
    assert r.json() == ["housewares", "toys"]


def test_anonymous_cannot_create_product(client):
    r = client.post("/products", json={"name": "Mug", "price": 5})
    assert r.status_code == 401


def test_customer_cannot_create_product(client, make_headers):
    r = client.post(
        "/products", json={"name": "Mug", "price": 5}, headers=make_headers()
    )
    assert r.status_code == 403


def test_admin_can_create_product(client, make_headers):
    admin = make_headers("boss@gmail.com", role="admin")
    r = client.post(
        "/products", json={"name": "New Mug", "price": 12.5}, headers=admin
    )
    assert r.status_code == 201
    assert client.get(f"/products/{r.json()['id']}").json()["name"] == "New Mug"


def test_negative_price_is_rejected(client, make_headers):
    admin = make_headers("boss@gmail.com", role="admin")
    r = client.post("/products", json={"name": "Bad", "price": -1}, headers=admin)
    assert r.status_code == 422


def test_patch_changes_only_the_fields_sent(client, make_headers, make_product):
    admin = make_headers("boss@gmail.com", role="admin")
    pid = make_product(name="Mug", price=10, stock=5)
    r = client.patch(f"/products/{pid}", json={"price": 9.99}, headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["price"] == 9.99
    assert body["name"] == "Mug"
    assert body["stock"] == 5


def test_patch_cannot_null_a_required_field(client, make_headers, make_product):
    admin = make_headers("boss@gmail.com", role="admin")
    pid = make_product()
    r = client.patch(f"/products/{pid}", json={"price": None}, headers=admin)
    assert r.status_code == 422


def test_admin_can_delete_product(client, make_headers, make_product):
    admin = make_headers("boss@gmail.com", role="admin")
    pid = make_product()
    assert client.delete(f"/products/{pid}", headers=admin).status_code == 204
    assert client.get(f"/products/{pid}").status_code == 404