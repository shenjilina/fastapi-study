from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = Field(default_factory=list)


@router.post("/items/", response_model=Item)
async def create_item(item: Item) -> Any:
    return item


@router.get("/items/", response_model=list[Item])
async def read_items() -> Any:
    return [
        {"name": "Portal Gun", "price": 42.0},
        {"name": "Plumbus", "price": 32.0},
    ]
