"""The shopping list: API for the panel and the list sensors."""
from __future__ import annotations

import json
from typing import Any

from aiohttp import web

from ah.errors import AHOrderModeError
from ah.models import normalize
from ah.pricing import line_for
from config import BONUS_SENSOR, COST_SENSOR, LIST_SENSOR


class ListMixin:
    async def list_totals(self, items) -> tuple[float, float, int, list[str]]:
        """(estimated cost incl. bonus, bonus saving, items without price, bonus items) of the open items."""
        await self._ensure_products([i.product_id for i in items if i.product_id])
        cost, saving, unknown, bonus = 0.0, 0.0, 0, []
        for i in items:
            if i.checked:
                continue
            p = self._product_cache.get(i.product_id) if i.product_id else None
            line = line_for(p, i.quantity)
            if line:
                cost += line["total"]
                saving += line["saving"]
            else:
                unknown += 1
            if p and p.get("is_bonus"):
                bonus.append(f"{i.name} ({p.get('bonus') or 'bonus'})")
        return round(cost, 2), round(saving, 2), unknown, bonus

    async def publish_list_sensors(self, items) -> None:
        open_items = [i for i in items if not i.checked]
        cost, saving, unknown, bonus = await self.list_totals(items)
        self._list_cost = cost
        await self._set_state_if_changed(
            LIST_SENSOR,
            len(open_items),
            {
                "friendly_name": "AH boodschappenlijst",
                "icon": "mdi:cart-outline",
                "unit_of_measurement": "items",
                "state_class": "measurement",
                "items": [f"{i.quantity}× {i.name}" if i.quantity > 1 else i.name for i in open_items],
                "checked": len(items) - len(open_items),
                "total": len(items),
            },
        )
        await self._set_state_if_changed(
            COST_SENSOR,
            round(cost, 2),
            {
                "friendly_name": "AH geschatte kosten",
                "icon": "mdi:currency-eur",
                "unit_of_measurement": "EUR",
                "device_class": "monetary",
                "items_without_price": unknown,
                "bonus_saving": round(saving, 2),
            },
        )
        await self._set_state_if_changed(
            BONUS_SENSOR,
            len(bonus),
            {
                "friendly_name": "AH bonusitems op lijst",
                "icon": "mdi:sale",
                "unit_of_measurement": "items",
                "products": bonus,
            },
        )

    async def _enrich(self, items: list[dict[str, Any]]) -> None:
        await self._ensure_products([i["product_id"] for i in items if i["product_id"]])
        for i in items:
            i["product"] = self._product_cache.get(i["product_id"]) if i["product_id"] else None
            i["line"] = line_for(i["product"], i["quantity"])

    async def get_list(self, request: web.Request) -> web.Response:
        items = [i.to_json() for i in await self.ah.get_list()]
        await self._enrich(items)
        items.sort(key=lambda i: (i["checked"], (i["product"] or {}).get("category") or "~", i["name"].casefold()))
        return web.json_response({"items": items})

    async def _find(self, key: str):
        for item in await self.ah.get_list():
            if item.key == key:
                return item
        raise web.HTTPNotFound(text=json.dumps({"error": "Item niet gevonden"}), content_type="application/json")

    async def add_to_list(self, name: str, product_id: Any = None, quantity: int = 1) -> None:
        name = (name or "").strip()
        if not name:
            raise web.HTTPBadRequest(text='{"error":"Naam ontbreekt"}', content_type="application/json")
        async with self.sync.lock:
            existing = {i.key: i for i in await self.ah.get_list()}.get(normalize(name))
            if existing and not existing.checked:
                await self.ah.set_quantity(existing, existing.quantity + quantity)
            else:
                await self.ah.add_item(name, int(product_id) if product_id else None, quantity)
        await self.run_sync_now()

    async def add(self, request: web.Request) -> web.Response:
        body = await request.json()
        await self.add_to_list(body.get("name"), body.get("product_id"), max(1, int(body.get("quantity") or 1)))
        return web.json_response({"ok": True})

    async def check(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.sync.lock:
            item = await self._find(body["key"])
            await self.ah.set_checked(item, bool(body.get("checked")))
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def quantity(self, request: web.Request) -> web.Response:
        body = await request.json()
        qty = int(body.get("quantity") or 0)
        async with self.sync.lock:
            item = await self._find(body["key"])
            if qty <= 0:
                await self.ah.remove_items([item])
            else:
                await self.ah.set_quantity(item, qty)
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def remove(self, request: web.Request) -> web.Response:
        body = await request.json()
        keys = set(body.get("keys") or [body.get("key")])
        async with self.sync.lock:
            items = [i for i in await self.ah.get_list() if i.key in keys]
            await self.ah.remove_items(items)
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def _on_list_ids(self) -> set[int]:
        try:
            return {i.product_id for i in await self.ah.get_list() if i.product_id}
        except AHOrderModeError:
            return set()
