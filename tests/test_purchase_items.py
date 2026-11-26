"""Articles per purchase: most bought, categories, receipt lines, linking. Run: python tests/test_purchase_items.py"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import config  # noqa: E402
from ah import AHError  # noqa: E402
from server.app import App  # noqa: E402
from services.purchase_items import (  # noqa: E402
    UNMATCHED, PurchaseItems, allocate_receipt, discount_key, overview, receipt_key)  # noqa: E402
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


def line(key, name, amount, deposit=0.0, qty=1.0):
    return {"key": key, "name": name, "qty": qty, "amount": amount, "deposit": deposit}


def test_allocate_receipt():
    assert discount_key("ALLEROBIJN") == "ROBIJ" and discount_key("MBAHSNOEPGRO") == "SNOEP"
    assert discount_key("BIOPREMIUMST") == "BIOPR" and discount_key("AH") == "AH"
    # a real receipt (24 Nov): 17.98 on the lines, one bonus of 0.77 that fits no receipt text, paid 17.21
    lines = [line("r:1", "AH KRIELTJES", 0.79), line("r:2", "AH BIO BES", 4.69), line("r:3", "MANDARIJNEN", 2.29),
             line("r:4", "AH BIO PEER", 2.99), line("r:5", "AH ANDIJVIE", 1.49), line("r:6", "ALMHOF", 2.98, qty=2),
             line("r:7", "MENTOS", 2.75)]
    bio = [{"name": "BIOPREMIUMST", "type": "BONUS", "amount": -0.77}]
    out, ds = allocate_receipt(lines, bio, [None] * 7)
    assert round(sum(l["amount"] for l in out), 2) == 17.21 and not ds[0]["matched"]
    assert all(l["bonus"] == 0 for l in out) and round(sum(l["spread"] for l in out), 2) == -0.77
    assert out[1]["gross"] == 4.69 and out[1]["spread"] < out[0]["spread"] <= 0  # by price
    # with product titles: "Bio premium" is in two of them, so the bonus goes to those two
    titles = [None, "AH Biologisch Bio premium blauwe bessen", None, "AH Bio premium peer", None, None, None]
    out, ds = allocate_receipt(lines, bio, titles)
    assert ds[0]["matched"] and [i for i, l in enumerate(out) if l["bonus"]] == [1, 3]
    assert round(out[1]["bonus"] + out[3]["bonus"], 2) == -0.77 and round(sum(l["amount"] for l in out), 2) == 17.21

    # one promotion over several lines, a sticker, statiegeld, Air Miles for the whole receipt
    lines = [line("r:a", "ROBIJN K&K", 39.18, qty=2), line("r:b", "ROBIJN WIT", 19.59),
             line("r:c", "PESTO SPREAD", 4.38, qty=2), line("r:d", "AH SMOOTHIE", 7.98, deposit=0.30, qty=2),
             line("r:e", "MENTOS", 0.01)]
    ds = [{"name": "ALLEROBIJN", "type": "BONUS", "amount": -29.39}, {"name": "PESTO SPREAD", "type": "35% K", "amount": -1.4},
          {"name": "MIJN AH MILES", "type": "2000", "amount": -10.0}]
    out, ds = allocate_receipt(lines, ds, [None] * 5)
    assert [d["matched"] for d in ds] == [True, True, False]
    assert round(out[0]["bonus"] + out[1]["bonus"], 2) == -29.39 and out[0]["bonus"] < out[1]["bonus"]  # 2/3 and 1/3
    assert out[2]["bonus"] == -1.4 and out[3]["deposit"] == 0.30 and out[3]["bonus"] == 0
    assert round(sum(l["spread"] for l in out), 2) == -10.0
    total = 39.18 + 19.59 + 4.38 + 7.98 + 0.01 + 0.30 - 29.39 - 1.4 - 10.0
    assert round(sum(l["amount"] for l in out), 2) == round(total, 2)
    assert all(abs(l["amount"] * 100 - round(l["amount"] * 100)) < 1e-6 for l in out)  # whole cents
    # no discounts: nothing changes
    out, ds = allocate_receipt([line("r:x", "AH EIEREN", 3.15)], [], [None])
    assert out[0]["amount"] == 3.15 and out[0]["gross"] == 3.15 and ds == []


def test_old_cache():
    """Receipt lines cached before discounts were known are fetched again; orders, lookups and links stay."""
    path = os.path.join(tempfile.mkdtemp(), "items.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"lines": {"order:1": [{"key": "p:1", "name": "Melk", "qty": 1, "amount": None}],
                             "receipt:a": [{"key": "p:1", "name": "AH HALFVOLLE", "qty": 1, "amount": 1.19}]},
                   "products": {"p:1": product(1, "Melk", "Zuivel, eieren", 1.29)},
                   "hq": {"11943": {"key": "p:1", "guess": None}}, "links": {"r:99": "Frisdrank"}}, fh)
    s = PurchaseItems(path)
    assert list(s.lines) == ["order:1"] and s.hq and s.links and s.products
    assert [x["id"] for x in s.pending(PURCHASES, "2026-01-01")] == ["receipt:b", "receipt:a", "order:2"]
    s.lines["receipt:a"] = []
    s.save()
    assert "receipt:a" in PurchaseItems(path).lines  # the new version is kept


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

    async def receipt_details(rid):
        if rid == "bad":
            raise AHError("500")
        return {"lines": [{"hq_id": 11943, "name": "AH HALFVOLLE", "quantity": 1.0, "amount": 1.19, "deposit": 0.0},
                          {"hq_id": 77, "name": "SPA ROOD", "quantity": 1.0, "amount": 0.85, "deposit": 0.15},
                          {"hq_id": 11943, "name": "AH HALFVOLLE", "quantity": 1.0, "amount": 1.19, "deposit": 0.0}],
                "discounts": [{"name": "MBAHHALFVOLL", "type": "BONUS", "amount": -0.6},
                              {"name": "MIJN AH MILES", "type": "2000", "amount": -0.32}]}

    async def product_by_hq_id(hq_id, name):
        calls["search"] += 1
        return (product(1, "Melk", "Zuivel, eieren", 1.29), None) if hq_id == 11943 else (None, "Bier")

    app.ah.order_lines = order_lines
    app.ah.receipt_details = receipt_details
    app.ah.product_by_hq_id = product_by_hq_id
    app.start_items_refresh()
    await app._items_task
    assert set(app.items.lines) == {"order:1", "receipt:a"}, app.items.lines
    assert app.items.lines["order:1"] == [{"key": "p:1", "name": "Melk", "qty": 2, "amount": None}]  # not delivered: out
    assert [l["key"] for l in app.items.lines["receipt:a"]] == ["p:1", "r:77", "p:1"]
    assert calls["search"] == 2  # each hqId is looked up once
    a = app.items.lines["receipt:a"]
    assert round(sum(l["amount"] for l in a), 2) == round(3.23 + 0.15 - 0.92, 2), a  # what was paid
    assert [l["bonus"] for l in a] == [-0.3, 0, -0.3] and a[1]["deposit"] == 0.15, a
    assert [d["matched"] for d in app.items.discounts["receipt:a"]] == [True, False]
    assert "receipt:bad" in app._items_failed
    app.start_items_refresh()
    assert not app.items_running  # failed one waits ITEMS_RETRY before the next try
    saved = PurchaseItems(app.items.path)
    assert saved.lines.keys() == app.items.lines.keys() and saved.discounts.keys() == {"receipt:a"}  # saved
    app.spending.purchases["receipt:a"]["total"] = 2.46
    resp = await app.spending_purchase_api(type("R", (), {"match_info": {"purchase_id": "receipt:a"}})())
    body = json.loads(resp.body)
    assert body["deposit"] == 0.15 and body["total"] == 2.46 and [d["name"] for d in body["discounts"]] == ["MIJN AH MILES"]
    assert body["lines"][0]["gross"] == 1.19 and body["lines"][0]["bonus"] == -0.3

    o = overview(app.items, app.spending.list(), "2026-01-01", TODAY)
    assert o["top"][0]["times"] == 2 and o["top"][0]["quantity"] == 4 and o["unmatched"][0]["guess"] == "Bier"
    melk = sum(l["amount"] for l in a if l["key"] == "p:1")
    assert o["top"][0]["paid"] == round(melk, 2)  # after bonus and its share of the Air Miles
    assert app.spending_overview()["month_budget"]["budget"] == 300


async def test_no_double_fetches():
    """Receipts fetched together share hqId lookups, and the panel waits for the background fetch of a purchase."""
    app = App(None, config.load_options())
    app.ah._refresh_token = "x"
    app.spending.merge([p("receipt:c", "winkel", "2026-11-12"), p("receipt:d", "winkel", "2026-11-13")], TODAY)
    calls = {"lines": [], "search": 0}

    async def receipt_details(rid):
        calls["lines"].append(rid)
        await asyncio.sleep(0.01)
        return {"lines": [{"hq_id": 555, "name": "AH KARNEMELK", "quantity": 1.0, "amount": 1.19}], "discounts": []}

    async def product_by_hq_id(hq_id, name):
        calls["search"] += 1
        await asyncio.sleep(0.01)
        return product(9, "Karnemelk", "Zuivel, eieren", 0.99), None

    app.ah.receipt_details = receipt_details
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
    test_allocate_receipt()
    test_old_cache()
    test_weekday_average()
    asyncio.run(test_app_fetches_items())
    asyncio.run(test_no_double_fetches())
    print("all purchase item tests passed")
