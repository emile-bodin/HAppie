"""Shared base for HAppie entities: one per sensor the app publishes, same entity_id as before."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HAppieCoordinator

# Set by the app for its own set_state; on an entity they come from the description instead
_META_ATTRS = {"friendly_name", "icon", "unit_of_measurement", "device_class", "state_class", "last_reset"}


class HAppieEntity(CoordinatorEntity[HAppieCoordinator]):
    _attr_has_entity_name = True
    # Long lists: shown on the entity, kept out of the recorder database
    _unrecorded_attributes = frozenset({"items", "products"})

    def __init__(self, coordinator: HAppieCoordinator, description: EntityDescription, domain: str) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"happie_{description.key}"
        # Keep the entity IDs the app always used, so automations keep working
        self.entity_id = f"{domain}.happie_{description.key}"
        slug = _app_slug(coordinator.url)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="HAppie",
            manufacturer="HAppie",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"homeassistant://hassio/ingress/{slug}" if slug else None,
        )

    @property
    def _app_entity(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self.entity_id)

    @property
    def _raw_state(self) -> str | None:
        e = self._app_entity
        state = e and e.get("state")
        return None if state in (None, "", "unknown", "unavailable", "None") else str(state)

    @property
    def available(self) -> bool:
        return super().available and self._app_entity is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        e = self._app_entity
        if not e:
            return None
        return {k: v for k, v in (e.get("attributes") or {}).items() if k not in _META_ATTRS}


def _app_slug(url: str) -> str | None:
    """http://a1b2c3d4-happie:8099 -> a1b2c3d4_happie (the app's slug, for the panel link)."""
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    return host.replace("-", "_") if host.endswith("-happie") else None


def setup_dynamic_entities(
    coordinator: HAppieCoordinator,
    descriptions: Iterable[EntityDescription],
    domain: str,
    factory: Callable[[EntityDescription], Entity],
    async_add_entities: AddEntitiesCallback,
) -> Callable[[], None]:
    """Add an entity once the app publishes it (the budget sensor only exists with a week budget).

    Entities added earlier stay registered and show as unavailable while the app doesn't publish them.
    """
    hass = coordinator.hass
    registry = er.async_get(hass)
    added: set[str] = set()
    descriptions = list(descriptions)

    @callback
    def _add_new() -> None:
        data = coordinator.data or {}
        new = []
        for d in descriptions:
            entity_id = f"{domain}.happie_{d.key}"
            if d.key in added:
                continue
            known = registry.async_get_entity_id(domain, "happie", f"happie_{d.key}") is not None
            if entity_id not in data and not known:
                continue
            if not known and hass.states.get(entity_id) is not None:
                # A leftover state the app created with set_state: remove it, or the entity
                # registry would hand out happie_..._2 instead of the familiar entity ID
                hass.states.async_remove(entity_id)
            added.add(d.key)
            new.append(factory(d))
        if new:
            async_add_entities(new)

    _add_new()
    return coordinator.async_add_listener(_add_new)
