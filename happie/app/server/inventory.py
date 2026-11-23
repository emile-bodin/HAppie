"""Inventory (voorraad): API for the panel and the inventory sensor."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import web

from config import INVENTORY_SENSOR
from services.inventory import clean_gtin, product_key

_LOGGER = logging.getLogger("happie")


class InventoryMixin:
    def _inv_item(self, item: dict[str, Any] | None) -> dict[str, Any] | None:
        if item and item.get("product_id"):
            p = self._product_cache.get(int(item["product_id"]))
            if p:
                item = {**item, "price": p.get("price"), "is_bonus": p.get("is_bonus"), "bonus": p.get("bonus"),
                        "image": item.get("image") or p.get("image")}
        return item

    async def publish_inventory_sensor(self) -> None:
        if not self.ha:
            return
        s = self.inventory.summary()
        try:
            await self._set_state_if_changed(
                INVENTORY_SENSOR,
                s["products"],
                {
                    "friendly_name": "Voorraad",
                    "icon": "mdi:fridge-outline",
                    "unit_of_measurement": "producten",
                    "items": s["items"],
                    "total_units": s["total_units"],
                    "empty": s["empty"],
                },
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Sensor %s bijwerken mislukt: %s", INVENTORY_SENSOR, err)

    async def _inv_changed(self, result: Any) -> web.Response:
        await self.publish_inventory_sensor()
        return web.json_response({"ok": True, "item": self._inv_item(result) if isinstance(result, dict) else None})

    async def inv_list(self, request: web.Request) -> web.Response:
        items = self.inventory.list()
        await self._ensure_products([int(i["product_id"]) for i in items if i.get("product_id")])
        return web.json_response({"items": [self._inv_item(i) for i in items], "summary": self.inventory.summary()})

    async def inv_adjust(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.inv_lock:
            try:
                result = self.inventory.adjust(
                    int(body.get("delta", 1)), key=body.get("key"), product=body.get("product"),
                    name=body.get("name"), gtin=body.get("gtin"),
                )
            except KeyError as err:
                raise web.HTTPNotFound(text=json.dumps({"error": str(err.args[0])}), content_type="application/json")
        return await self._inv_changed(result)

    async def inv_set(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.inv_lock:
            try:
                result = self.inventory.set(body["key"], int(body.get("quantity") or 0))
            except KeyError as err:
                raise web.HTTPNotFound(text=json.dumps({"error": str(err.args[0])}), content_type="application/json")
        return await self._inv_changed(result)

    async def inv_remove(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.inv_lock:
            self.inventory.remove(body["key"])
        return await self._inv_changed(None)

    async def inv_scan(self, request: web.Request) -> web.Response:
        gtin = clean_gtin(request.match_info["gtin"])
        local = self.inventory.find_by_gtin(gtin)
        if local:
            return web.json_response({"gtin": gtin, "item": self._inv_item(local), "product": None, "source": "local"})
        product = await self.ah.product_by_gtin(gtin)
        if product and product.get("id"):
            self._product_cache[int(product["id"])] = product
            existing = self.inventory.get(product_key(product))
            if existing:  # known product, new barcode: remember it
                async with self.inv_lock:
                    self.inventory.link_gtin(gtin, existing["key"])
            return web.json_response({"gtin": gtin, "item": self._inv_item(existing), "product": product, "source": "ah"})
        return web.json_response({"gtin": gtin, "item": None, "product": None, "source": None})

    async def inv_link(self, request: web.Request) -> web.Response:
        """Link an unknown barcode to a name or product and add it (quantity delta, default +1)."""
        body = await request.json()
        if not (body.get("name") or body.get("product")) or not clean_gtin(body.get("gtin")):
            raise web.HTTPBadRequest(text='{"error":"Barcode en naam of product nodig"}', content_type="application/json")
        async with self.inv_lock:
            result = self.inventory.adjust(
                int(body.get("delta", 1)), product=body.get("product"), name=body.get("name"), gtin=body["gtin"]
            )
        return await self._inv_changed(result)

    async def inv_orders(self, request: web.Request) -> web.Response:
        orders = await self.ah.delivered_orders(5)
        lines = await asyncio.gather(*(self.ah.order_lines(o["orderId"]) for o in orders))
        return web.json_response(
            {
                "orders": [
                    {
                        "order_id": o["orderId"],
                        "date": o.get("deliveryDate"),
                        "products": len(ls),
                        "items": sum(l["quantity"] for l in ls),
                        "unpacked": o["orderId"] in self.inventory.unpacked_orders,
                    }
                    for o, ls in zip(orders, lines)
                ]
            }
        )

    async def inv_unpack(self, request: web.Request) -> web.Response:
        body = await request.json()
        order_id = body["order_id"]
        lines = await self.ah.order_lines(order_id)
        if not lines:
            raise web.HTTPNotFound(text='{"error":"Geen producten gevonden in deze bestelling"}', content_type="application/json")
        for line in lines:
            if line["product"].get("id"):
                self._product_cache.setdefault(int(line["product"]["id"]), line["product"])
        async with self.inv_lock:
            result = self.inventory.unpack(order_id, lines)
        await self.publish_inventory_sensor()
        return web.json_response({"ok": True, **result})

    async def inv_to_list(self, request: web.Request) -> web.Response:
        body = await request.json()
        item = self.inventory.get(body["key"])
        if not item:
            raise web.HTTPNotFound(text='{"error":"Onbekend voorraaditem"}', content_type="application/json")
        await self.add_to_list(item["name"], item.get("product_id"), 1)
        return web.json_response({"ok": True})
