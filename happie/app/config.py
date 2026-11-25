"""Paths, entity and notification IDs, refresh intervals and the app options."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATIC_DIR = Path(__file__).parent / "static"
# The bundled HAppie integration, installed into HA's config folder (map: homeassistant_config)
INTEGRATION_SRC = Path(__file__).parent / "custom_components" / "happie"
HA_CONFIG_DIR = Path(os.environ.get("HA_CONFIG_DIR", "/homeassistant"))
INTEGRATION_NOTIFICATION = "happie_integration"
INGRESS_IP = "172.30.32.2"
# Home Assistant Core on the Supervisor network; the companion integration polls from there
CORE_IP = os.environ.get("HAPPIE_CORE_IP", "172.30.32.1")
INTEGRATION_HEADER = "X-HAppie-Integration"
INTEGRATION_TIMEOUT = 300  # seconds without a poll before the app sets the sensors itself again
ENTITIES_API = 1  # version of /api/entities, bump on incompatible changes
DELIVERY_SENSOR = "sensor.happie_volgende_bezorging"
DELIVERY_REFRESH = 300  # seconds
SYNC_BACKOFF_MAX = 900  # after failed syncs the wait doubles, up to this many seconds
# sync_interval: 0 = only manual, else SYNC_MIN..SYNC_MAX seconds. The schema in config.yaml can only say
# int(0,3600), so smaller values from the configuration page are raised to SYNC_MIN by sync_interval()
SYNC_MIN, SYNC_MAX = 15, 3600
OPTIONS_REFRESH = 300  # seconds between reads of the app configuration, for an interval changed there
LIST_SENSOR = "sensor.happie_lijst_items"
COST_SENSOR = "sensor.happie_geschatte_kosten"
BONUS_SENSOR = "sensor.happie_bonus_items"
LOGIN_NOTIFICATION = "happie_login"
BONUS_NOTIFICATION = "happie_bonus"
BONUS_CHECK_INTERVAL = 3 * 3600
FREQUENT_TTL = 6 * 3600
BONUS_TTL = 3600
INVENTORY_SENSOR = "sensor.happie_voorraad"
SPEND_WEEK_SENSOR = "sensor.happie_uitgaven_week"
SPEND_MONTH_SENSOR = "sensor.happie_uitgaven_maand"
BUDGET_SENSOR = "binary_sensor.happie_boven_budget"
BUDGET_NOTIFICATION = "happie_budget"
BUDGET_MONTH_NOTIFICATION = "happie_budget_maand"
SPENDING_REFRESH = 6 * 3600
ITEMS_HISTORY_DAYS = 365  # articles are fetched for purchases this far back
ITEMS_BATCH = 20  # purchases fetched per round (saved after each round)
ITEMS_RETRY = 6 * 3600  # wait this long before trying a purchase again that gave no articles
ORDER_LINES_TTL = 300  # open orders can still change; delivered ones are cached for good
DONE_STATES = ("DELIVERED", "COMPLETED")
CANCELLED_STATES = ("CANCELLED", "CANCELED")


def load_options() -> dict[str, Any]:
    defaults = {
        "todo_entity": "todo.boodschappen",
        "sync_interval": 60,
        "auto_match_products": False,
        "bonus_notifications": True,
        "notify_service": "",
        "week_budget": 0,
        "month_budget": 0,
        "log_level": "info",
    }
    try:
        with open(DATA_DIR / "options.json", encoding="utf-8") as fh:
            defaults.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return defaults


def sync_interval(options: dict[str, Any]) -> int:
    """The sync interval to use: 0 (only manual) or SYNC_MIN..SYNC_MAX seconds."""
    try:
        value = int(options.get("sync_interval", 60))
    except (TypeError, ValueError):
        return 60
    return 0 if value <= 0 else min(max(value, SYNC_MIN), SYNC_MAX)
