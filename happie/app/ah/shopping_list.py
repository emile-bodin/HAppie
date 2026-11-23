"""AH shopping list endpoints."""
from __future__ import annotations

from typing import Any

from ah.models import ListItem


class ShoppingListMixin:
    async def get_list(self) -> list[ListItem]:
        data = await self._raw("GET", "/mobile-services/shoppinglist/v2/items")
        items: list[ListItem] = []
        for raw in (data or {}).get("items", []) if isinstance(data, dict) else data or []:
            details = ((raw.get("productDetails") or {}).get("product")) or {}
            product_id = raw.get("productId") or details.get("webshopId")
            name = raw.get("description") or details.get("title") or ""
            checked = bool(
                raw.get("strikedthrough", raw.get("strikeThrough", raw.get("strikethrough", False)))
            )
            if not name:
                continue
            items.append(
                ListItem(
                    name=name,
                    quantity=int(raw.get("quantity") or 1),
                    checked=checked,
                    product_id=int(product_id) if product_id else None,
                    raw=raw,
                )
            )
        return items

    @staticmethod
    def _item_body(name: str, product_id: int | None, quantity: int, checked: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "description": name,
            "quantity": quantity,
            "type": "SHOPPABLE",
            "strikeThrough": checked,
        }
        if product_id:
            body["productId"] = product_id
            body["originCode"] = "PRD"
            body["searchTerm"] = name
        else:
            body["originCode"] = "TXT"
        return body

    async def _patch(self, items: list[dict[str, Any]]) -> None:
        if items:
            await self._raw("PATCH", "/mobile-services/shoppinglist/v2/items", json_body={"items": items})

    async def add_item(
        self, name: str, product_id: int | None = None, quantity: int = 1, checked: bool = False
    ) -> None:
        await self._patch([self._item_body(name, product_id, quantity, checked)])

    async def set_checked(self, item: ListItem, checked: bool) -> None:
        await self._patch([self._item_body(item.name, item.product_id, item.quantity, checked)])

    async def set_quantity(self, item: ListItem, quantity: int) -> None:
        await self._patch([self._item_body(item.name, item.product_id, quantity, item.checked)])

    async def remove_items(self, items: list[ListItem]) -> None:
        await self._patch([self._item_body(i.name, i.product_id, 0, i.checked) for i in items])
