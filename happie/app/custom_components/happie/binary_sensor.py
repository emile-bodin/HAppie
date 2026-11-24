"""HAppie binary sensor: over the week budget (only when the app has a week budget set)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HAppieConfigEntry
from .entity import HAppieEntity, setup_dynamic_entities

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="boven_budget",
        icon="mdi:wallet-outline",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HAppieConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entry.async_on_unload(
        setup_dynamic_entities(
            coordinator, BINARY_SENSORS, Platform.BINARY_SENSOR,
            lambda d: HAppieBinarySensor(coordinator, d, Platform.BINARY_SENSOR), async_add_entities,
        )
    )


class HAppieBinarySensor(HAppieEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        raw = self._raw_state
        return None if raw is None else raw == "on"
