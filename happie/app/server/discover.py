"""Search and discover: search, suggestions, frequent products, bonus, barcodes."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from aiohttp import web

from ah.errors import AHOrderModeError
from config import BONUS_NOTIFICATION, BONUS_TTL, DATA_DIR, FREQUENT_TTL

_LOGGER = logging.getLogger("happie")


class DiscoverMixin:
    async def get_frequent(self, refresh: bool = False) -> list[dict[str, Any]]:
        if refresh or self._frequent is None or time.time() - self._frequent_at > FREQUENT_TTL:
            self._frequent = await self.ah.frequent_products()
            self._frequent_at = time.time()
        return self._frequent

    async def get_bonus(self, refresh: bool = False) -> dict[str, Any]:
        if refresh or self._bonus is None or time.time() - self._bonus_at > BONUS_TTL:
            self._bonus = await self.ah.bonus_for_you()
            self._bonus_at = time.time()
        return self._bonus

    async def check_bonus_notifications(self) -> None:
        """Notify (once per offer) when something on the list or a frequent buy is in the bonus."""
        candidates: dict[int, tuple[dict[str, Any], str]] = {}
        for i in self.sync.last_items or []:
            p = self._product_cache.get(i.product_id) if i.product_id else None
            if p and p.get("is_bonus") and not i.checked:
                candidates[p["id"]] = (p, "op je lijst")
        try:
            for p in (await self.get_frequent())[:25]:
                if p.get("is_bonus") and p.get("id") not in candidates:
                    candidates[p["id"]] = (p, f"koop je vaak ({p.get('times')}× in {p.get('orders')} bestellingen)")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Vaak gekocht ophalen mislukt: %s", err)

        path = DATA_DIR / "notified_bonus.json"
        try:
            notified: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            notified = {}
        current = {f"{pid}:{p.get('bonus') or ''}": (p, why) for pid, (p, why) in candidates.items()}
        new = [(p, why) for key, (p, why) in current.items() if key not in notified]
        # forget offers that ended, so they notify again next time they come back
        notified = {k: v for k, v in notified.items() if k in current}
        for key in current:
            notified.setdefault(key, time.strftime("%Y-%m-%d"))
        path.write_text(json.dumps(notified), encoding="utf-8")
        if not new:
            return
        lines = [f"- **{p['title']}**: {p.get('bonus') or 'in de bonus'} · {why}" for p, why in new[:15]]
        if len(new) > 15:
            lines.append(f"- … en nog {len(new) - 15}")
        _LOGGER.info("Bonusmelding voor %d producten", len(new))
        await self.ha.notify(
            "AH-bonus voor jou",
            "Nieuw in de bonus:\n" + "\n".join(lines),
            BONUS_NOTIFICATION,
            self.options.get("notify_service", ""),
        )

    async def search(self, request: web.Request) -> web.Response:
        q = request.query.get("q", "").strip()
        if not q:
            return web.json_response({"products": []})
        products = await self.ah.search(q)
        for p in products:
            if p.get("id"):
                self._product_cache[int(p["id"])] = p
        return web.json_response({"products": products})

    async def suggestions(self, request: web.Request) -> web.Response:
        try:
            items = await self.ah.get_list()
        except AHOrderModeError:
            items = []
        on_list = {i.product_id for i in items if i.product_id}
        products = await self.ah.suggestions([pid for pid in on_list], limit=16)
        products = [p for p in products if p.get("id") not in on_list][:12]
        for p in products:
            if p.get("id"):
                self._product_cache[int(p["id"])] = p
        return web.json_response({"products": products})

    async def frequent(self, request: web.Request) -> web.Response:
        products = await self.get_frequent(bool(request.query.get("refresh")))
        on_list = await self._on_list_ids()
        return web.json_response({"products": [{**p, "on_list": p.get("id") in on_list} for p in products]})

    async def bonus(self, request: web.Request) -> web.Response:
        data = await self.get_bonus(bool(request.query.get("refresh")))
        on_list = await self._on_list_ids()
        mark = lambda ps: [{**p, "on_list": p.get("id") in on_list} for p in ps]  # noqa: E731
        return web.json_response({"personal": mark(data["personal"]), "previously_bought": mark(data["previously_bought"])})

    async def barcode(self, request: web.Request) -> web.Response:
        product = await self.ah.product_by_gtin(request.match_info["gtin"])
        if product and product.get("id"):
            self._product_cache[int(product["id"])] = product
        return web.json_response({"product": product})
