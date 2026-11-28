import os
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request as ClientRequest
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from request_logging import REQUEST_ID_HEADER, add_request_logging

ERP_DB = Path(
    os.getenv("ERP_DB_PATH") or Path(__file__).with_name("erp_uebung.sqlite3")
).resolve()
ORDER_API_URL = os.getenv("ORDER_API_URL", "http://127.0.0.1:8001").rstrip("/")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with closing(sqlite3.connect(ERP_DB)) as db, db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS erp_orders (
                id INTEGER PRIMARY KEY,
                shop_order_id TEXT NOT NULL UNIQUE,
                sku TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0)
            )
        """)
    yield


app = FastAPI(title="Python Fitness ERP-Demo", lifespan=lifespan)
add_request_logging(app, service="erp", path_prefix="/erp/orders")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["POST"],
    allow_headers=["Content-Type", REQUEST_ID_HEADER],
)


class ShopOrder(BaseModel):
    order_id: str
    sku: str
    quantity: int = Field(gt=0)


class ErpOrder(BaseModel):
    erp_order_id: str
    shop_order_id: str
    sku: str
    quantity: int


def fetch_shop_order(shop_order_id: str, request_id: str) -> ShopOrder:
    order_url = f"{ORDER_API_URL}/orders/{quote(shop_order_id, safe='')}"
    request = ClientRequest(order_url, headers={REQUEST_ID_HEADER: request_id})
    try:
        with urlopen(request, timeout=3) as response:
            order = ShopOrder.model_validate_json(response.read())
    except (OSError, ValidationError) as error:
        if isinstance(error, HTTPError) and error.code == 404:
            raise HTTPException(status_code=404, detail="Shop-Bestellung nicht gefunden.") from error
        raise HTTPException(status_code=503, detail="Bestellservice vorübergehend nicht verfügbar.") from error

    if order.order_id != shop_order_id:
        raise HTTPException(status_code=502, detail="Bestellservice lieferte eine andere Bestellnummer.")
    return order


def to_erp_order(row: tuple[int, str, str, int]) -> ErpOrder:
    number, shop_order_id, sku, quantity = row
    return ErpOrder(
        erp_order_id=f"ERP-{number:03d}",
        shop_order_id=shop_order_id,
        sku=sku,
        quantity=quantity,
    )


def find_erp_order(db: sqlite3.Connection, shop_order_id: str) -> ErpOrder | None:
    row = db.execute(
        "SELECT id, shop_order_id, sku, quantity FROM erp_orders WHERE shop_order_id = ?",
        (shop_order_id,),
    ).fetchone()
    return to_erp_order(row) if row is not None else None


@app.get("/", include_in_schema=False)
def order_overview() -> FileResponse:
    return FileResponse(Path(__file__).with_name("erp_uebersicht.html"), media_type="text/html")


@app.get("/erp/orders")
def list_erp_orders() -> list[ErpOrder]:
    with closing(sqlite3.connect(ERP_DB)) as db:
        rows = db.execute(
            "SELECT id, shop_order_id, sku, quantity FROM erp_orders ORDER BY id DESC"
        ).fetchall()
    return [to_erp_order(row) for row in rows]


@app.post(
    "/erp/orders/import/{shop_order_id}",
    status_code=201,
    responses={
        200: {"model": ErpOrder, "description": "Auftrag bereits übernommen"},
        404: {"description": "Shop-Bestellung fehlt"},
        503: {"description": "Bestellservice vorübergehend nicht verfügbar"},
    },
)
def import_order(shop_order_id: str, request: Request, response: Response) -> ErpOrder:
    with closing(sqlite3.connect(ERP_DB)) as db, db:
        saved = find_erp_order(db, shop_order_id)
        if saved is not None:
            response.status_code = 200
            return saved

        order = fetch_shop_order(shop_order_id, request.state.request_id)
        result = db.execute(
            """
            INSERT INTO erp_orders (shop_order_id, sku, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(shop_order_id) DO NOTHING
            """,
            (order.order_id, order.sku, order.quantity),
        )
        saved = find_erp_order(db, shop_order_id)
        if saved is None:
            raise RuntimeError("ERP-Auftrag fehlt nach dem Import.")
        if result.rowcount == 0:
            response.status_code = 200
        return saved


@app.get("/erp/orders/{shop_order_id}")
def get_erp_order(shop_order_id: str) -> ErpOrder:
    with closing(sqlite3.connect(ERP_DB)) as db:
        saved = find_erp_order(db, shop_order_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="ERP-Auftrag nicht gefunden.")
    return saved
