import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.request import Request, urlopen

from pydantic import ValidationError

from shop_catalog import ShopCatalog


def fetch_catalog(url: str) -> ShopCatalog:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        return ShopCatalog.model_validate_json(response.read())


def sync_products(catalog: ShopCatalog, database: Path) -> dict[str, int]:
    counts = {"neu": 0, "aktualisiert": 0, "unverändert": 0}

    with closing(sqlite3.connect(database, timeout=5)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artikel (
                artikelnummer TEXT NOT NULL PRIMARY KEY,
                bezeichnung TEXT NOT NULL,
                preis_cent INTEGER NOT NULL CHECK (preis_cent >= 0),
                waehrung TEXT NOT NULL
            )
            """
        )

        for product in catalog.products:
            # Shop-Felder auf die entsprechenden ERP-Felder abbilden.
            erp_values = (product.name, product.price_cents, product.currency)
            current = connection.execute(
                """
                SELECT bezeichnung, preis_cent, waehrung
                FROM artikel WHERE artikelnummer = ?
                """,
                (product.sku,),
            ).fetchone()
            if current == erp_values:
                counts["unverändert"] += 1
                continue

            connection.execute(
                """
                INSERT INTO artikel (artikelnummer, bezeichnung, preis_cent, waehrung)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(artikelnummer) DO UPDATE SET
                    bezeichnung = excluded.bezeichnung,
                    preis_cent = excluded.preis_cent,
                    waehrung = excluded.waehrung
                """,
                (product.sku, *erp_values),
            )
            counts["neu" if current is None else "aktualisiert"] += 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Shop-Katalog ins lokale Demo-ERP importieren")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/products")
    parser.add_argument("--db", type=Path, default=Path("erp-demo.sqlite3"))
    args = parser.parse_args()

    try:
        catalog = fetch_catalog(args.url)
    except ValidationError as error:
        parser.exit(1, f"Ungültige Antwort der Shop-API ({args.url}):\n{error}\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Shop-API nicht abrufbar ({args.url}): {error}\n")

    try:
        counts = sync_products(catalog, args.db)
    except sqlite3.Error as error:
        parser.exit(1, f"Import in {args.db} fehlgeschlagen: {error}\n")

    summary = ", ".join(f"{count} {status}" for status, count in counts.items())
    print(f"ERP-Import in {args.db}: {summary}")


if __name__ == "__main__":
    main()
