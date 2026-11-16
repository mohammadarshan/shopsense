"""SQLAlchemy ORM models: one Python class per database table.

The tables themselves are created by db/schema.sql, which also holds the CHECK
constraints; keep these classes in step with it when either changes.

The olist_* columns keep the original IDs from the Olist dataset so seeded
rows can be traced back to the source CSVs. They are nullable because rows
created through the API have no Olist ID.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A customer or admin account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True makes the database itself reject duplicate emails, even if
    # two sign-ups race past the check in the register route.
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # Only the bcrypt hash is stored, never the plain password.
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="customer")
    olist_customer_unique_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    # server_default: SQLAlchemy leaves this column out of the INSERT and lets
    # the DEFAULT NOW() in db/schema.sql fill it in, using the database's clock.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Product(Base):
    """An item in the shop catalogue."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    olist_product_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    # Numeric (exact decimal) instead of float, so money never gets rounding
    # errors like 0.1 + 0.2 = 0.30000000000000004.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Order(Base):
    """A purchase made by a user, made up of one or more OrderItems."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    olist_order_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    # Foreign key: the DB guarantees every order points at a real user.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="orders")
    # delete-orphan: deleting an order (or removing an item from order.items)
    # also deletes those item rows, since a line item can't exist on its own.
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    """One product line within an order."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # ondelete="CASCADE" makes Postgres remove the items when their order is
    # deleted, even if the delete doesn't go through SQLAlchemy.
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    # No cascade here: a product that appears in orders can't be deleted,
    # which protects order history (see delete_product in routers/products.py).
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(default=1)
    # Price is copied at purchase time, so later price changes don't
    # rewrite what the customer actually paid.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Review(Base):
    """A user's star rating and optional comment on a product."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    # Optional link to the order the review came from (set for seeded data).
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    rating: Mapped[int]
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CartItem(Base):
    """A product sitting in a user's shopping cart."""

    __tablename__ = "cart_items"

    # Composite primary key (user_id, product_id): a user can have each
    # product in their cart once; more of it means a higher quantity, not a new row.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=1)

    product: Mapped["Product"] = relationship()