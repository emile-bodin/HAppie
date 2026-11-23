"""AH order endpoints: summaries, items and the next delivery."""
from __future__ import annotations

import time
from typing import Any

from ah.errors import AHError, AHOrderModeError
from ah.models import parse_eta, parse_product


class OrdersMixin:
    async def order_summaries(self) -> list[dict[str, Any]]:
        data = await self._raw("GET", "/mobile-services/order/v1/summaries", params={"sortBy": "DEFAULT"})
        if isinstance(data, dict):
            data = data.get("orders") or data.get("content") or []
        return data or []

    async def delivered_orders(self, n: int = 8) -> list[dict[str, Any]]:
        """Most recent delivered online orders (summaries), newest first."""
        return sorted(
            (o for o in await self.order_summaries() if str(o.get("state", "")).upper() in ("DELIVERED", "COMPLETED")),
            key=lambda o: o.get("deliveryDate") or "",
            reverse=True,
        )[:n]

    async def order_details(self, order_id: Any) -> dict[str, Any]:
        try:
            return await self._raw("GET", f"/mobile-services/order/v1/{order_id}/details-grouped-by-taxonomy") or {}
        except AHOrderModeError:
            raise
        except AHError as err:
            _LOGGER.debug("Bestelling %s ophalen mislukt: %s", order_id, err)
            return {}

    @staticmethod
    def raw_order_lines(details: dict[str, Any]) -> list[dict[str, Any]]:
        return [l for g in details.get("groupedProductsInTaxonomy") or [] for l in g.get("orderedProducts") or []]

    @staticmethod
    def line_quantity(line: dict[str, Any]) -> int:
        return int(line.get("allocatedQuantity") or line.get("quantity") or 0)

    async def order_lines(self, order_id: Any) -> list[dict[str, Any]]:
        """Products in an order: [{product (parsed), quantity}]."""
        details = await self.order_details(order_id)
        return [
            {"product": parse_product(l.get("product") or {}), "quantity": self.line_quantity(l),
             "ordered": int(l.get("amount") or l.get("quantity") or 0)}
            for l in self.raw_order_lines(details)
            if (l.get("product") or {}).get("webshopId")
        ]

    async def get_next_delivery(self) -> dict[str, Any] | None:
        """Next upcoming online order (delivery or pickup), or None."""
        summaries = await self.order_summaries()
        today = time.strftime("%Y-%m-%d")
        upcoming = [
            o for o in summaries
            if (o.get("deliveryDate") or "") >= today
            and str(o.get("state", "")).upper() not in ("DELIVERED", "CANCELLED", "CANCELED", "COMPLETED")
        ]
        if not upcoming:
            return None
        upcoming.sort(key=lambda o: o.get("deliveryDate") or "")
        order = upcoming[0]
        result: dict[str, Any] = {
            "order_id": order.get("orderId"),
            "state": order.get("state"),
            "date": order.get("deliveryDate"),
            "closing_time": order.get("closingTime"),
            "start": None, "end": None, "start_utc": None, "end_utc": None,
            "type": None, "total": None, "item_count": None,
            **parse_eta(order.get("trackTraceInfo")),
        }
        # the active order has the time window, total and products
        try:
            active = await self._raw(
                "GET", "/mobile-services/order/v1/summaries/active", params={"sortBy": "DEFAULT"}
            )
        except AHError:
            active = None
        if isinstance(active, dict) and active.get("id") == result["order_id"]:
            info = active.get("deliveryInformation") or {}
            products = active.get("orderedProducts") or []
            result.update(
                {
                    "type": active.get("shoppingType"),
                    "start": info.get("deliveryStartTime"),
                    "end": info.get("deliveryEndTime"),
                    "start_utc": info.get("deliveryUtcStartTime"),
                    "end_utc": info.get("deliveryUtcEndTime"),
                    "total": (active.get("totalPrice") or {}).get("priceTotalPayable"),
                    "item_count": sum(int(p.get("allocatedQuantity") or p.get("quantity") or 0) for p in products),
                    "product_count": len(products),
                }
            )
        else:
            # confirmed orders aren't "active"; the order details have the time window and products
            details = await self.order_details(result["order_id"])
            period = details.get("deliveryTimePeriod") or {}
            lines = self.raw_order_lines(details)
            if period:
                result.update(
                    {
                        "type": "PICKUP" if str(details.get("deliveryType", "")).upper() == "PICKUP" else "DELIVERY",
                        "start": (period.get("startDateTime") or "")[11:16] or None,
                        "end": (period.get("endDateTime") or "")[11:16] or None,
                        "start_utc": period.get("startTimeUtc"),
                        "end_utc": period.get("endTimeUtc"),
                    }
                )
            if lines:
                result["item_count"] = sum(self.line_quantity(l) for l in lines)
                result["product_count"] = len(lines)
        return result
