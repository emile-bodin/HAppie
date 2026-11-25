"""Settings page tests: sync interval, saved in the app configuration. Run: python tests/test_settings.py"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import config  # noqa: E402
from server.app import App  # noqa: E402
from server.settings import interval_label  # noqa: E402


class FakeHA:
    """Running under Supervisor: options go to /addons/self/options."""

    under_supervisor = True

    def __init__(self):
        self.saved = []

    async def set_app_options(self, options):
        self.saved.append(dict(options))


class FakeRequest:
    def __init__(self, body=None):
        self._body = body or {}

    async def json(self):
        return self._body


async def call(handler, body=None):
    resp = await handler(FakeRequest(body))
    return resp.status, json.loads(resp.body)


async def test_supervisor():
    app = App(None, config.load_options())
    ha = app.ha = FakeHA()

    status, data = await call(app.settings_api)
    assert status == 200 and data["sync_interval"] == 60 and not data["manual"] and data["saved_in_ha"], data

    status, data = await call(app.save_settings_api, {"sync_interval": 300})
    assert status == 200 and data["sync_interval"] == 300
    assert app.options["sync_interval"] == 300
    # Supervisor replaces all options: the full set is sent
    assert ha.saved[-1]["sync_interval"] == 300 and ha.saved[-1]["todo_entity"] == "todo.boodschappen", ha.saved
    assert app._sync_event.is_set()  # the sync loop picks the new interval up right away

    status, data = await call(app.save_settings_api, {"sync_interval": 0})
    assert status == 200 and app.options["sync_interval"] == 0
    assert (await call(app.settings_api))[1]["manual"]

    for bad in (5, 4000, -1, "abc", None):
        status, data = await call(app.save_settings_api, {"sync_interval": bad})
        assert status == 400 and "handmatig" in data["error"], (bad, data)
    assert app.options["sync_interval"] == 0 and len(ha.saved) == 2  # nothing saved for invalid values


async def test_local():
    app = App(None, config.load_options())  # no HA: local development
    status, data = await call(app.settings_api)
    assert not data["saved_in_ha"]
    status, _ = await call(app.save_settings_api, {"sync_interval": 120})
    assert status == 200
    saved = json.loads((config.DATA_DIR / "options.json").read_text(encoding="utf-8"))
    assert saved["sync_interval"] == 120
    assert config.load_options()["sync_interval"] == 120  # read back on the next start


def test_labels():
    assert interval_label(0) == "alleen handmatig"
    assert interval_label(45) == "45 s"
    assert interval_label(300) == "5 min"
    assert interval_label(3600) == "1 uur"


if __name__ == "__main__":
    asyncio.run(test_supervisor())
    asyncio.run(test_local())
    test_labels()
    print("all settings tests passed")
