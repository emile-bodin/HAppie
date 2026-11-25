"""Bundled HAppie integration: installing it and handing the sensors over. Run: python tests/test_integration.py"""
import asyncio
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["HA_CONFIG_DIR"] = tempfile.mkdtemp()

import config  # noqa: E402
from server.app import App  # noqa: E402
from ah import ListItem  # noqa: E402


class FakeHA:
    def __init__(self):
        self.writes, self.notes, self.dismissed = [], [], []

    async def set_state(self, entity_id, state, attrs):
        self.writes.append(entity_id)

    async def notify(self, title, message, notification_id, service=""):
        self.notes.append((notification_id, message))

    async def dismiss(self, notification_id):
        self.dismissed.append(notification_id)


class FakeRequest:
    def __init__(self, version):
        self.headers = {config.INTEGRATION_HEADER: version} if version else {}


async def entities(app, version="0.0.1"):
    resp = await app.entities_api(FakeRequest(version))
    return json.loads(resp.body)


async def run():
    app = App(None, config.load_options())
    ha = app.ha = FakeHA()
    items = [ListItem("Brood", 1, False, None), ListItem("Melk", 2, False, None)]

    # --- 1. without the integration the app writes the sensors itself
    await app.publish_list_sensors(items)
    assert config.LIST_SENSOR in ha.writes
    assert not app.integration_active

    # --- 2. a poll without the header (e.g. the panel) does not hand over
    data = await entities(app, version=None)
    assert data["api"] == config.ENTITIES_API
    assert data["entities"][config.LIST_SENSOR]["state"] == "2"
    assert not app.integration_active

    # --- 3. the integration polls: the app stops writing but keeps the values up to date
    await entities(app)
    assert app.integration_active
    ha.writes.clear()
    await app.publish_list_sensors(items + [ListItem("Kaas", 1, False, None)])
    await app.publish_inventory_sensor()
    assert ha.writes == [], ha.writes
    data = await entities(app)
    assert data["entities"][config.LIST_SENSOR]["state"] == "3"
    assert data["entities"][config.LIST_SENSOR]["attributes"]["items"] == ["Brood", "2× Melk", "Kaas"]
    assert config.INVENTORY_SENSOR in data["entities"]

    # --- 4. remembered across a restart, so the app doesn't write before the first poll
    app2 = App(None, config.load_options())
    app2.ha = FakeHA()
    assert app2.integration_active
    await app2.publish_list_sensors(items)
    assert app2.ha.writes == []

    # --- 5. integration gone: after the timeout the app takes the sensors back and publishes everything
    app._integration_seen = time.time() - config.INTEGRATION_TIMEOUT - 1
    assert not app.integration_active
    await app.check_integration_handover()
    assert config.INVENTORY_SENSOR in ha.writes
    await app.publish_list_sensors(items)
    assert config.LIST_SENSOR in ha.writes
    app3 = App(None, config.load_options())
    assert not app3.integration_active

    # --- 6. install: copied once into custom_components, with one restart notification
    from server.integration import integration_version

    app = App(None, config.load_options())
    ha = app.ha = FakeHA()
    dest = config.HA_CONFIG_DIR / "custom_components" / "happie"
    await app.install_integration()
    assert (dest / "manifest.json").is_file() and (dest / "translations" / "nl.json").is_file()
    assert [n[0] for n in ha.notes] == [config.INTEGRATION_NOTIFICATION]
    assert "geïnstalleerd" in ha.notes[0][1]
    await app.install_integration()  # unchanged: nothing to do
    assert len(ha.notes) == 1

    # --- 7. an older copy is replaced ("bijgewerkt"), leftovers of the copy are cleaned up
    (dest / "sensor.py").write_text("# old", encoding="utf-8")
    await app.install_integration()
    assert "bijgewerkt" in ha.notes[-1][1]
    assert (dest / "sensor.py").read_text(encoding="utf-8") != "# old"
    assert sorted(p.name for p in dest.parent.iterdir()) == ["happie"], list(dest.parent.iterdir())

    # --- 8. the notification goes away once HA runs the new version
    await entities(app, version="0.0.0-old")
    assert ha.dismissed == []
    await entities(app, version=integration_version(config.INTEGRATION_SRC))
    assert ha.dismissed == [config.INTEGRATION_NOTIFICATION]

    # --- 9. no config folder mapped (local development): nothing happens
    config.HA_CONFIG_DIR.rename(str(config.HA_CONFIG_DIR) + "-gone")
    app2 = App(None, config.load_options())
    app2.ha = FakeHA()
    await app2.install_integration()
    assert app2.ha.notes == []

    print("all integration tests passed")


def test_versions_match():
    """The app ships the integration: its manifest version must be the app version.

    HA shows the manifest version under the integration, and the app only copies a changed integration
    (and closes the restart notification) when that version changes.
    """
    import re
    from server.integration import integration_version
    with open(os.path.join(os.path.dirname(__file__), "..", "happie", "config.yaml"), encoding="utf-8") as fh:
        app_version = re.search(r'^version:\s*"?([^"\s]+)"?', fh.read(), re.M).group(1)
    manifest = integration_version(config.INTEGRATION_SRC)
    assert manifest == app_version, (
        f"custom_components/happie/manifest.json heeft versie {manifest}, de app {app_version}: maak ze gelijk")


test_versions_match()
asyncio.run(run())
