"""Pydantic schemas: the shapes of data the API accepts and returns.

These are kept separate from the ORM models so the API controls exactly which
fields go in and out (e.g. password_hash is never sent back to clients).
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, PlainSerializer, computed_field


class UserCreate(BaseModel):
    """Request body for registering a new account."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        """Reject passwords longer than 72 bytes, the most bcrypt can hash.

        max_length=72 counts characters, but accented letters or emoji take
        several bytes each, so this extra byte check is still needed.
        """
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v


class UserOut(BaseModel):
    """Public view of a user returned by the API (no password hash)."""

    # from_attributes lets pydantic read fields from an ORM object
    # (user.email) instead of only from a dict.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class Token(BaseModel):
    """Login response in the format OAuth2 clients (and Swagger UI) expect."""

    access_token: str
    token_type: str = "bearer"

# Pydantic v2 sends Decimal as a JSON *string* ("19.90"). React would then
# get text instead of a number, so we serialize money as a number.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class ProductOut(BaseModel):
    """A product as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str | None
    description: str | None
    price: Money
    stock: int
    created_at: datetime


class ProductPage(BaseModel):
    """One page of product results plus the info a UI needs to show pagination."""

    items: list[ProductOut]
    # Total matches across ALL pages, so the client can work out the page count.
    total: int
    page: int
    page_size: int


class ProductCreate(BaseModel):
    """Request body for creating a product (admin only)."""

    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    # These limits mirror the Numeric(10, 2) column, so bad values get a clear
    # 422 error here instead of a database error later.
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    stock: int = Field(default=100, ge=0)


class ProductUpdate(BaseModel):
    """Request body for PATCH: every field is optional.

    The None defaults just mean "not sent"; the route uses exclude_unset to
    change only the fields the client actually included.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)


class ProductBrief(BaseModel):
    """Minimal product info shown inside orders."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str | None


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product: ProductOut
    quantity: int

    @computed_field
    @property
    def line_total(self) -> Money:
        return self.product.price * self.quantity


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Money


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product: ProductBrief
    quantity: int
    unit_price: Money

    @computed_field
    @property
    def line_total(self) -> Money:
        return self.unit_price * self.quantity


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    total: Money
    created_at: datetime
    items: list[OrderItemOut]