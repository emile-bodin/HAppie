"""Articles per purchase: most bought, categories, receipt lines, linking. Run: python tests/test_purchase_items.py"""
import asyncio
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import config  # noqa: E402
from ah import AHError  # noqa: E402
from server.app import App  # noqa: E402
from services.purchase_items import UNMATCHED, PurchaseItems, overview, receipt_key  # noqa: E402
from services.spending import weekday_average  # noqa: E402

TODAY = date(2026, 11, 20)


def p(pid, source, day, total=10.0):
    return {"id": pid, "source": source, "date": day, "total": total}


def product(pid, title, category, price):
    return {"id": pid, "title": title, "category": category, "image": None, "price": price}


def store_with_lines(path):
    s = PurchaseItems(path)
    melk = s.add_product(product(1, "Melk", "Zuivel, eieren", 1.29))
    kaas = s.add_product(product(2, "Kaas", "Kaas", 4.0))
    s.lines = {
        "order:1": [{"key": melk, "name": "Melk", "qty": 2, "amount": None},
                    {"key": kaas, "name": "Kaas", "qty": 1, "amount": None}],
        "order:2": [{"key": melk, "name": "Melk", "qty": 1, "amount": None}],
        # a receipt: melk matched by hqId, statiegeld not
        "receipt:a": [{"key": melk, "name": "AH HALFVOLLE", "qty": 1, "amount": 1.19},
                      {"key": "r:99", "name": "STATIEGELD", "qty": 1, "amount": 0.25}],
        "receipt:b": [{"key": melk, "name": "AH HALFVOLLE", "qty": 1, "amount": 1.19}],
    }
    s.hq = {"99": {"key": None, "guess": "Frisdrank"}}
    return s


PURCHASES = [p("order:1", "online", "2026-10-01"), p("order:2", "online", "2026-10-15"),
             p("receipt:a", "winkel", "2026-10-29"), p("receipt:b", "winkel", "2026-11-12"),
             p("order:old", "online", "2025-01-01")]


def test_overview():
    s = store_with_lines(os.path.join(tempfile.mkdtemp(), "items.json"))
    o = overview(s, PURCHASES, "2025-11-20", TODAY)
    assert o["total"] == 4 and o["covered"] == 4, o  # the old order is out of range
    melk = o["top"][0]
    assert melk["name"] == "Melk" and melk["times"] == 4 and melk["online"] == 2 and melk["winkel"] == 2
    assert melk["quantity"] == 5 and melk["paid"] == 2.38
    assert melk["amount"] == round(2.38 + 3 * 1.29, 2) and melk["estimated"]  # 3 ordered ones at today's price
    assert melk["interval"] == 14 and melk["last"] == "2026-11-12"
    assert not melk["due"]  # 8 days since the last one, every ~14 days
    assert [r["name"] for r in o["top"]] == ["Melk", "Kaas"]  # unrecognised lines are no products
    names = [c["name"] for c in o["categories"]]
    assert names[-1] == UNMATCHED and names[0] == "Zuivel, eieren", names
    zuivel = o["categories"][0]
    assert zuivel["winkel"] == 2.38 and zuivel["online"] == round(3 * 1.29, 2)
    assert round(sum(c["share"] for c in o["categories"])) == 100
    assert o["unmatched"][0]["name"] == "STATIEGELD" and o["unmatched"][0]["guess"] == "Frisdrank"
    assert "Kaas" in o["category_names"]

    # due: bought every ~14 days, last one 30 days ago
    o = overview(s, PURCHASES, "2025-11-20", date(2026, 12, 12))
    assert o["top"][0]["due"]
    # 3 months back: only the receipts and order:2... order:1 (1 Oct) too: 91 days before 20 Nov is 21 Aug
    o = overview(s, PURCHASES, "2026-10-20", TODAY)
    assert o["total"] == 2 and o["top"][0]["times"] == 2


def test_link_and_store():
    path = os.path.join(tempfile.mkdtemp(), "items.json")
    s = store_with_lines(path)
    s.link("r:99", "Frisdrank")
    s.save()
    s = PurchaseItems(path)
    assert s.links == {"r:99": "Frisdrank"} and len(s.lines) == 4
    o = overview(s, PURCHASES, "2025-11-20", TODAY)
    assert not o["unmatched"] and "Frisdrank" in [c["name"] for c in o["categories"]]
    s.link("r:99", None)
    assert overview(s, PURCHASES, "2025-11-20", TODAY)["unmatched"]
    assert receipt_key(None, "ah  tas papier") == "r:AH TAS PAPIER" and receipt_key(12, "x") == "r:12"
    assert [x["id"] for x in s.pending(PURCHASES + [p("order:3", "online", "2026-11-19")], "2026-01-01")] == ["order:3"]
    s.prune({"order:1"})
    assert list(s.lines) == ["order:1"]


def test_weekday_average():
    ps = [p("a", "online", "2026-11-16", 24.0), p("b", "winkel", "2026-11-14", 12.0), p("c", "winkel", "2026-01-01", 99.0)]
    w = weekday_average(ps, TODAY, weeks=12)
    # 12 Mondays, but only 11 Saturdays: this week's Saturday is still to come. January is too long ago
    assert w[0] == 2.0 and w[5] == round(12 / 11, 2) and sum(w) == w[0] + w[5], w
    # a short history: divided by the weeks since the first purchase, not by 12
    w = weekday_average(ps[:2], TODAY, weeks=12)
    assert w[0] == 12.0 and w[5] == 12.0, w  # 2 Mondays (09-11, 16-11), 1 Saturday so far (14-11)
    # only a delivery still to come: nothing yet, and never negative
    assert weekday_average([p("x", "online", "2026-11-30", 50.0)], TODAY) == [0.0] * 7


async def test_app_fetches_items():
    app = App(None, {**config.load_options(), "month_budget": 300})
    app.ah._refresh_token = "x"  # logged in
    app.spending.merge([p("order:1", "online", "2026-11-10"), p("receipt:a", "winkel", "2026-11-12"),
                        p("receipt:bad", "winkel", "2026-11-13")], TODAY)
    app.spending.updated_at = 1
    calls = {"search": 0}

    async def order_lines(order_id):
        return [{"product": product(1, "Melk", "Zuivel, eieren", 1.29), "quantity": 2, "ordered": 2},
                {"product": product(5, "Uitverkocht", "Kaas", 3.0), "quantity": 0, "ordered": 1}]

    async def receipt_lines(rid):
        if rid == "bad":
            raise AHError("500")
        return [{"hq_id": 11943, "name": "AH HALFVOLLE", "quantity": 1.0, "amount": 1.19},
                {"hq_id": 77, "name": "STATIEGELD", "quantity": 1.0, "amount": 0.25},
                {"hq_id": 11943, "name": "AH HALFVOLLE", "quantity": 1.0, "amount": 1.19}]

    async def product_by_hq_id(hq_id, name):
        calls["search"] += 1
        return (product(1, "Melk", "Zuivel, eieren", 1.29), None) if hq_id == 11943 else (None, "Bier")

    app.ah.order_lines = order_lines
    app.ah.receipt_lines = receipt_lines
    app.ah.product_by_hq_id = product_by_hq_id
    app.start_items_refresh()
    await app._items_task
    assert set(app.items.lines) == {"order:1", "receipt:a"}, app.items.lines
    assert app.items.lines["order:1"] == [{"key": "p:1", "name": "Melk", "qty": 2, "amount": None}]  # not delivered: out
    assert [l["key"] for l in app.items.lines["receipt:a"]] == ["p:1", "r:77", "p:1"]
    assert calls["search"] == 2  # each hqId is looked up once
    assert "receipt:bad" in app._items_failed
    app.start_items_refresh()
    assert not app.items_running  # failed one waits ITEMS_RETRY before the next try
    assert PurchaseItems(app.items.path).lines.keys() == app.items.lines.keys()  # saved

    o = overview(app.items, app.spending.list(), "2026-01-01", TODAY)
    assert o["top"][0]["times"] == 2 and o["top"][0]["quantity"] == 4 and o["unmatched"][0]["guess"] == "Bier"
    assert app.spending_overview()["month_budget"]["budget"] == 300


async def test_no_double_fetches():
    """Receipts fetched together share hqId lookups, and the panel waits for the background fetch of a purchase."""
    app = App(None, config.load_options())
    app.ah._refresh_token = "x"
    app.spending.merge([p("receipt:c", "winkel", "2026-11-12"), p("receipt:d", "winkel", "2026-11-13")], TODAY)
    calls = {"lines": [], "search": 0}

    async def receipt_lines(rid):
        calls["lines"].append(rid)
        await asyncio.sleep(0.01)
        return [{"hq_id": 555, "name": "AH KARNEMELK", "quantity": 1.0, "amount": 1.19}]

    async def product_by_hq_id(hq_id, name):
        calls["search"] += 1
        await asyncio.sleep(0.01)
        return product(9, "Karnemelk", "Zuivel, eieren", 0.99), None

    app.ah.receipt_lines = receipt_lines
    app.ah.product_by_hq_id = product_by_hq_id
    app.start_items_refresh()
    await asyncio.sleep(0)  # the background task has started on both receipts
    resp = await app.spending_purchase_api(type("R", (), {"match_info": {"purchase_id": "receipt:c"}})())
    await app._items_task
    assert resp.status == 200
    assert sorted(calls["lines"]) == ["c", "d"], calls  # receipt c fetched once, not again for the panel
    assert calls["search"] == 1, calls  # one lookup for the hqId both receipts have
    assert not app._items_inflight and not app._hq_inflight

    # the background task is busy with other purchases: the panel doesn't wait for it
    app.spending.merge([p("receipt:e", "winkel", "2026-11-14")], TODAY)
    app._items_sem = asyncio.Semaphore(0)  # every background slot taken
    app.start_items_refresh()
    resp = await asyncio.wait_for(
        app.spending_purchase_api(type("R", (), {"match_info": {"purchase_id": "receipt:e"}})()), 1)
    assert resp.status == 200 and "e" in calls["lines"]
    app._items_task.cancel()


if __name__ == "__main__":
    test_overview()
    test_link_and_store()
    test_weekday_average()
    asyncio.run(test_app_fetches_items())
    asyncio.run(test_no_double_fetches())
    print("all purchase item tests passed")
