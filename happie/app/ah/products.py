"""AH product endpoints: search, suggestions, frequent products, bonus, barcodes."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from ah.errors import AHError
from ah.models import parse_product


class ProductsMixin:
    async def search(self, query: str, size: int = 24) -> list[dict[str, Any]]:
        data = await self._raw(
            "GET",
            "/mobile-services/product/search/v2",
            params={"query": query, "page": 0, "size": size, "sortOn": "RELEVANCE"},
            auth="any",
        )
        return [parse_product(p) for p in (data or {}).get("products", [])]

    async def get_member(self) -> dict[str, Any]:
        """Account name of the logged in member."""
        data = await self._raw(
            "POST", "/graphql", json_body={"query": "query { member { id name { first last } } }"}
        )
        member = ((data or {}).get("data") or {}).get("member") or {}
        name = member.get("name") or {}
        return {
            "id": member.get("id"),
            "first_name": name.get("first"),
            "name": " ".join(p for p in (name.get("first"), name.get("last")) if p),
        }

    async def suggestions(self, basket_product_ids: list[int], limit: int = 12) -> list[dict[str, Any]]:
        """Personal 'Suggesties voor jou' (the app's don't-forget lane for the list).

        AH bases them on purchase history and adapts them to what's already on the list.
        """
        data = await self._raw(
            "POST",
            "/mobile-services/v2/recommendations/dontforgetlane",
            json_body={
                "positiveCmOnly": True,
                "offset": 0,
                "usecaseId": "app_mylist",
                "basketItems": [
                    {"quantity": 1, "position": n, "productId": pid}
                    for n, pid in enumerate(basket_product_ids, start=1)
                ],
                "limit": limit,
            },
        )
        return [parse_product(p) for p in (data or {}).get("productCards", [])]

    async def frequent_products(self, max_orders: int = 8, limit: int = 40) -> list[dict[str, Any]]:
        """Products you buy most often, aggregated from your last delivered online orders."""
        delivered = await self.delivered_orders(max_orders)
        orders = await asyncio.gather(*(self.order_details(o["orderId"]) for o in delivered))
        stats: dict[int, dict[str, Any]] = {}
        for order in orders:
            for line in self.raw_order_lines(order):
                p = line.get("product") or {}
                pid = p.get("webshopId")
                if not pid:
                    continue
                s = stats.setdefault(pid, {"times": 0, "quantity": 0, "last": "", "raw": p})
                s["times"] += 1
                s["quantity"] += self.line_quantity(line)
                s["last"] = max(s["last"], order.get("deliveryDate") or "")
        ranked = sorted(stats.items(), key=lambda kv: (-kv[1]["times"], -kv[1]["quantity"]))[:limit]
        # refresh price/bonus info, order history has stale prices
        fresh = {}
        try:
            fresh = {p["id"]: p for p in await self.products_by_id([pid for pid, _ in ranked])}
        except AHError:
            pass
        out = []
        for pid, s in ranked:
            product = fresh.get(pid) or parse_product(s["raw"])
            product.update({"times": s["times"], "orders": len(delivered), "last_bought": s["last"]})
            out.append(product)
        return out

    @staticmethod
    def _bonus_entries(data: Any) -> list[dict[str, Any]]:
        out = []
        for entry in (data or {}).get("bonusGroupOrProducts") or []:
            if entry.get("product"):
                out.append(parse_product(entry["product"]))
            elif entry.get("bonusGroup"):
                group = entry["bonusGroup"]
                for p in group.get("products") or []:
                    item = parse_product(p)
                    item["bonus"] = item.get("bonus") or group.get("discountDescription") or group.get("bonusMechanism")
                    item["is_bonus"] = True
                    out.append(item)
        return out

    async def bonus_for_you(self) -> dict[str, list[dict[str, Any]]]:
        """Personal bonus offers + previously bought products that are in the bonus now."""
        today = time.strftime("%Y-%m-%d")
        params = {"application": "AHWEBSHOP", "date": today}
        personal = await self._raw("GET", "/mobile-services/bonuspage/v2/section/personal", params=params)
        previous = await self._raw("GET", "/mobile-services/bonuspage/v2/section/previously-bought", params=params)
        return {"personal": self._bonus_entries(personal), "previously_bought": self._bonus_entries(previous)}

    async def product_by_gtin(self, gtin: str) -> dict[str, Any] | None:
        """Look up a product by its barcode (EAN/GTIN)."""
        gtin = re.sub(r"\D", "", gtin or "")
        if not gtin:
            return None
        try:
            data = await self._raw("GET", f"/mobile-services/product/search/v1/gtin/{gtin}", auth="any")
        except AHError as err:
            if str(err).startswith("404"):
                return None
            raise
        return parse_product(data) if isinstance(data, dict) and data.get("webshopId") else None

    async def products_by_id(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        params = [("ids", str(i)) for i in ids] + [("sortOn", "INPUT_PRODUCT_IDS")]
        data = await self._raw(
            "GET", "/mobile-services/product/search/v2/products", params=params, auth="any"
        )
        if isinstance(data, dict):
            data = data.get("products", [])
        return [parse_product(p) for p in data or []]
