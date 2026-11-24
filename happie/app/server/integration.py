"""The bundled HAppie integration: installing it into HA, and handing the sensors over to it.

The app copies custom_components/happie into HA's config folder on every start (when it is
missing or different) and asks the user once to restart HA. After the restart HA finds the app
through Supervisor discovery and offers to set up the integration.

Without the integration the app creates its sensors with ha.set_state. Those states have no
unique_id, so users can't rename them or put them in an area, and they vanish when HA restarts.
When the integration polls /api/entities, the app stops writing them and the integration
creates real entities with the same entity IDs. If the integration stops polling, the app
takes over again after INTEGRATION_TIMEOUT.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import socket
import stat
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from config import (
    DATA_DIR,
    ENTITIES_API,
    HA_CONFIG_DIR,
    INTEGRATION_HEADER,
    INTEGRATION_NOTIFICATION,
    INTEGRATION_SRC,
    INTEGRATION_TIMEOUT,
)

_LOGGER = logging.getLogger("happie")
_STATE_FILE = "integration.json"


class IntegrationMixin:
    def _load_integration_state(self) -> None:
        """After a restart, give an integration that was active the full timeout to poll again."""
        try:
            active = json.loads((DATA_DIR / _STATE_FILE).read_text(encoding="utf-8")).get("active")
        except (OSError, ValueError):
            active = False
        self._integration_seen = time.time() if active else 0.0
        self._handed_over = bool(active)

    def _save_integration_state(self) -> None:
        try:
            (DATA_DIR / _STATE_FILE).write_text(json.dumps({"active": self._handed_over}), encoding="utf-8")
        except OSError as err:
            _LOGGER.debug("integration.json schrijven mislukt: %s", err)

    @property
    def integration_active(self) -> bool:
        return time.time() - self._integration_seen < INTEGRATION_TIMEOUT

    async def check_integration_handover(self) -> None:
        """Called after every sync: take the sensors back when the integration stopped polling."""
        if self._handed_over and not self.integration_active:
            _LOGGER.info("HAppie-integratie reageert niet meer; de app zet de sensoren weer zelf")
            self._handed_over = False
            self._save_integration_state()
            self._published.clear()  # publish everything again
            self._delivery_at = 0
            await self.publish_inventory_sensor()

    async def entities_api(self, request: web.Request) -> web.Response:
        version = request.headers.get(INTEGRATION_HEADER)
        if version:
            self._integration_seen = time.time()
            if not self._handed_over:
                _LOGGER.info("HAppie-integratie gevonden; die maakt nu de sensoren in Home Assistant")
                self._handed_over = True
                self._save_integration_state()
            if self._restart_pending and version == integration_version(INTEGRATION_SRC):
                self._restart_pending = False  # HA restarted and runs the installed version
                try:
                    await self.ha.dismiss(INTEGRATION_NOTIFICATION)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Melding sluiten mislukt: %s", err)
        return web.json_response({"api": ENTITIES_API, "entities": self.entities})

    async def install_integration(self) -> None:
        """Copy the bundled integration into HA's config folder and ask for a restart once."""
        if not self.ha or not HA_CONFIG_DIR.is_dir():
            return  # no access to HA's config folder (local development)
        dest = HA_CONFIG_DIR / "custom_components" / "happie"
        try:
            if _tree_hash(dest) == _tree_hash(INTEGRATION_SRC):
                return
            fresh = not dest.exists()
            _copy_tree(INTEGRATION_SRC, dest)
        except OSError as err:
            _LOGGER.warning("HAppie-integratie installeren mislukt: %s", err)
            return
        version = integration_version(INTEGRATION_SRC)
        _LOGGER.info("HAppie-integratie %s %s; herstart Home Assistant om hem te laden",
                     version, "geïnstalleerd" if fresh else "bijgewerkt")
        self._restart_pending = True
        await self.ha.notify(
            "HAppie: herstart Home Assistant",
            ("De HAppie-integratie is geïnstalleerd. " if fresh
             else f"De HAppie-integratie is bijgewerkt naar {version}. ")
            + "Herstart Home Assistant (Instellingen > Systeem > Herstarten) om hem te laden."
            + (" Daarna verschijnt HAppie onder Instellingen > Apparaten & diensten; klik daar op Toevoegen."
               if fresh else ""),
            INTEGRATION_NOTIFICATION,
        )

    async def announce_integration(self) -> None:
        """Let HA show 'HAppie discovered' under Integrations (Supervisor discovery)."""
        if not self.ha or os.environ.get("HA_URL"):
            return  # no real Supervisor (local development)
        port = int(os.environ.get("PORT", 8099))
        try:
            await self.ha.announce("happie", {"host": socket.gethostname(), "port": port})
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Discovery naar de Supervisor mislukt: %s", err)



def integration_version(path: Path) -> str | None:
    try:
        return json.loads((path / "manifest.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def _tree_hash(root: Path) -> str | None:
    if not root.is_dir():
        return None
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _copy_tree(src: Path, dest: Path) -> None:
    """Replace dest with src in one step, so HA never sees a half-copied integration."""
    tmp, old = dest.with_name(".happie.tmp"), dest.with_name(".happie.old")
    _rmtree(tmp)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("__pycache__"))
    _rmtree(old)
    if dest.exists():
        dest.rename(old)
    tmp.rename(dest)
    _rmtree(old)


def _rmtree(path: Path) -> None:
    def make_writable(func, p, _exc):  # read-only files or folders (copied along with their mode)
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        func(p)

    if path.exists():
        shutil.rmtree(path, onexc=make_writable)
