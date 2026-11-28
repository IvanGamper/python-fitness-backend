from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShopProduct(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{0,31}$")
    name: str = Field(min_length=1)
    price_cents: int = Field(strict=True, ge=0, le=2**63 - 1)
    currency: Literal["EUR"]


class ShopCatalog(BaseModel):
    products: list[ShopProduct]

    @field_validator("products")
    @classmethod
    def validate_unique_skus(cls, products: list[ShopProduct]) -> list[ShopProduct]:
        if len({product.sku for product in products}) != len(products):
            raise ValueError("Artikelnummern müssen eindeutig sein.")
        return products


DEMO_CATALOG = ShopCatalog(
    products=[
        ShopProduct(
            sku="PF-UPPER-HANDSTAND",
            name="Upper Body & Handstand",
            price_cents=0,
            currency="EUR",
        ),
        ShopProduct(
            sku="PF-SHOULDER-MOBILITY",
            name="Shoulder & Mobility",
            price_cents=100,
            currency="EUR",
        ),
    ],
)
