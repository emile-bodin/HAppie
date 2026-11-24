"""Polls the HAppie app for the values of its sensors."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_VERSION, CONF_URL, DOMAIN, ENTITIES_PATH, INTEGRATION_HEADER, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HAppieError(Exception):
    """The app could not be reached or gave an unexpected answer."""


async def fetch_entities(hass: HomeAssistant, url: str, version: str = "") -> dict[str, dict[str, Any]]:
    """GET <url>/api/entities -> {entity_id: {"state": ..., "attributes": {...}}}.

    With a version, the header also tells the app to hand its sensors over to this integration.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url.rstrip("/") + ENTITIES_PATH,
            headers={INTEGRATION_HEADER: version} if version else None,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                raise HAppieError(f"HTTP {resp.status}")
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        raise HAppieError(str(err) or type(err).__name__) from err
    if not isinstance(data, dict) or not isinstance(data.get("entities"), dict):
        raise HAppieError("unexpected response")
    if data.get("api", 0) > API_VERSION:
        _LOGGER.warning("The HAppie app is newer than this integration; update the integration")
    return data["entities"]


class HAppieCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.url: str = entry.data[CONF_URL]
        self.version = ""  # set in async_setup_entry, from manifest.json

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await fetch_entities(self.hass, self.url, self.version)
        except HAppieError as err:
            raise UpdateFailed(f"HAppie app not reachable at {self.url}: {err}") from err
