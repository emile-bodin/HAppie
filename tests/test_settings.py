"""Settings page tests: sync interval, saved in the app configuration. Run: python tests/test_settings.py"""
import asyncio
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import config  # noqa: E402
from server.app import App  # noqa: E402


class FakeHA:
    """Running under Supervisor: options go to /addons/self/options."""

    under_supervisor = True

    def __init__(self, options):
        self.options = dict(options)  # what the configuration page shows
        self.saved = []

    async def get_app_options(self):
        if self.options is None:
            raise RuntimeError("Supervisor bezet")
        return dict(self.options)

    async def set_app_options(self, options):
        self.saved.append(dict(options))
        self.options = dict(options)


class FakeRequest:
    def __init__(self, body=None):
        self._body = {} if body is None else body

    async def json(self):
        return self._body


async def call(handler, body=None):
    resp = await handler(FakeRequest(body))
    return resp.status, json.loads(resp.body)


async def test_supervisor():
    app = App(None, config.load_options())
    ha = app.ha = FakeHA(app.options)

    status, data = await call(app.settings_api)
    assert status == 200 and data["sync_interval"] == 60 and not data["manual"] and data["saved_in_ha"], data

    status, data = await call(app.save_settings_api, {"sync_interval": 300})
    assert status == 200 and data["sync_interval"] == 300
    assert app.options["sync_interval"] == 300
    # Supervisor replaces all options: the full set is sent
    assert ha.saved[-1]["sync_interval"] == 300 and ha.saved[-1]["todo_entity"] == "todo.boodschappen", ha.saved
    # the sync loop picks the new interval up right away, but that is no reason to sync
    assert app._sync_event.is_set() and not app._sync_requested
    app._sync_event.clear()

    # changed on the configuration page without a restart: kept when the panel saves, and the
    # interval from there shows up in the panel
    ha.options.update({"week_budget": 150, "sync_interval": 600})
    status, data = await call(app.settings_api)
    assert data["sync_interval"] == 600 and app.options["sync_interval"] == 600 and app._sync_event.is_set()
    assert app.options["week_budget"] == 0  # other options only apply after a restart
    await call(app.save_settings_api, {"sync_interval": 300})
    assert ha.saved[-1]["week_budget"] == 150 and ha.saved[-1]["sync_interval"] == 300, ha.saved

    status, data = await call(app.save_settings_api, {"sync_interval": 0})
    assert status == 200 and app.options["sync_interval"] == 0
    assert (await call(app.settings_api))[1]["manual"]

    for bad in (5, 4000, -1, "abc", None, True, 60.5, "60"):
        status, data = await call(app.save_settings_api, {"sync_interval": bad})
        assert status == 400 and "handmatig" in data["error"], (bad, data)
    for body in ([], "60"):  # not an object
        status, data = await call(app.save_settings_api, body)
        assert status == 400, (body, data)
    assert app.options["sync_interval"] == 0 and len(ha.saved) == 3  # nothing saved for invalid values

    # the schema allows 1..14 on the configuration page; the app uses 15 then
    ha.options["sync_interval"] = 5
    status, data = await call(app.settings_api)
    assert data["sync_interval"] == 15 and not data["manual"], data

    # the sync loop also picks up a change on the configuration page, at most every OPTIONS_REFRESH seconds
    ha.options["sync_interval"] = 900
    app._options_at = time.time()
    await app.refresh_live_options()
    assert app.options["sync_interval"] == 5  # read just now: not again yet
    app._options_at -= config.OPTIONS_REFRESH
    await app.refresh_live_options()
    assert app.options["sync_interval"] == 900

    # Supervisor can't be read (busy): still saved, with the options from startup
    ha.options = None
    status, _ = await call(app.save_settings_api, {"sync_interval": 120})
    assert status == 200 and ha.saved[-1]["sync_interval"] == 120 and app.options["sync_interval"] == 120
    status, data = await call(app.settings_api)  # and the menu still opens
    assert status == 200 and data["sync_interval"] == 120


async def test_local():
    app = App(None, config.load_options())  # no HA: local development
    status, data = await call(app.settings_api)
    assert not data["saved_in_ha"]
    status, _ = await call(app.save_settings_api, {"sync_interval": 120})
    assert status == 200
    saved = json.loads((config.DATA_DIR / "options.json").read_text(encoding="utf-8"))
    assert saved["sync_interval"] == 120
    assert config.load_options()["sync_interval"] == 120  # read back on the next start


def test_sync_interval():
    assert config.sync_interval({"sync_interval": 0}) == 0
    assert config.sync_interval({"sync_interval": 1}) == 15
    assert config.sync_interval({"sync_interval": 45}) == 45
    assert config.sync_interval({"sync_interval": 99999}) == 3600
    assert config.sync_interval({"sync_interval": "x"}) == 60


async def test_sync_loop_wakeups():
    """A new interval only reschedules; a requested sync still runs."""
    app = App(None, {**config.load_options(), "sync_interval": 0})
    runs = []

    async def fake_sync():
        runs.append(1)

    async def nothing():
        pass

    app._run_sync = fake_sync
    app._debounce = 0
    app.after_sync = nothing
    loop = asyncio.create_task(app.sync_loop())
    await asyncio.sleep(0)
    app.reschedule_sync()
    await asyncio.sleep(0.05)
    assert runs == [] and not app._sync_event.is_set()
    app.request_sync()
    await asyncio.sleep(0.05)
    assert runs == [1]
    loop.cancel()


if __name__ == "__main__":
    asyncio.run(test_supervisor())
    asyncio.run(test_local())
    test_sync_interval()
    asyncio.run(test_sync_loop_wakeups())
    print("all settings tests passed")
