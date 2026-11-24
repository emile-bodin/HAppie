"""Constants for the HAppie integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "happie"
CONF_URL = "url"

# Installed from a local folder the app's hostname is local-happie; from a repository it is
# <hash>-happie, which Supervisor discovery fills in automatically.
DEFAULT_URL = "http://local-happie:8099"

SCAN_INTERVAL = timedelta(seconds=30)
ENTITIES_PATH = "/api/entities"
INTEGRATION_HEADER = "X-HAppie-Integration"
API_VERSION = 1
