from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import CartItem, Product, User
from app.schemas import CartItemAdd, CartItemUpdate, CartOut

router = APIRouter(prefix="/cart", tags=["cart"])


def cart_response(db: Session, user: User) -> dict:
    """Load the user's cart and total it. Every cart endpoint returns this."""
    items = db.scalars(
        select(CartItem)
        .where(CartItem.user_id == user.id)
        .options(selectinload(CartItem.product))  # one extra query, not one per item
        .order_by(CartItem.product_id)
    ).all()
    total = sum((i.product.price * i.quantity for i in items), Decimal("0"))
    return {"items": items, "total": total}


@router.get("", response_model=CartOut)
def get_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cart_response(db, user)


@router.post("/items", response_model=CartOut)
def add_to_cart(
    payload: CartItemAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    item = db.get(CartItem, (user.id, product.id))  # composite primary key
    new_quantity = payload.quantity + (item.quantity if item else 0)
    if new_quantity > product.stock:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only {product.stock} in stock")

    if item:
        item.quantity = new_quantity
    else:
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=new_quantity))
    db.commit()
    return cart_response(db, user)


@router.patch("/items/{product_id}", response_model=CartOut)
def update_cart_item(
    product_id: int,
    payload: CartItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(CartItem, (user.id, product_id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item is not in your cart")
    if payload.quantity > item.product.stock:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Only {item.product.stock} in stock"
        )
    item.quantity = payload.quantity
    db.commit()
    return cart_response(db, user)


@router.delete("/items/{product_id}", response_model=CartOut)
def remove_from_cart(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(CartItem, (user.id, product_id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item is not in your cart")
    db.delete(item)
    db.commit()
    return cart_response(db, user)


@router.delete("", response_model=CartOut)
def clear_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    return cart_response(db, user)