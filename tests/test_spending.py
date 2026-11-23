"""Spending overview tests: aggregation, store, budget, sensors. Run: python tests/test_spending.py"""
import asyncio
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "appie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import main  # noqa: E402
import spending  # noqa: E402
from ah_client import AHClient, ListItem  # noqa: E402
from spending import SpendingStore, aggregate, budget_status, summary  # noqa: E402

TODAY = date(2026, 11, 20)  # Friday, ISO week 47


def p(pid, source, day, total):
    return {"id": pid, "source": source, "date": day, "total": total}


PURCHASES = [
    p("order:1", "online", "2026-11-16", 60.0),   # Monday, this week
    p("receipt:a", "winkel", "2026-11-20", 12.5),  # today
    p("receipt:b", "winkel", "2026-11-15", 8.0),   # Sunday, last week
    p("order:2", "online", "2026-11-09", 40.0),   # Monday, last week
    p("order:3", "online", "2026-10-31", 50.0),   # October
]


def test_aggregate_weeks():
    weeks = aggregate(PURCHASES, "week", 4, TODAY)
    assert [w["label"] for w in weeks] == ["wk 44", "wk 45", "wk 46", "wk 47"], weeks
    assert weeks[-1]["start"] == "2026-11-16" and weeks[-1]["end"] == "2026-11-22"
    assert weeks[-1] == {**weeks[-1], "online": 60.0, "winkel": 12.5, "total": 72.5, "count": 2}
    assert weeks[-2]["total"] == 48.0 and weeks[-2]["winkel"] == 8.0  # Sunday belongs to the week before
    assert weeks[1]["total"] == 0.0  # empty week stays in
    assert weeks[0]["total"] == 50.0  # 31 Oct is in ISO week 44


def test_aggregate_months_and_year_boundary():
    months = aggregate(PURCHASES, "month", 3, TODAY)
    assert [m["label"] for m in months] == ["sep", "okt", "nov"]
    assert months[-1]["total"] == 120.5 and months[1]["total"] == 50.0
    jan = aggregate([p("x", "online", "2026-12-31", 10.0), p("y", "online", "2027-01-01", 5.0)], "week", 2, date(2027, 1, 3))
    # 31 Dec 2026 (Thu) and 1 Jan 2027 (Fri) are both in ISO week 53 of 2026
    assert jan[-1]["label"] == "wk 53" and jan[-1]["total"] == 15.0, jan
    m = aggregate([p("y", "online", "2027-01-01", 5.0)], "month", 2, date(2027, 1, 3))
    assert [x["label"] for x in m] == ["dec", "jan '27"] and m[-1]["total"] == 5.0


def test_summary():
    s = summary(PURCHASES, TODAY)
    assert s["this_week"] == 72.5 and s["last_week"] == 48.0
    assert s["this_month"] == 120.5 and s["last_month"] == 50.0
    assert s["this_week_winkel"] == 12.5 and s["week_start"] == "2026-11-16"
    assert s["avg_week"] == round((48.0 + 50.0) / 8, 2)  # 8 complete weeks, empty ones count


def test_budget():
    assert budget_status(50, 20, 0) is None
    b = budget_status(72.5, 30.0, 100)
    assert b["projected"] == 102.5 and b["over"] and b["remaining"] == -2.5
    assert not budget_status(50, None, 100)["over"]


def test_store():
    path = os.path.join(tempfile.mkdtemp(), "spending.json")
    store = SpendingStore(path)
    assert store.merge(PURCHASES + [p("old", "online", "2025-01-01", 9.0)], TODAY) == 6
    assert "old" not in store.purchases  # older than HISTORY_DAYS
    assert store.merge(PURCHASES[:2], TODAY) == 0  # dedupe
    store.receipts_ok = True
    store.save(123.0)
    again = SpendingStore(path)
    assert again.updated_at == 123.0 and again.receipts_ok is True and len(again.list()) == 5
    assert again.ids("winkel") == {"receipt:a", "receipt:b"}


def test_order_total():
    summ = {"orderTotalPrice": {"priceAfterDiscount": 58.43, "priceTotalPayable": 59.43}}
    assert AHClient.order_total(summ) == 59.43
    assert AHClient.order_total({}) is None


class FakeHA:
    def __init__(self):
        self.notes, self.dismissed, self.states = [], [], {}

    async def notify(self, title, message, notification_id, service=""):
        self.notes.append((notification_id, title, message))

    async def dismiss(self, notification_id):
        self.dismissed.append(notification_id)

    async def set_state(self, entity_id, state, attrs):
        self.states[entity_id] = (state, attrs)


async def test_app_sensors_and_budget_warning():
    opts = {**main.load_options(), "week_budget": 100}
    app = main.App(None, opts)
    ha = app.ha = FakeHA()
    app.ah._refresh_token = "x"
    today = date.today()
    monday = today.fromordinal(today.toordinal() - today.weekday()).isoformat()

    async def online():
        return [p("order:1", "online", monday, 80.0)]

    async def store(since, known=None, **kw):
        return [p("receipt:a", "winkel", today.isoformat(), 10.0)]

    app.ah.online_purchases = online
    app.ah.store_purchases = store
    await app.refresh_spending()
    assert app.spending.receipts_ok and app.spending.updated_at

    # list: 2 x 7.50 = 15 -> 90 + 15 = 105 > 100
    app._product_cache = {1: {"id": 1, "title": "Kaas", "price": 7.5, "is_bonus": False}}
    await app.publish_list_sensors([ListItem("Kaas", 2, False, 1)])
    await app.publish_spending_sensors()
    week_state, week_attrs = ha.states[main.SPEND_WEEK_SENSOR]
    assert week_state == "90.0" and week_attrs["online"] == 80.0 and week_attrs["winkel"] == 10.0
    assert week_attrs["state_class"] == "total" and week_attrs["last_reset"].startswith(monday)
    assert week_attrs["budget_remaining"] == -5.0
    assert ha.states[main.BUDGET_SENSOR][0] == "on"

    await app.check_budget_notification()
    await app.check_budget_notification()
    assert [n[0] for n in ha.notes] == ["appie_budget"], ha.notes
    assert "105.00" in ha.notes[0][2]

    # list shrinks -> back under budget -> notification dismissed
    await app.publish_list_sensors([ListItem("Kaas", 1, False, 1)])
    await app.check_budget_notification()
    assert ha.dismissed == ["appie_budget"]
    await app.publish_spending_sensors()
    assert ha.states[main.BUDGET_SENSOR][0] == "off"

    # over again in the same week: no second notification
    await app.publish_list_sensors([ListItem("Kaas", 3, False, 1)])
    await app.check_budget_notification()
    assert len(ha.notes) == 1

    # receipts failing -> online only, flagged
    async def broken(since, known=None, **kw):
        raise main.AHError("404")

    app.ah.store_purchases = broken
    await app.refresh_spending()
    assert app.spending.receipts_ok is False and "receipt:a" in app.spending.purchases  # cached ones stay


if __name__ == "__main__":
    test_aggregate_weeks()
    test_aggregate_months_and_year_boundary()
    test_summary()
    test_budget()
    test_store()
    test_order_total()
    asyncio.run(test_app_sensors_and_budget_warning())
    print("all spending tests passed")
