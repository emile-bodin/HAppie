"""Notification + sensor tests with fakes. Run: python tests/test_notifications.py"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import config  # noqa: E402
from server.app import App  # noqa: E402
from ah import AHAuthError, ListItem  # noqa: E402


class FakeHA:
    def __init__(self):
        self.notes, self.dismissed, self.states = [], [], {}

    async def notify(self, title, message, notification_id, service=""):
        self.notes.append((notification_id, title, message, service))

    async def dismiss(self, notification_id):
        self.dismissed.append(notification_id)

    async def set_state(self, entity_id, state, attrs):
        self.states[entity_id] = (state, attrs)


async def run():
    opts = config.load_options()
    app = App(None, opts)
    ha = app.ha = FakeHA()
    app.ah._refresh_token = "x"  # pretend logged in

    # --- 2. login expiry: notify once, dismiss when OK again
    app.sync.last_exc = AHAuthError("expired")
    await app.check_login_notification()
    await app.check_login_notification()
    assert [n[0] for n in ha.notes] == ["happie_login"], ha.notes
    app.sync.last_exc = None
    await app.check_login_notification()
    assert ha.dismissed == ["happie_login"]

    # --- 3. sensors
    app._product_cache = {
        1: {"id": 1, "title": "Pesto", "price": 2.19, "is_bonus": True, "bonus": "2 voor 3.99"},
        2: {"id": 2, "title": "Melk", "price": 1.29, "is_bonus": False},
    }
    items = [ListItem("Pesto", 2, False, 1), ListItem("Melk", 1, True, 2), ListItem("Brood", 1, False, None)]
    await app.publish_list_sensors(items)
    assert ha.states[config.LIST_SENSOR][0] == "2"
    assert ha.states[config.COST_SENSOR][0] == "3.99", ha.states[config.COST_SENSOR]  # 2 voor 3.99 applied
    assert ha.states[config.COST_SENSOR][1]["bonus_saving"] == 0.39
    assert ha.states[config.COST_SENSOR][1]["items_without_price"] == 1
    assert ha.states[config.BONUS_SENSOR][0] == "1"
    assert ha.states[config.BONUS_SENSOR][1]["products"] == ["Pesto (2 voor 3.99)"]

    # --- 6. bonus notifications: once per offer
    app.sync.last_items = items

    async def frequent(refresh=False):
        return [{"id": 3, "title": "Bananen", "is_bonus": True, "bonus": "2 voor 3.50", "times": 5, "orders": 8},
                {"id": 4, "title": "Kaas", "is_bonus": False, "times": 4, "orders": 8}]

    app.get_frequent = frequent
    ha.notes.clear()
    await app.check_bonus_notifications()
    assert len(ha.notes) == 1 and ha.notes[0][0] == "happie_bonus"
    msg = ha.notes[0][2]
    assert "Pesto" in msg and "op je lijst" in msg and "Bananen" in msg and "Kaas" not in msg, msg
    await app.check_bonus_notifications()
    assert len(ha.notes) == 1, "same offers must not notify twice"
    # offer ends, then comes back -> notify again
    app._product_cache[1]["is_bonus"] = False
    await app.check_bonus_notifications()
    app._product_cache[1]["is_bonus"] = True
    await app.check_bonus_notifications()
    assert len(ha.notes) == 2 and "Pesto" in ha.notes[1][2] and "Bananen" not in ha.notes[1][2]

    print("all notification tests passed")


asyncio.run(run())
