"""Order overview tests: order list, products of an order, sensor attribute. Run: python tests/test_orders.py"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "appie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import main  # noqa: E402
from ah_client import ListItem, parse_eta  # noqa: E402


class Req:
    def __init__(self, match_info=None, query=None):
        self.match_info, self.query = match_info or {}, query or {}


class FakeHA:
    def __init__(self):
        self.states = {}

    async def set_state(self, entity_id, state, attrs):
        self.states[entity_id] = (state, attrs)


def product(pid, title, price, cat="Zuivel"):
    return {"id": pid, "title": title, "price": price, "price_before": None, "is_bonus": False, "category": cat}


async def run():
    app = main.App(None, main.load_options())
    today = date.today()
    summaries = [
        {"orderId": 1, "deliveryDate": (today + timedelta(days=2)).isoformat(), "state": "CONFIRMED",
         "orderTotalPrice": {"priceTotalPayable": 50.0, "priceDiscount": 5.0}},
        {"orderId": 2, "deliveryDate": today.isoformat(), "state": "OUT_FOR_DELIVERY", "orderTotalPrice": {"priceTotalPayable": 80.0}},
        {"orderId": 3, "deliveryDate": (today - timedelta(days=7)).isoformat(), "state": "DELIVERED", "orderTotalPrice": {"priceTotalPayable": 70.0}},
        {"orderId": 4, "deliveryDate": (today - timedelta(days=14)).isoformat(), "state": "DELIVERED", "orderTotalPrice": {"priceTotalPayable": 60.0}},
        {"orderId": 5, "deliveryDate": (today + timedelta(days=5)).isoformat(), "state": "CANCELLED"},
    ]
    calls = []

    async def order_summaries():
        return summaries

    async def order_lines(order_id):
        calls.append(str(order_id))
        return [{"product": product(10, "Melk", 1.29), "quantity": 2, "ordered": 3},
                {"product": product(11, "Brood", 2.5, "Bakkerij"), "quantity": 1, "ordered": 1}]

    app.ah.order_summaries = order_summaries
    app.ah.order_lines = order_lines
    app.inventory.unpacked_orders = [3]

    # --- order list: upcoming soonest first, then delivered newest first; cancelled left out
    data = json.loads((await app.orders(Req())).text)["orders"]
    assert [o["order_id"] for o in data] == [2, 1, 3, 4], data
    assert data[1]["total"] == 50.0 and data[1]["discount"] == 5.0 and not data[1]["done"]
    assert data[2]["done"] and data[2]["unpacked"] and not data[3]["unpacked"]

    # --- products of an order, marked when also on the shopping list
    app.sync.last_items = [ListItem("Melk", 1, False, 10), ListItem("Brood", 1, True, 11)]
    d = json.loads((await app.order(Req({"order_id": "1"}))).text)
    assert d["items"] == 3 and len(d["lines"]) == 2
    melk, brood = d["lines"]
    assert melk["on_list"] == 1 and melk["ordered"] == 3 and melk["line"]["total"] == 2.58
    assert brood["on_list"] is None  # checked off on the list -> not a duplicate
    assert app._product_cache[10]["title"] == "Melk"

    # --- caching: open orders for a few minutes, delivered ones for good
    await app.order(Req({"order_id": "1"}))
    assert calls == ["1"], calls
    await app.order(Req({"order_id": "1"}, {"refresh": "1"}))
    assert calls == ["1", "1"]
    app._order_lines["1"] = (0, False, app._order_lines["1"][2])  # expired
    await app.order(Req({"order_id": "1"}))
    assert calls == ["1", "1", "1"]
    await app.order(Req({"order_id": "3"}, {"done": "1"}))
    app._order_lines["3"] = (0, True, app._order_lines["3"][2])
    await app.order(Req({"order_id": "3"}, {"done": "1"}))
    assert calls.count("3") == 1, calls
    d = json.loads((await app.order(Req({"order_id": "3"}, {"done": "1"}))).text)
    assert d["unpacked"] is True

    # --- products as attribute on the delivery sensor
    ha = app.ha = FakeHA()

    async def next_delivery():
        return {"order_id": 2, "state": "OUT_FOR_DELIVERY", "date": today.isoformat(), "start": "18:00", "end": "20:00",
                "start_utc": f"{today}T17:00:00Z", "end_utc": f"{today}T19:00:00Z", "item_count": 3,
                **parse_eta({"state": "OUT_FOR_DELIVERY", "message": "Onze bezorger verwacht tussen 18:40 en 19:40 uur bij je te zijn."})}

    app.ah.get_next_delivery = next_delivery
    await app.refresh_delivery()
    attrs = ha.states[main.DELIVERY_SENSOR][1]
    assert attrs["products"] == ["2× Melk", "Brood"], attrs
    assert attrs["eta_window"] == "18:40–19:40" and attrs["eta_start"].startswith(f"{today}T18:40:00")
    assert attrs["eta_end"].startswith(f"{today}T19:40:00") and "bezorger" in attrs["eta_message"]
    assert parse_eta({"message": "Bezorging tussen 9.05 - 10.05"})["eta_start"] == "09:05"
    assert parse_eta({"state": "CONFIRMED"})["eta_start"] is None
    print("all order tests passed")


asyncio.run(run())
