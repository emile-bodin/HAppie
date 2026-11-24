"""HAppie sensors: shopping list, estimated cost, bonus items, next delivery, inventory, spending."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HAppieConfigEntry
from .entity import HAppieEntity, setup_dynamic_entities

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="lijst_items",
        icon="mdi:cart-outline",
        native_unit_of_measurement="items",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="geschatte_kosten",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="bonus_items",
        icon="mdi:sale",
        native_unit_of_measurement="items",
    ),
    SensorEntityDescription(
        key="volgende_bezorging",
        icon="mdi:truck-delivery",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="voorraad",
        icon="mdi:fridge-outline",
        native_unit_of_measurement="producten",
    ),
    SensorEntityDescription(
        key="uitgaven_week",
        icon="mdi:cash-register",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="uitgaven_maand",
        icon="mdi:cash-register",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HAppieConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entry.async_on_unload(
        setup_dynamic_entities(
            coordinator, SENSORS, Platform.SENSOR,
            lambda d: HAppieSensor(coordinator, d, Platform.SENSOR), async_add_entities,
        )
    )


class HAppieSensor(HAppieEntity, SensorEntity):
    entity_description: SensorEntityDescription

    @property
    def native_value(self) -> float | int | datetime | None:
        raw = self._raw_state
        if raw is None:
            return None
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(raw)
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if self.entity_description.device_class == SensorDeviceClass.MONETARY else int(value)

    @property
    def last_reset(self) -> datetime | None:
        if self.entity_description.state_class != SensorStateClass.TOTAL:
            return None
        e = self._app_entity
        reset = e and (e.get("attributes") or {}).get("last_reset")
        return dt_util.parse_datetime(reset) if reset else None
