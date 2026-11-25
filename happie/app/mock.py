"""Development mocks: in-memory AH list and HA to-do list (HAPPIE_MOCK=1).

Product search still talks to the real AH API with an anonymous token.
"""
from __future__ import annotations

import itertools
import logging
import random
from datetime import date, timedelta

from ah import ListItem, normalize
from ha.client import TodoItem

_LOGGER = logging.getLogger(__name__)


class FakeHA:
    under_supervisor = False  # settings are saved to <DATA_DIR>/options.json

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id
        self.items: list[TodoItem] = [TodoItem("1", "Bananen", False), TodoItem("2", "Wc-papier", False)]
        self._ids = itertools.count(100)

    async def entity_exists(self) -> bool:
        return True

    async def get_items(self):
        return list(self.items)

    async def add_item(self, summary, completed=False):
        self.items.append(TodoItem(str(next(self._ids)), summary, completed))

    async def set_completed(self, item, completed):
        for i in self.items:
            if i.uid == item.uid:
                i.completed = completed

    async def remove_items(self, items):
        uids = {i.uid for i in items}
        self.items = [i for i in self.items if i.uid not in uids]

    async def listen(self, on_change):
        return

    async def set_state(self, entity_id, state, attrs):
        _LOGGER.debug("Mock sensor %s = %s", entity_id, state)

    async def notify(self, title, message, notification_id, service=""):
        _LOGGER.info("Mock melding [%s] %s: %s", notification_id, title, message)

    async def dismiss(self, notification_id):
        _LOGGER.info("Mock melding weg [%s]", notification_id)


def fake_purchases(today: date | None = None, weeks: int = 60) -> list[dict]:
    """A weekly online order plus a few store visits, deterministic."""
    rnd = random.Random(42)
    today = today or date.today()
    out = []
    for w in range(weeks):
        monday = today - timedelta(days=today.weekday() + 7 * w)
        if rnd.random() < 0.85:
            d = monday + timedelta(days=rnd.choice([0, 3]))
            if d <= today:
                out.append({"id": f"order:{w}", "source": "online", "date": d.isoformat(),
                            "total": round(rnd.uniform(45, 110), 2)})
        for n in range(rnd.choice([0, 1, 1, 2, 3])):
            d = monday + timedelta(days=rnd.randrange(7))
            if d <= today:
                out.append({"id": f"receipt:{w}-{n}", "source": "winkel", "date": d.isoformat(),
                            "total": round(rnd.uniform(4, 35), 2)})
    return out


def install_mocks(app, mock_ha: bool = True) -> None:
    ah = app.ah
    store: list[dict] = [
        {"description": "AH Halfvolle melk", "productId": 1525, "quantity": 2, "strikedthrough": False},
        {"description": "Brood", "quantity": 1, "strikedthrough": False},
    ]
    ah._access_token = "mock"
    ah._refresh_token = "mock"
    ah._expires_at = 1e12

    async def get_list():
        return [
            ListItem(d["description"], d["quantity"], d["strikedthrough"], d.get("productId"), d)
            for d in store
        ]

    async def patch(items):
        for body in items:
            key = normalize(body["description"])
            match = next((d for d in store if normalize(d["description"]) == key), None)
            if body["quantity"] == 0:
                if match:
                    store.remove(match)
                continue
            if match is None:
                match = {"description": body["description"]}
                store.append(match)
            match["quantity"] = body["quantity"]
            match["strikedthrough"] = body["strikeThrough"]
            if body.get("productId"):
                match["productId"] = body["productId"]

    async def login(code):
        _LOGGER.info("Mock login met code %s", code)

    ah._any_token = ah._anonymous_token

    async def suggestions(basket, limit=12):
        return (await ah.search("kaas", size=limit))

    ah.suggestions = suggestions

    async def get_member():
        return {"id": 1, "first_name": "Test", "name": "Test Gebruiker"}

    ah.get_member = get_member

    async def get_next_delivery():
        return {"order_id": 1, "state": "SUBMITTED", "date": "2026-11-23", "start": "18:00", "end": "22:00",
                "start_utc": "2026-11-23T17:00:00Z", "end_utc": "2026-11-23T21:00:00Z",
                "closing_time": "2026-11-22T22:59:00Z", "type": "DELIVERY", "total": 42.5, "item_count": 12}

    ah.get_next_delivery = get_next_delivery

    async def frequent_products(max_orders=8, limit=40):
        out = await ah.search("melk", size=10)
        for n, p in enumerate(out):
            p.update({"times": 6 - n // 2, "orders": 6})
        return out

    async def bonus_for_you():
        return {"personal": [], "previously_bought": [p for p in await ah.search("bonus", size=12)]}

    async def delivered_orders(n=8):
        return [{"orderId": 1001, "deliveryDate": "2026-11-16"}, {"orderId": 1000, "deliveryDate": "2026-11-09"}][:n]

    found: dict[str, list] = {}

    async def cached_search(term, size=8):
        if term not in found:
            found[term] = await ah.search(term, size=size)
        return found[term]

    async def order_lines(order_id):
        rnd = random.Random(str(order_id))
        terms = rnd.sample(["ontbijt", "melk", "groente", "kaas", "brood", "fruit", "chips"], 3)
        products = [p for t in terms for p in (await cached_search(t))[:rnd.randint(2, 5)]]
        return [{"product": p, "quantity": 1 + n % 3} for n, p in enumerate(products)]

    receipt_texts = ["AH HALFVOLLE", "AH BANANEN", "AH KIPFILET", "AH EIEREN", "TONY CHOCO", "AH CROISSANT",
                     "SPA ROOD", "STATIEGELD", "AH TAS PAPIER", "BAKKERIJ DIV"]
    unknown = {"STATIEGELD", "AH TAS PAPIER", "BAKKERIJ DIV"}

    async def receipt_lines(receipt_id):
        rnd = random.Random(receipt_id)
        return [{"hq_id": 1000 + receipt_texts.index(t), "name": t, "quantity": 1.0, "amount": round(rnd.uniform(0.25, 6), 2)}
                for t in rnd.sample(receipt_texts, rnd.randint(2, 6))]

    async def product_by_hq_id(hq_id, name):
        if name in unknown:
            return None, "Bakkerij" if "BAKKERIJ" in name else None
        hits = await cached_search(name.replace("AH ", ""), size=1)
        return (hits[0], None) if hits else (None, None)

    async def online_purchases():
        return [p for p in fake_purchases() if p["source"] == "online"]

    async def store_purchases(since, page_size=50, max_pages=20, known=None):
        return [p for p in fake_purchases() if p["source"] == "winkel" and p["date"] >= since]

    async def order_summaries():
        today = date.today()
        nxt = today + timedelta(days=3)
        rows = [{"orderId": 1, "deliveryDate": nxt.isoformat(), "state": "SUBMITTED",
                 "orderTotalPrice": {"priceTotalPayable": 42.5, "priceDiscount": 3.1}},
                {"orderId": 2, "deliveryDate": (nxt + timedelta(days=7)).isoformat(), "state": "CONFIRMED",
                 "orderTotalPrice": {"priceTotalPayable": 0}}]
        for n, d in enumerate((7, 14, 21)):
            rows.append({"orderId": 1001 - n, "deliveryDate": (today - timedelta(days=d)).isoformat(), "state": "DELIVERED",
                         "orderTotalPrice": {"priceTotalPayable": 60 + 7 * n, "priceDiscount": 4.25}})
        return rows

    async def mock_order_lines(order_id):
        if str(order_id) == "2":
            return []  # planned order, not filled yet
        return await order_lines(order_id)

    ah.order_summaries = order_summaries
    ah.online_purchases = online_purchases
    ah.store_purchases = store_purchases
    ah.receipt_lines = receipt_lines
    ah.product_by_hq_id = product_by_hq_id
    ah.delivered_orders = delivered_orders
    ah.order_lines = mock_order_lines
    ah.frequent_products = frequent_products
    ah.bonus_for_you = bonus_for_you
    ah.get_list = get_list
    ah._patch = patch
    ah.login_with_code = login
    ah.logout = lambda: None
    # the fake AH list starts fresh every run, so the sync snapshot must too
    app.sync.reset()
    if mock_ha:
        app.ha = FakeHA(app.options["todo_entity"])
        app.sync.ha = app.ha
        app.fake_ha = app.ha
