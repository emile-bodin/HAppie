"""Orders and the next delivery."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

from aiohttp import web

from ah.pricing import line_for
from config import CANCELLED_STATES, DELIVERY_SENSOR, DONE_STATES, ORDER_LINES_TTL

_LOGGER = logging.getLogger("happie")


class OrdersMixin:
    @staticmethod
    def _local_iso(day: str | None, hhmm: str | None) -> str | None:
        """'2026-11-23' + '20:40' -> '2026-11-23T20:40:00+01:00' (local time zone)."""
        if not day or not hhmm:
            return None
        try:
            return datetime.fromisoformat(f"{day}T{hhmm}").astimezone().isoformat()
        except ValueError:
            return None

    async def refresh_delivery(self) -> dict[str, Any] | None:
        previous = (self._delivery or {}).get("order_id")
        self._delivery = await self.ah.get_next_delivery()
        if previous and previous != (self._delivery or {}).get("order_id"):
            self._spending_stale = True  # the previous order was delivered: fetch spending again
        self._delivery_at = time.time()
        if self.ha:
            d = self._delivery
            attrs: dict[str, Any] = {
                "friendly_name": "AH volgende bezorging",
                "icon": "mdi:truck-delivery",
                "device_class": "timestamp",
            }
            if d:
                attrs.update(
                    {
                        "date": d.get("date"),
                        "window": f"{d['start']}–{d['end']}" if d.get("start") else None,
                        "end": d.get("end_utc"),
                        "closing_time": d.get("closing_time"),
                        "order_state": d.get("state"),
                        "order_type": d.get("type"),
                        "total": d.get("total"),
                        "item_count": d.get("item_count"),
                        "eta_window": f"{d['eta_start']}–{d['eta_end']}" if d.get("eta_start") else None,
                        "eta_start": self._local_iso(d.get("date"), d.get("eta_start")),
                        "eta_end": self._local_iso(d.get("date"), d.get("eta_end")),
                        "eta_message": d.get("eta_message"),
                        "min_order": d.get("min_order"),
                    }
                )
                try:
                    lines = await self.get_order_lines(d["order_id"])
                    attrs["products"] = [
                        f"{l['quantity']}× {l['product'].get('title')}" if l["quantity"] > 1 else l["product"].get("title")
                        for l in lines[:100]
                    ]
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Producten van bestelling ophalen mislukt: %s", err)
            state = (d or {}).get("start_utc") or ((d or {}).get("date") and f"{d['date']}T00:00:00+01:00") or "unknown"
            try:
                await self._set_state_if_changed(DELIVERY_SENSOR, state, attrs)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sensor %s bijwerken mislukt: %s", DELIVERY_SENSOR, err)
        return self._delivery

    # ------------------------------------------------------------ orders
    async def get_order_lines(self, order_id: Any, done: bool = False, refresh: bool = False) -> list[dict[str, Any]]:
        key = str(order_id)
        cached = self._order_lines.get(key)
        if cached and not refresh and (cached[1] or time.time() - cached[0] < ORDER_LINES_TTL):
            return cached[2]
        lines = await self.ah.order_lines(order_id)
        self._order_lines[key] = (time.time(), done, lines)
        for line in lines:
            if line["product"].get("id"):
                self._product_cache.setdefault(int(line["product"]["id"]), line["product"])
        return lines

    def _order_row(self, o: dict[str, Any]) -> dict[str, Any]:
        price = o.get("orderTotalPrice") or {}
        state = str(o.get("state", "")).upper()
        return {
            "order_id": o.get("orderId"),
            "date": o.get("deliveryDate"),
            "state": state,
            "done": state in DONE_STATES,
            "total": self.ah.order_total(o),
            "discount": price.get("priceDiscount"),
            "unpacked": str(o.get("orderId")) in {str(x) for x in self.inventory.unpacked_orders},
        }

    async def orders(self, request: web.Request) -> web.Response:
        """Upcoming orders (soonest first) and the last delivered ones (newest first)."""
        summaries = await self.ah.order_summaries()
        today = date.today().isoformat()
        upcoming = sorted(
            (o for o in summaries
             if (o.get("deliveryDate") or "") >= today
             and str(o.get("state", "")).upper() not in DONE_STATES + CANCELLED_STATES),
            key=lambda o: o.get("deliveryDate") or "",
        )[:4]
        done = sorted(
            (o for o in summaries if str(o.get("state", "")).upper() in DONE_STATES),
            key=lambda o: o.get("deliveryDate") or "", reverse=True,
        )[:6]
        return web.json_response({"orders": [self._order_row(o) for o in upcoming + done]})

    async def order(self, request: web.Request) -> web.Response:
        order_id = request.match_info["order_id"]
        done = request.query.get("done") == "1"
        lines = await self.get_order_lines(order_id, done, bool(request.query.get("refresh")))
        on_list = {i.product_id: i.quantity for i in (self.sync.last_items or []) if i.product_id and not i.checked}
        out = []
        for l in lines:
            p = l["product"]
            out.append({
                "product": p,
                "quantity": l["quantity"],
                "ordered": l.get("ordered") or l["quantity"],
                "line": line_for(p, l["quantity"]),
                "on_list": on_list.get(p.get("id")),
            })
        return web.json_response({
            "order_id": order_id,
            "lines": out,
            "items": sum(l["quantity"] for l in out),
            "unpacked": str(order_id) in {str(x) for x in self.inventory.unpacked_orders},
        })

    async def delivery(self, request: web.Request) -> web.Response:
        if request.query.get("refresh") or self.delivery_stale():
            await self.refresh_delivery()
        return web.json_response({"delivery": self._delivery, "sensor": DELIVERY_SENSOR if self.ha else None})
