import os
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.request import Request as ClientRequest
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from request_logging import REQUEST_ID_HEADER, add_request_logging

app = FastAPI()
add_request_logging(app, service="orders", path_prefix="/orders")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["POST"],
    allow_headers=["Content-Type", REQUEST_ID_HEADER],
)
ORDERS_DB = Path(
    os.getenv("ORDERS_DB_PATH") or Path(__file__).with_name("orders_demo.sqlite3")
).resolve()
PRODUCT_API_URL = os.getenv("PRODUCT_API_URL", "http://127.0.0.1:8000/api/v1/products")


class Order(BaseModel):
    order_id: str
    sku: str
    quantity: int = Field(gt=0)


class CatalogProduct(BaseModel):
    sku: str


class ProductCatalog(BaseModel):
    products: list[CatalogProduct]


def fetch_product_catalog(request_id: str | None = None) -> ProductCatalog:
    """Ruft den Katalog ab und prüft sein JSON-Format."""
    headers = {REQUEST_ID_HEADER: request_id} if request_id else {}
    product_request = ClientRequest(PRODUCT_API_URL, headers=headers)
    try:
        with urlopen(product_request, timeout=3) as response:
            return ProductCatalog.model_validate_json(response.read())
    except (OSError, ValidationError) as error:
        raise HTTPException(
            status_code=503,
            detail="Produktkatalog vorübergehend nicht verfügbar.",
        ) from error


def product_exists(sku: str, request_id: str) -> bool:
    return any(product.sku == sku for product in fetch_product_catalog(request_id).products)


@app.get("/health/live", tags=["Health"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get(
    "/health/ready",
    tags=["Health"],
    responses={503: {"description": "Produktkatalog nicht verfügbar"}},
)
def readiness() -> dict[str, str]:
    fetch_product_catalog()
    return {"status": "ready"}


def insert_order(order: Order) -> bool:
    with closing(sqlite3.connect(ORDERS_DB)) as db, db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                quantity INTEGER NOT NULL
            )
        """)

        result = db.execute(
            """
            INSERT INTO orders (order_id, sku, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(order_id) DO NOTHING
            """,
            (order.order_id, order.sku, order.quantity),
        )
    return result.rowcount == 1


def find_order(order_id: str) -> Order | None:
    row = None
    if ORDERS_DB.is_file():
        database_uri = f"{ORDERS_DB.as_uri()}?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True)) as db:
            orders_table = db.execute(
                "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'orders'"
            ).fetchone()
            if orders_table is not None:
                row = db.execute(
                    "SELECT order_id, sku, quantity FROM orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()

    if row is None:
        return None

    saved_order_id, sku, quantity = row
    return Order(order_id=saved_order_id, sku=sku, quantity=quantity)


@app.post(
    "/orders",
    status_code=201,
    responses={
        200: {"model": Order, "description": "Identische Bestellung bereits gespeichert"},
        409: {"description": "Bestellnummer gehört zu einer anderen Bestellung"},
    },
)
def create_order(order: Order, request: Request, response: Response) -> Order:
    saved_order = find_order(order.order_id)
    if saved_order is None:
        if not product_exists(order.sku, request.state.request_id):
            raise HTTPException(status_code=422, detail="Artikelnummer unbekannt.")
        if insert_order(order):
            return order

        # Ein paralleler Aufruf hat dieselbe Bestellnummer zuerst gespeichert.
        saved_order = find_order(order.order_id)

    if saved_order != order:
        raise HTTPException(
            status_code=409,
            detail="Bestellnummer ist bereits mit anderen Bestelldaten belegt.",
        )

    response.status_code = 200
    return saved_order


@app.get("/orders/{order_id}")
def get_order(order_id: str) -> Order:
    order = find_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden.")
    return order
