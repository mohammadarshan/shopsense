"""Entry point of the ShopSense API: creates the FastAPI app and plugs in the routers.

Run with uvicorn (e.g. `uvicorn app.main:app --reload` from the backend folder).
"""
from fastapi import Depends, FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product, User
from app.routers import auth, products
from app.dependencies import require_admin

# title/description/version show up in the auto-generated docs at /docs.
app = FastAPI(
    title="ShopSense API",
    description="E-commerce backend with ML-powered features",
    version="0.1.0",
)

# Each router lives in its own file to keep this one small; including it here
# registers all of its endpoints on the app.
app.include_router(auth.router)
app.include_router(products.router)

@app.get("/")
def root():
    """Simple welcome message to confirm the API is running."""
    return {"message": "Welcome to the ShopSense API"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Health check that also confirms the database is reachable.

    If Postgres is down, the query raises and the endpoint returns a 500,
    which is what monitoring tools look for.
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/stats")
def stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Row counts for the main tables (admin only).

    `admin` isn't used in the body; declaring it is what runs the admin check.
    """
    # COUNT(*) runs in the database, so we never load every row into Python.
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "products": db.scalar(select(func.count()).select_from(Product)),
        "orders": db.scalar(select(func.count()).select_from(Order)),
    }