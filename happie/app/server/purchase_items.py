"""Articles of purchases for the spending page: fetched in the background, one purchase at a time."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import date, timedelta
from typing import Any

from aiohttp import web

from ah.errors import AHAuthError, AHError
from config import ITEMS_BATCH, ITEMS_HISTORY_DAYS, ITEMS_RETRY
from services.purchase_items import allocate_receipt, overview, receipt_key
from services.spending import weekday_average

_LOGGER = logging.getLogger("happie")


class PurchaseItemsMixin:
    @staticmethod
    def _items_since(today: date | None = None) -> str:
        return ((today or date.today()) - timedelta(days=ITEMS_HISTORY_DAYS)).isoformat()

    def _items_pending(self) -> list[dict[str, Any]]:
        now = time.time()
        return [p for p in self.items.pending(self.spending.list(), self._items_since())
                if now - self._items_failed.get(p["id"], 0) > ITEMS_RETRY]

    @property
    def items_running(self) -> bool:
        return self._items_task is not None and not self._items_task.done()

    def start_items_refresh(self) -> None:
        """Fetch the articles of purchases that don't have them yet, in the background."""
        if self.ah.logged_in and not self.items_running and self._items_pending():
            self._items_task = asyncio.create_task(self._refresh_items())

    async def _refresh_items(self) -> None:
        fetched = 0
        try:
            while todo := self._items_pending()[:ITEMS_BATCH]:
                results = await asyncio.gather(*(self._background_lines(p) for p in todo), return_exceptions=True)
                for p, r in zip(todo, results):
                    if isinstance(r, AHAuthError):
                        raise r
                    if isinstance(r, BaseException):
                        _LOGGER.debug("Artikelen van %s ophalen mislukt: %s", p["id"], r)
                        self._items_failed[p["id"]] = time.time()
                        continue
                    self.items.lines[p["id"]] = r
                    fetched += 1
                self.items.prune(self.spending.ids())
                self.items.save()
        except AHAuthError as err:
            _LOGGER.debug("Artikelen ophalen gestopt: %s", err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Artikelen van aankopen ophalen mislukt: %s", err)
        if fetched:
            _LOGGER.info("Artikelen van %d aankopen opgehaald", fetched)

    @staticmethod
    async def _shared(inflight: dict[str, asyncio.Task], key: str, make) -> Any:
        """Run make() once per key at a time: a second caller waits for the first one's result."""
        task = inflight.get(key)
        if task is None:
            task = inflight[key] = asyncio.ensure_future(make())

            def done(t: asyncio.Task) -> None:
                inflight.pop(key, None)
                if not t.cancelled():
                    t.exception()  # retrieved: no asyncio error in the log when every caller went away

            task.add_done_callback(done)
        return await asyncio.shield(task)  # a caller that goes away doesn't cancel it for the others

    async def _lines_for(self, purchase: dict[str, Any], sem: asyncio.Semaphore | None) -> list[dict[str, Any]]:
        """Lines of one purchase, fetched once even when the panel and the background task ask at the same time."""
        return await self._shared(self._items_inflight, purchase["id"], lambda: self._fetch_items(purchase, sem))

    async def _background_lines(self, purchase: dict[str, Any]) -> list[dict[str, Any]]:
        # a slot per purchase, taken before the fetch is registered: the panel then only ever waits for a
        # fetch that is running, never for one still queued behind the rest of the batch
        async with self._items_sem:
            return await self._lines_for(purchase, None)

    async def _fetch_items(self, purchase: dict[str, Any], sem: asyncio.Semaphore | None) -> list[dict[str, Any]]:
        """Lines of one purchase: [{key, name, qty, amount}]. Raises when AH returns nothing, so it's tried again later.

        `sem` limits the AH requests; None when the caller already holds a slot for the whole purchase.
        """
        kind, _, pid = purchase["id"].partition(":")
        sem = sem or contextlib.nullcontext()
        if kind == "order":
            async with sem:
                lines = await self.ah.order_lines(pid)
            out = [{"key": self.items.add_product(l["product"]), "name": l["product"].get("title") or "",
                    "qty": l["quantity"], "amount": None} for l in lines if l["quantity"] > 0]
        else:
            async with sem:
                receipt = await self.ah.receipt_details(pid)
            raw = [{"key": await self._receipt_line_key(l, sem), "name": l["name"], "qty": l["quantity"],
                    "amount": l["amount"], "deposit": l.get("deposit")} for l in receipt["lines"]]
            titles = [(self.items.products.get(l["key"]) or {}).get("title") for l in raw]
            out, discounts = allocate_receipt(raw, receipt["discounts"], titles)
            if out:
                self.items.discounts[purchase["id"]] = discounts
        if not out:
            raise AHError("geen artikelen gevonden")
        return out

    async def _receipt_line_key(self, line: dict[str, Any], sem: Any) -> str:
        """Product key of a receipt line, or a receipt key when no webshop product has its hqId."""
        hq = str(line["hq_id"]) if line.get("hq_id") else None
        if not hq:
            return receipt_key(None, line["name"])
        if hq not in self.items.hq:
            # receipts fetched at the same time often share products: look each hqId up only once
            await self._shared(self._hq_inflight, hq, lambda: self._lookup_hq(hq, line, sem))
        return self.items.hq[hq]["key"] or receipt_key(hq, line["name"])

    async def _lookup_hq(self, hq: str, line: dict[str, Any], sem: Any) -> None:
        async with sem:
            product, guess = await self.ah.product_by_hq_id(line["hq_id"], line["name"])
        self.items.hq[hq] = {"key": self.items.add_product(product) if product else None, "guess": guess}

    # ------------------------------------------------------------------ api
    async def spending_items_api(self, request: web.Request) -> web.Response:
        today = date.today()
        days = 91 if request.query.get("months") == "3" else 365
        self.start_items_refresh()
        purchases = self.spending.list()
        data = overview(self.items, purchases, (today - timedelta(days=days)).isoformat(), today)
        # order history has old prices: show today's price and bonus for the most bought products
        await self._ensure_products([int(r["product"]["id"]) for r in data["top"] if r["product"].get("id")])
        for r in data["top"]:
            fresh = self._product_cache.get(int(r["product"]["id"] or 0))
            if fresh:
                r["product"] = {**r["product"], **{k: fresh.get(k) for k in ("title", "image", "price", "is_bonus", "bonus")}}
        data.update({"weekday": weekday_average(purchases, today), "running": self.items_running})
        return web.json_response(data)

    async def spending_purchase_api(self, request: web.Request) -> web.Response:
        """Articles of one purchase, fetched now if the background task hasn't got to it yet."""
        pid = request.match_info["purchase_id"]
        purchase = self.spending.purchases.get(pid)
        if not purchase:
            return web.json_response({"error": "Aankoop niet gevonden"}, status=404)
        lines = self.items.lines.get(pid)
        if lines is None:
            lines = await self._lines_for(purchase, asyncio.Semaphore(3))  # its own slots: not behind the background
            self.items.lines[pid] = lines
            self.items.save()
        out = []
        for l in lines:
            product = self.items.products.get(l["key"]) or {}
            out.append({"name": product.get("title") or l["name"], "receipt_name": l["name"], "quantity": l["qty"],
                        "amount": l["amount"], "gross": l.get("gross"), "bonus": l.get("bonus") or 0,
                        "deposit": l.get("deposit") or 0, "category": self.items.category(l["key"]),
                        "product_id": product.get("id"), "image": product.get("image")})
        # on a receipt: the discounts that fit no line, and the statiegeld, as rows of their own
        other = [d for d in self.items.discounts.get(pid) or [] if not d.get("matched")]
        deposit = round(sum(l["deposit"] for l in out), 2)
        return web.json_response({"id": pid, "lines": out, "discounts": other, "deposit": deposit,
                                  "total": purchase.get("total")})

    async def spending_link_api(self, request: web.Request) -> web.Response:
        """Put an unrecognised receipt line in a category of your choice (empty category: undo)."""
        body = await request.json()
        key = str(body.get("key") or "")
        if not key.startswith("r:"):
            return web.json_response({"error": "Alleen niet-herkende bonregels kun je koppelen"}, status=400)
        self.items.link(key, str(body.get("category") or "").strip() or None)
        self.items.save()
        return web.json_response({"ok": True})
