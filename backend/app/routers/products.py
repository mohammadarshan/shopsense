"""Product endpoints: public browsing (search, filter, sort, paginate) and admin CRUD."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Product, User
from app.schemas import ProductCreate, ProductOut, ProductPage, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

# The extra Product.id makes the order stable, so pages never repeat or skip rows
SORTS = {
    "newest": [Product.id.desc()],
    "price_asc": [Product.price.asc(), Product.id],
    "price_desc": [Product.price.desc(), Product.id],
    "name": [Product.name.asc(), Product.id],
}


@router.get("", response_model=ProductPage)
def list_products(
    # Parameters that aren't in the path become query-string params
    # (?search=...&page=2). Query(...) adds validation, e.g. page must be >= 1.
    search: str | None = None,
    category: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    # Literal restricts sort to known keys, so FastAPI returns 422 for anything
    # else and SORTS[sort] below can never raise a KeyError.
    sort: Literal["newest", "price_asc", "price_desc", "name"] = "newest",
    page: int = Query(default=1, ge=1),
    # Capped at 100 so one request can't ask for the whole table.
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List products with optional search, filters, sorting and pagination."""
    # Build the query step by step, adding a filter only if it was provided.
    query = select(Product)
    if search:
        # ilike = case-insensitive match. The value is sent as a bound
        # parameter, so user input can't inject SQL.
        query = query.where(Product.name.ilike(f"%{search}%"))
    if category:
        query = query.where(Product.category == category)
    # "is not None" instead of a plain truth check, so a filter of 0 still applies.
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)

    # Count all matches (before paging) by wrapping the filtered query as a subquery.
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    # Skip the rows of earlier pages: page 1 -> offset 0, page 2 -> offset page_size, ...
    items = db.scalars(
        query.order_by(*SORTS[sort]).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# Must come BEFORE /{product_id}, otherwise "categories" is read as an id
@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    """Return every distinct category name, sorted, e.g. to fill a filter dropdown."""
    rows = db.scalars(
        select(Product.category)
        .where(Product.category.is_not(None))
        .distinct()
        .order_by(Product.category)
    )
    return list(rows)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Return a single product by id, or 404 if it doesn't exist."""
    # db.get looks up by primary key (and reuses the object if already loaded).
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    # Not used in the body; declaring it is what enforces the admin check.
    admin: User = Depends(require_admin),
):
    """Create a new product (admin only)."""
    # model_dump() turns the validated body into a dict whose keys match the columns.
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Partially update a product (admin only); only the fields sent are changed."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    # exclude_unset keeps only fields the client actually sent. Without it,
    # every missing field would come through as None and wipe existing data.
    changes = payload.model_dump(exclude_unset=True)
    # A client can still send an explicit null. These columns are required,
    # so reject that with a clear 422 instead of a database error.
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name cannot be null")
    if "price" in changes and changes["price"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "price cannot be null")
    if "stock" in changes and changes["stock"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "stock cannot be null")

    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a product (admin only), unless other records still reference it."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    # Let the foreign keys decide: Postgres refuses the delete if any order,
    # review or cart row still points at this product.
    try:
        db.delete(product)
        db.commit()
    except IntegrityError:
        # A failed commit leaves the session unusable until it's rolled back.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Product has orders, reviews or cart entries and cannot be deleted",
        )