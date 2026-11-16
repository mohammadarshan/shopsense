from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import CartItem, Order, OrderItem, Product, User
from app.schemas import OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])

# Eagerly load items and their products so building the response doesn't
# fire one query per item
ORDER_LOAD = selectinload(Order.items).selectinload(OrderItem.product)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def checkout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart_items = db.scalars(
        select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.product_id)
    ).all()
    if not cart_items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your cart is empty")

    # Lock the product rows until we commit, so two checkouts can't both
    # take the last item. Sorted by id so concurrent checkouts lock in the
    # same order and can't deadlock each other.
    product_ids = [c.product_id for c in cart_items]
    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }

    problems = [
        f"{products[c.product_id].name}: wanted {c.quantity}, only {products[c.product_id].stock} left"
        for c in cart_items
        if c.quantity > products[c.product_id].stock
    ]
    if problems:
        db.rollback()  # nothing was changed; release the locks now
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Not enough stock - " + "; ".join(problems)
        )

    order = Order(user_id=user.id, status="pending", total=Decimal("0"))
    total = Decimal("0")
    for c in cart_items:
        product = products[c.product_id]
        product.stock -= c.quantity
        total += product.price * c.quantity
        # unit_price is a snapshot: later price changes don't rewrite history
        order.items.append(
            OrderItem(product_id=product.id, quantity=c.quantity, unit_price=product.price)
        )
    order.total = total

    db.add(order)
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()  # order, items, stock changes and cart wipe: all or nothing

    return db.scalars(select(Order).where(Order.id == order.id).options(ORDER_LOAD)).one()


@router.get("", response_model=list[OrderOut])
def my_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .options(ORDER_LOAD)
        .order_by(Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(ORDER_LOAD)
    )
    if order is None:
        # Same 404 whether the order doesn't exist or belongs to someone else,
        # so nobody can probe which order ids exist
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order