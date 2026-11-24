"""HAppie: real entities for the sensors of the HAppie app (Albert Heijn shopping list).

The HAppie app installs this integration into custom_components itself; nobody installs it by hand.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

from .coordinator import HAppieCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type HAppieConfigEntry = ConfigEntry[HAppieCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HAppieConfigEntry) -> bool:
    coordinator = HAppieCoordinator(hass, entry)
    coordinator.version = str((await async_get_integration(hass, DOMAIN)).version or "0")
    # The first poll also tells the app to stop creating these sensors itself
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HAppieConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
