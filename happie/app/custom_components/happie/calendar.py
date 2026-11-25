"""HAppie calendar: the next AH delivery as an event, built from the delivery sensor the app publishes."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HAppieConfigEntry
from .entity import HAppieEntity

try:  # HA 2026.11+: a calendar entity reads initial_color from its description
    from homeassistant.components.calendar import CalendarEntityDescription
except ImportError:  # older HA
    from homeassistant.helpers.entity import EntityDescription as CalendarEntityDescription

DELIVERY_SENSOR = "sensor.happie_volgende_bezorging"
CALENDAR = CalendarEntityDescription(key="bezorging", icon="mdi:truck-delivery")


async def async_setup_entry(
    hass: HomeAssistant, entry: HAppieConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([HAppieDeliveryCalendar(entry.runtime_data, CALENDAR, Platform.CALENDAR)])


def delivery_event(state: str | None, attrs: dict[str, Any]) -> CalendarEvent | None:
    """The delivery window as an event; a whole-day event while only the date is known."""
    start = dt_util.parse_datetime(state) if state else None
    if start is None:
        return None
    end = dt_util.parse_datetime(attrs["end"]) if attrs.get("end") else None
    details = [
        f"Tijdvak {attrs['window']}" if attrs.get("window") else None,
        f"Verwacht {attrs['eta_window']}" if attrs.get("eta_window") else None,
        attrs.get("eta_message"),
        f"{attrs['item_count']} artikelen" if attrs.get("item_count") else None,
        f"€ {float(attrs['total']):.2f}".replace(".", ",") if attrs.get("total") is not None else None,
        _closing(attrs.get("closing_time")),
    ]
    description = "\n".join(d for d in details if d) or None
    uid = f"happie-bezorging-{attrs.get('date') or start.date().isoformat()}"
    if end is None or not attrs.get("window"):
        day: date = date.fromisoformat(attrs["date"]) if attrs.get("date") else dt_util.as_local(start).date()
        return CalendarEvent(start=day, end=day + timedelta(days=1), summary="AH-bezorging",
                             description=description, uid=uid)
    return CalendarEvent(start=start, end=end, summary="AH-bezorging", description=description, uid=uid)


def _closing(value: str | None) -> str | None:
    closing = dt_util.parse_datetime(value) if value else None
    if closing is None:
        return f"Wijzigen kan tot {value}" if value else None
    return f"Wijzigen kan tot {dt_util.as_local(closing).strftime('%d-%m %H:%M')}"


class HAppieDeliveryCalendar(HAppieEntity, CalendarEntity):
    """Only the upcoming delivery: the app does not keep past delivery windows."""

    @property
    def _app_entity(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DELIVERY_SENSOR)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return None  # the delivery details are in the event description and on the sensor

    @property
    def event(self) -> CalendarEvent | None:
        e = self._app_entity
        return delivery_event(self._raw_state, (e or {}).get("attributes") or {}) if e else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        ev = self.event
        if ev is None:
            return []
        start, end = ev.start_datetime_local, ev.end_datetime_local
        return [ev] if start < end_date and end > start_date else []
