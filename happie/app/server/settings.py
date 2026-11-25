"""Settings page of the panel: the sync interval, saved in the app's own configuration."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from aiohttp import web

from config import DATA_DIR

_LOGGER = logging.getLogger("happie")

SYNC_MIN, SYNC_MAX = 15, 3600  # same range as the schema in config.yaml; 0 = only manual


def interval_label(seconds: int) -> str:
    if seconds <= 0:
        return "alleen handmatig"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} uur"
    if seconds % 60 == 0:
        return f"{seconds // 60} min"
    return f"{seconds} s"


class SettingsMixin:
    @property
    def _saved_in_ha(self) -> bool:
        return bool(self.ha and getattr(self.ha, "under_supervisor", False))

    async def settings_api(self, request: web.Request) -> web.Response:
        interval = int(self.options["sync_interval"])
        return web.json_response({
            "sync_interval": interval,
            "manual": interval == 0,
            "saved_in_ha": self._saved_in_ha,
            "min": SYNC_MIN,
            "max": SYNC_MAX,
        })

    async def save_settings_api(self, request: web.Request) -> web.Response:
        body = await request.json()
        try:
            interval = int(body.get("sync_interval"))
        except (TypeError, ValueError):
            interval = -1
        if interval != 0 and not SYNC_MIN <= interval <= SYNC_MAX:
            return web.json_response(
                {"error": f"Kies een interval van {SYNC_MIN} tot {SYNC_MAX} seconden, of alleen handmatig."}, status=400
            )
        await self.save_options({**self.options, "sync_interval": interval})
        _LOGGER.info("Sync-interval ingesteld op %s", interval_label(interval))
        self._sync_event.set()  # wake the sync loop so the new interval applies right away
        return web.json_response({"ok": True, "sync_interval": interval})

    async def save_options(self, options: dict[str, Any]) -> None:
        """Under Supervisor: the app's configuration in HA. Locally: <DATA_DIR>/options.json."""
        if self._saved_in_ha:
            await self.ha.set_app_options(options)
        else:
            path = DATA_DIR / "options.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(options, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        self.options.update(options)
