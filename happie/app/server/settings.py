"""Settings page of the panel: the sync interval, saved in the app's own configuration."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from aiohttp import web

from config import DATA_DIR, OPTIONS_REFRESH, SYNC_MAX, SYNC_MIN, sync_interval

_LOGGER = logging.getLogger("happie")

LIVE_OPTIONS = ("sync_interval",)  # options that apply without a restart; the rest is read at startup


class SettingsMixin:
    @property
    def _saved_in_ha(self) -> bool:
        return bool(self.ha and getattr(self.ha, "under_supervisor", False))

    async def _fetch_saved_options(self) -> dict[str, Any]:
        """All options as saved now. Under Supervisor they may have changed on the configuration page since startup."""
        if not self._saved_in_ha:
            return dict(self.options)
        return {**self.options, **await self.ha.get_app_options()}

    def _apply_live_options(self, saved: dict[str, Any]) -> None:
        """Take over the options that apply without a restart; wake the sync loop for a new interval."""
        changed = {k: saved[k] for k in LIVE_OPTIONS if k in saved and saved[k] != self.options.get(k)}
        if changed:
            self.options.update(changed)
            self.reschedule_sync()

    async def refresh_live_options(self, max_age: float = OPTIONS_REFRESH) -> None:
        """Pick up a sync interval changed on the configuration page; at most every `max_age` seconds."""
        if not self._saved_in_ha or time.time() - self._options_at < max_age:
            return
        self._options_at = time.time()
        try:
            self._apply_live_options(await self._fetch_saved_options())
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("App-configuratie lezen mislukt: %s", err)

    async def settings_api(self, request: web.Request) -> web.Response:
        await self.refresh_live_options(max_age=0)
        interval = sync_interval(self.options)
        return web.json_response({
            "sync_interval": interval,
            "manual": interval == 0,
            "saved_in_ha": self._saved_in_ha,
            "min": SYNC_MIN,
            "max": SYNC_MAX,
        })

    async def save_settings_api(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except ValueError:
            body = None
        value = body.get("sync_interval") if isinstance(body, dict) else None
        # whole seconds only: no bools, no fractions
        interval = value if isinstance(value, int) and not isinstance(value, bool) else -1
        if interval != 0 and not SYNC_MIN <= interval <= SYNC_MAX:
            return web.json_response(
                {"error": f"Kies een interval van {SYNC_MIN} tot {SYNC_MAX} seconden, of alleen handmatig."}, status=400
            )
        await self.save_options({"sync_interval": interval})
        _LOGGER.info("Sync-interval ingesteld op %s", f"{interval} s" if interval else "alleen handmatig")
        self.reschedule_sync()  # the new interval applies right away, without a sync of its own
        return web.json_response({"ok": True, "sync_interval": interval})

    async def save_options(self, changes: dict[str, Any]) -> None:
        """Change some options. Under Supervisor: in the app's configuration in HA. Locally: <DATA_DIR>/options.json.

        Supervisor replaces all options, so the rest is taken from what is saved there now, not from what was
        loaded at startup: otherwise a change on the configuration page without a restart would be undone.
        """
        try:
            saved = await self._fetch_saved_options()
        except Exception as err:  # noqa: BLE001
            # Supervisor busy (e.g. a backup): still save, with the options as loaded at startup
            _LOGGER.warning("App-configuratie lezen mislukt, opslaan met de opties van bij het starten: %s", err)
            saved = dict(self.options)
        options = {**saved, **changes}
        if self._saved_in_ha:
            await self.ha.set_app_options(options)
        else:
            path = DATA_DIR / "options.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(options, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        self.options.update(changes)
