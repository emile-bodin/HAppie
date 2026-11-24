"""The app object: shared state, the background sync loop and sensor helpers."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import aiohttp

from ah.client import AHClient
from ah.errors import AHError
from config import BONUS_CHECK_INTERVAL, DATA_DIR, DELIVERY_REFRESH, SPENDING_REFRESH
from ha.client import HAClient
from server.account import AccountMixin
from server.discover import DiscoverMixin
from server.integration import IntegrationMixin
from server.inventory import InventoryMixin
from server.orders import OrdersMixin as AppOrdersMixin
from server.shopping_list import ListMixin
from server.spending import SpendingMixin
from services.inventory import Inventory
from services.spending import SpendingStore
from services.sync import SyncEngine

_LOGGER = logging.getLogger("happie")


class App(AccountMixin, ListMixin, DiscoverMixin, AppOrdersMixin, SpendingMixin, InventoryMixin, IntegrationMixin):
    """State shared by all parts of the app; the API handlers live in the mixins."""

    def __init__(self, session: aiohttp.ClientSession, options: dict[str, Any]) -> None:
        self.options = options
        self.ah = AHClient(session, str(DATA_DIR / "tokens.json"))
        self.ha = HAClient(session, options["todo_entity"]) if os.environ.get("SUPERVISOR_TOKEN") else None
        self.sync = SyncEngine(
            self.ah, self.ha, str(DATA_DIR / "sync_state.json"), options["auto_match_products"]
        )
        self._product_cache: dict[int, dict[str, Any]] = {}
        self._member: dict[str, Any] | None = None
        self._delivery: dict[str, Any] | None = None
        self._delivery_at: float = 0
        self._frequent: list[dict[str, Any]] | None = None
        self._frequent_at: float = 0
        self._bonus: dict[str, Any] | None = None
        self._bonus_at: float = 0
        self._bonus_checked_at: float = 0
        self._login_notified = False
        self._published: dict[str, Any] = {}
        self.entities: dict[str, dict[str, Any]] = {}  # everything published, served to the integration
        self._restart_pending = False  # integration copied, HA not restarted yet
        self._load_integration_state()
        self._sync_event = asyncio.Event()
        self.inventory = Inventory(str(DATA_DIR / "inventory.json"))
        self.inv_lock = asyncio.Lock()
        self.spending = SpendingStore(str(DATA_DIR / "spending.json"))
        self._spending_lock = asyncio.Lock()
        self._list_cost: float | None = None
        self._order_lines: dict[str, tuple[float, bool, list[dict[str, Any]]]] = {}
        self._spending_stale = False

    # -------------------------------------------------------- background
    def request_sync(self) -> None:
        self._sync_event.set()

    async def sync_loop(self) -> None:
        interval = int(self.options["sync_interval"])
        while True:
            try:
                await asyncio.wait_for(self._sync_event.wait(), timeout=interval)
                await asyncio.sleep(1.5)  # debounce bursts of changes
            except asyncio.TimeoutError:
                pass
            self._sync_event.clear()
            try:
                await self.sync.sync()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sync mislukt: %s", err)
            if self.ah.logged_in and time.time() - self._delivery_at > DELIVERY_REFRESH:
                try:
                    await self.refresh_delivery()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Bezorging ophalen mislukt: %s", err)
            if self.ah.logged_in and (self._spending_stale or time.time() - self.spending.updated_at > SPENDING_REFRESH):
                try:
                    await self.refresh_spending()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Uitgaven ophalen mislukt: %s", err)
            try:
                await self.after_sync()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sensoren/meldingen bijwerken mislukt: %s", err)

    # ------------------------------------------------ sensors + notifications
    async def after_sync(self) -> None:
        if not self.ha:
            return
        await self.check_integration_handover()
        await self.check_login_notification()
        if self.sync.last_exc is None and not self.sync.order_mode and self.sync.last_items is not None:
            await self.publish_list_sensors(self.sync.last_items)
        if self.spending.updated_at:
            await self.publish_spending_sensors()
            if self._list_cost is not None:
                await self.check_budget_notification()
        if (
            self.options.get("bonus_notifications")
            and self.ah.logged_in
            and self.sync.last_exc is None
            and time.time() - self._bonus_checked_at > BONUS_CHECK_INTERVAL
        ):
            self._bonus_checked_at = time.time()
            await self.check_bonus_notifications()

    async def _ensure_products(self, ids: list[int]) -> None:
        missing = [i for i in ids if i and i not in self._product_cache]
        for start in range(0, len(missing), 50):
            try:
                for p in await self.ah.products_by_id(missing[start:start + 50]):
                    if p.get("id"):
                        self._product_cache[int(p["id"])] = p
            except AHError as err:
                _LOGGER.debug("Productinfo ophalen mislukt: %s", err)

    async def _set_state_if_changed(self, entity_id: str, state: Any, attrs: dict[str, Any]) -> None:
        self.entities[entity_id] = {"state": str(state), "attributes": attrs}
        if self.integration_active:
            return  # the HAppie integration owns the entities now
        key = json.dumps([state, attrs], sort_keys=True, default=str)
        if self._published.get(entity_id) == key:
            return
        await self.ha.set_state(entity_id, str(state), attrs)
        self._published[entity_id] = key
