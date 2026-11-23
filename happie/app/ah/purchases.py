"""Purchases for the spending overview: online orders and store receipts."""
from __future__ import annotations

from typing import Any

from ah.errors import AHError
from ah.models import local_date


class PurchasesMixin:
    @staticmethod
    def order_total(summary: dict[str, Any]) -> float | None:
        """Amount paid for an order, from its summary (orderTotalPrice.priceTotalPayable)."""
        price = summary.get("orderTotalPrice") or summary.get("totalPrice") or {}
        value = price.get("priceTotalPayable", price.get("priceAfterDiscount"))
        return float(value) if value is not None else None

    async def online_purchases(self) -> list[dict[str, Any]]:
        """Delivered online orders as purchases: [{id, source, date, total}]."""
        out = []
        for o in await self.order_summaries():
            if str(o.get("state", "")).upper() not in ("DELIVERED", "COMPLETED"):
                continue
            total = self.order_total(o)
            if total is None or not o.get("deliveryDate"):
                continue
            out.append({"id": f"order:{o.get('orderId')}", "source": "online",
                        "date": o["deliveryDate"][:10], "total": round(total, 2)})
        return out

    async def store_purchases(self, since: str, page_size: int = 50, max_pages: int = 20,
                              known: set[str] | None = None) -> list[dict[str, Any]]:
        """In-store receipts (kassabonnen) since `since` (YYYY-MM-DD), newest first.

        Stops early at a page that only holds receipts already in `known`.
        """
        query = (
            "query($offset: Int!, $limit: Int!) { posReceiptsPage(pagination: {offset: $offset, limit: $limit}) "
            "{ posReceipts { id dateTime totalAmount { amount } } } }"
        )
        out: list[dict[str, Any]] = []
        for page in range(max_pages):
            data = await self._raw("POST", "/graphql", json_body={
                "query": query, "variables": {"offset": page * page_size, "limit": page_size}})
            if isinstance(data, dict) and data.get("errors") and not data.get("data"):
                raise AHError(str(data["errors"][0].get("message")))
            receipts = (((data or {}).get("data") or {}).get("posReceiptsPage") or {}).get("posReceipts") or []
            done = not receipts
            new_on_page = 0
            for r in receipts:
                date = local_date(r.get("dateTime") or "")
                amount = (r.get("totalAmount") or {}).get("amount")
                if not date or amount is None:
                    continue
                if date < since:
                    done = True
                    continue
                rid = f"receipt:{r.get('id')}"
                if known is None or rid not in known:
                    new_on_page += 1
                out.append({"id": rid, "source": "winkel", "date": date, "total": round(float(amount), 2)})
            if done or len(receipts) < page_size or (known is not None and not new_on_page):
                break
        return out
