"""Load the Olist CSVs into the ShopSense PostgreSQL schema.

WARNING: this wipes users, products, orders, order_items, reviews and
cart_items before loading. It is for initial seeding only.
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "olist"
load_dotenv(ROOT / ".env")

engine = create_engine(
    URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host="localhost",
        port=5433,
        database=os.environ["POSTGRES_DB"],
    )
)


def read(name):
    return pd.read_csv(DATA / name)


customers = read("olist_customers_dataset.csv")
orders = read("olist_orders_dataset.csv")
items = read("olist_order_items_dataset.csv")
products = read("olist_products_dataset.csv")
reviews = read("olist_order_reviews_dataset.csv")
translation = read("product_category_name_translation.csv")

# ---------- users: one per real person (customer_unique_id) ----------
users = customers[["customer_unique_id"]].drop_duplicates().reset_index(drop=True)
users["id"] = users.index + 1
users["email"] = "user" + users["id"].astype(str) + "@example.com"
users["password_hash"] = "!seeded-account-no-login"
users["full_name"] = "Customer " + users["customer_unique_id"].str[:6]
users["role"] = "customer"
users = users.rename(columns={"customer_unique_id": "olist_customer_unique_id"})

# Olist's customer_id (one per order) -> our users.id
customers = customers.merge(
    users[["olist_customer_unique_id", "id"]].rename(
        columns={"olist_customer_unique_id": "customer_unique_id", "id": "user_id"}
    ),
    on="customer_unique_id",
)

# ---------- products: English category, generated name, price from sales ----------
avg_price = items.groupby("product_id")["price"].mean().round(2).reset_index()
products = products.merge(translation, on="product_category_name", how="left")
products["category"] = products["product_category_name_english"].fillna("unknown")
products = products.merge(avg_price, on="product_id")  # drops never-sold products
products = products.reset_index(drop=True)
products["id"] = products.index + 1
products["name"] = (
    products["category"].str.replace("_", " ").str.title() + " #" + products["id"].astype(str)
)
products = products.rename(columns={"product_id": "olist_product_id"})

prod_map = products[["olist_product_id", "id"]].rename(
    columns={"olist_product_id": "product_id", "id": "product_pk"}
)

# ---------- order lines: one row per (order, product) with a quantity ----------
items = items.merge(prod_map, on="product_id")
order_items = (
    items.groupby(["order_id", "product_pk"])
    .agg(quantity=("order_item_id", "count"), unit_price=("price", "mean"))
    .reset_index()
)
order_items["unit_price"] = order_items["unit_price"].round(2)

# ---------- orders: total = sum of item prices; orders with no items are dropped ----------
totals = items.groupby("order_id")["price"].sum().round(2).rename("total").reset_index()
orders = orders.merge(customers[["customer_id", "user_id"]], on="customer_id")
orders = orders.merge(totals, on="order_id").reset_index(drop=True)
orders["id"] = orders.index + 1
orders["created_at"] = pd.to_datetime(orders["order_purchase_timestamp"])
orders = orders.rename(columns={"order_id": "olist_order_id", "order_status": "status"})

order_map = orders[["olist_order_id", "id"]].rename(
    columns={"olist_order_id": "order_id", "id": "order_pk"}
)
order_items = order_items.merge(order_map, on="order_id")
order_items = order_items[["order_pk", "product_pk", "quantity", "unit_price"]].rename(
    columns={"order_pk": "order_id", "product_pk": "product_id"}
)

# ---------- reviews: only orders with exactly one product ----------
# Olist reviews belong to an order, but our table links a review to one product.
counts = order_items["order_id"].value_counts()
single = order_items[order_items["order_id"].isin(counts[counts == 1].index)][
    ["order_id", "product_id"]
]
reviews = (
    reviews.drop_duplicates("order_id")
    .merge(order_map, on="order_id")
    .drop(columns="order_id")
    .rename(columns={"order_pk": "order_id"})
    .merge(single, on="order_id")
    .merge(orders[["id", "user_id"]].rename(columns={"id": "order_id"}), on="order_id")
)
reviews["rating"] = reviews["review_score"]
reviews["comment"] = reviews["review_comment_message"]
reviews["created_at"] = pd.to_datetime(reviews["review_creation_date"])

# ---------- write everything in ONE transaction ----------
tables = {
    "users": (users, ["id", "email", "password_hash", "full_name", "role", "olist_customer_unique_id"]),
    "products": (products, ["id", "olist_product_id", "name", "category", "price"]),
    "orders": (orders, ["id", "olist_order_id", "user_id", "status", "total", "created_at"]),
    "order_items": (order_items, ["order_id", "product_id", "quantity", "unit_price"]),
    "reviews": (reviews, ["user_id", "product_id", "order_id", "rating", "comment", "created_at"]),
}

with engine.begin() as conn:
    conn.execute(
        text(
            "TRUNCATE users, products, orders, order_items, reviews, cart_items "
            "RESTART IDENTITY CASCADE"
        )
    )
    for name, (df, cols) in tables.items():
        df[cols].to_sql(name, conn, if_exists="append", index=False, method="multi", chunksize=5000)
        print(f"loaded {len(df):>7} rows into {name}")

    # We inserted explicit ids, so move each auto-increment counter past them
    for name in ["users", "products", "orders"]:
        conn.execute(
            text(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), (SELECT MAX(id) FROM {name}))")
        )

print("done")