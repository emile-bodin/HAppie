"""Two-way sync between the AH shopping list and a Home Assistant to-do list.

Uses a three-way merge: the snapshot of the last successful sync tells us
which side changed (added, removed, ticked off) since then.
Items are matched on their normalized name.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from ah import AHClient, AHOrderModeError, ListItem, normalize
from ha.client import HAClient, TodoItem

_LOGGER = logging.getLogger(__name__)


def backoff_delay(interval: float, failures: int, cap: float) -> float:
    """Seconds until the next sync: the interval, doubled per failure in a row, at most `cap`."""
    if failures <= 0:
        return interval
    return max(interval, min(interval * 2 ** min(failures, 16), cap))


def sync_wait(interval: float, failures: int, cap: float, heartbeat: float) -> tuple[float, bool]:
    """How long the sync loop waits, and whether a timeout means "sync now".

    interval 0 is "only manual": the loop still wakes every `heartbeat` seconds to refresh the
    delivery, spending and sensors, but only a change or "Nu synchroniseren" runs a sync.
    """
    if interval <= 0:
        return heartbeat, False
    return backoff_delay(interval, failures, cap), True


class SyncEngine:
    def __init__(
        self, ah: AHClient, ha: HAClient | None, state_file: str, auto_match: bool = False
    ) -> None:
        self.ah = ah
        self.ha = ha
        self.auto_match = auto_match
        self._state_file = state_file
        self.lock = asyncio.Lock()
        self.last_sync: float | None = None
        self.last_error: str | None = None
        self.last_exc: Exception | None = None
        self.order_mode = False
        self.failures = 0  # failed syncs in a row
        self.warnings: list[str] = []
        self.ha_available: bool | None = None
        self.last_items: list[ListItem] | None = None
        state = self._load()
        # key -> {"checked": bool}; None means "never synced"
        self.snapshot: dict[str, dict[str, Any]] | None = state.get("snapshot")
        # AH product id -> HA key (when we auto-matched a free text item to a product)
        self.aliases: dict[str, str] = state.get("aliases", {})
        # keys we tried to remove from AH but that are still there
        self.tombstones: list[str] = state.get("tombstones", [])

    # -------------------------------------------------------------- state io
    def _load(self) -> dict[str, Any]:
        try:
            with open(self._state_file, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        tmp = self._state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"snapshot": self.snapshot, "aliases": self.aliases, "tombstones": self.tombstones}, fh
            )
        os.replace(tmp, self._state_file)

    def reset(self) -> None:
        self.snapshot = None
        self.aliases = {}
        self.tombstones = []
        self._save()

    # ------------------------------------------------------------- helpers
    def ah_key(self, item: ListItem) -> str:
        if item.product_id and str(item.product_id) in self.aliases:
            return self.aliases[str(item.product_id)]
        return item.key

    async def ah_index(self) -> dict[str, ListItem]:
        out: dict[str, ListItem] = {}
        for item in await self.ah.get_list():
            out.setdefault(self.ah_key(item), item)
        return out

    async def _add_to_ah(self, summary: str, checked: bool) -> None:
        if self.auto_match:
            try:
                results = [p for p in await self.ah.search(summary, size=5) if p.get("orderable", True)]
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Zoeken naar '%s' mislukt: %s", summary, err)
                results = []
            if results:
                product = results[0]
                _LOGGER.info("'%s' gekoppeld aan AH-product '%s'", summary, product["title"])
                self.aliases[str(product["id"])] = normalize(summary)
                await self.ah.add_item(product["title"], product["id"], 1, checked)
                return
        await self.ah.add_item(summary, None, 1, checked)

    # ---------------------------------------------------------------- sync
    async def sync(self) -> None:
        async with self.lock:
            try:
                await self._sync()
                self.last_error = None
                self.last_exc = None
                self.order_mode = False
                self.failures = 0
            except AHOrderModeError:
                # AH locks the list while an order is reopened; pause, change nothing
                self.order_mode = True
                self.last_error = None
                self.last_exc = None
                self.failures = 0
            except Exception as err:
                self.last_error = str(err)
                self.last_exc = err
                self.failures += 1
                raise
            finally:
                self.last_sync = time.time()

    async def _sync(self) -> None:
        if not self.ah.logged_in:
            return
        if self.ha is None:
            return
        ah = await self.ah_index()
        self.last_items = list(ah.values())
        try:
            ha_list = await self.ha.get_items()
            self.ha_available = True
        except Exception:
            self.ha_available = False
            raise
        ha: dict[str, TodoItem] = {}
        ha_dupes: list[TodoItem] = []
        for item in ha_list:
            k = normalize(item.summary)
            if k in ha:
                ha_dupes.append(item)
            else:
                ha[k] = item

        snap = self.snapshot
        tomb = set(self.tombstones)
        new_snap: dict[str, dict[str, Any]] = {}
        removed_from_ah: list[str] = []

        ah_remove: list[ListItem] = []
        ha_remove: list[TodoItem] = []

        for key in set(ah) | set(ha) | set(snap or {}):
            a = ah.get(key)
            h = ha.get(key)
            s = (snap or {}).get(key)

            if key in tomb:
                if a is not None and h is None:
                    # removal from AH didn't stick; don't resurrect it in HA
                    continue
                # gone from AH after all, or re-added in HA: back to normal
                tomb.discard(key)

            if a and h:
                state = a.checked
                if a.checked != h.completed:
                    if s is None or a.checked != s["checked"]:
                        await self.ha.set_completed(h, a.checked)
                    else:
                        await self.ah.set_checked(a, h.completed)
                        state = h.completed
                new_snap[key] = {"checked": state}
            elif a:
                if snap is not None and s is not None:
                    _LOGGER.info("'%s' verwijderd in HA -> verwijderen bij AH", a.name)
                    ah_remove.append(a)
                    removed_from_ah.append(key)
                else:
                    _LOGGER.info("'%s' nieuw bij AH -> toevoegen in HA", a.name)
                    await self.ha.add_item(a.name, a.checked)
                    new_snap[key] = {"checked": a.checked}
            elif h:
                if snap is not None and s is not None:
                    _LOGGER.info("'%s' verwijderd bij AH -> verwijderen in HA", h.summary)
                    ha_remove.append(h)
                else:
                    _LOGGER.info("'%s' nieuw in HA -> toevoegen bij AH", h.summary)
                    await self._add_to_ah(h.summary, h.completed)
                    new_snap[key] = {"checked": h.completed}

        await self.ah.remove_items(ah_remove)
        await self.ha.remove_items(ha_remove)

        self.warnings = []
        if removed_from_ah:
            # verify AH actually removed them (the remove call is reverse engineered)
            still = await self.ah_index()
            failed = [k for k in removed_from_ah if k in still]
            if failed:
                tomb.update(failed)
        if tomb:
            self.warnings.append(
                "Deze items konden niet bij AH verwijderd worden; haal ze weg in de AH-app: "
                + ", ".join(sorted(tomb))
            )
        if ha_dupes:
            self.warnings.append(
                "Dubbele items in Home Assistant: " + ", ".join(sorted({d.summary for d in ha_dupes}))
            )

        # forget aliases for products that are no longer on the list
        live_pids = {str(i.product_id) for i in ah.values() if i.product_id}
        self.aliases = {pid: k for pid, k in self.aliases.items() if pid in live_pids or k in new_snap}

        self.snapshot = new_snap
        self.tombstones = sorted(tomb)
        self._save()
