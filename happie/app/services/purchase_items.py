"""Articles per purchase (online orders and store receipts): most bought products and spending per category."""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

_LOGGER = logging.getLogger(__name__)

UNMATCHED = "Niet herkend"
OTHER = "Overig"


def product_key(product_id: Any) -> str:
    return f"p:{product_id}"


def receipt_key(hq_id: Any, name: str) -> str:
    """Key of a receipt line without a known product; the same text on a later receipt gets the same key."""
    return f"r:{hq_id}" if hq_id else "r:" + " ".join(name.upper().split())


class PurchaseItems:
    """Lines per purchase, cached on disk. Finished purchases never change, so each one is fetched once.

    lines:    purchase id -> [{key, name, qty, amount}]; amount is what was paid (receipts) or None (orders)
    products: "p:<webshopId>" -> {id, title, category, image, price}
    hq:       str(hqId) -> {key: product key or None, guess: category of the best search hit}
    links:    receipt key ("r:...") -> category the user picked for an unrecognised receipt line
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.lines: dict[str, list[dict[str, Any]]] = {}
        self.products: dict[str, dict[str, Any]] = {}
        self.hq: dict[str, dict[str, Any]] = {}
        self.links: dict[str, str] = {}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.lines = data.get("lines") or {}
            self.products = data.get("products") or {}
            self.hq = data.get("hq") or {}
            self.links = data.get("links") or {}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as err:
            _LOGGER.warning("Kon artikelen van aankopen niet lezen: %s", err)

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"lines": self.lines, "products": self.products, "hq": self.hq, "links": self.links}, fh)
        os.replace(tmp, self.path)

    def pending(self, purchases: list[dict[str, Any]], since: str) -> list[dict[str, Any]]:
        """Purchases since `since` whose lines aren't known yet, newest first."""
        todo = [p for p in purchases if p["date"] >= since and p["id"] not in self.lines]
        return sorted(todo, key=lambda p: p["date"], reverse=True)

    def prune(self, keep: set[str]) -> None:
        self.lines = {k: v for k, v in self.lines.items() if k in keep}

    def add_product(self, p: dict[str, Any]) -> str:
        key = product_key(p["id"])
        self.products[key] = {k: p.get(k) for k in ("id", "title", "category", "image", "price")}
        return key

    def category(self, key: str) -> str:
        if key in self.products:
            return self.products[key].get("category") or OTHER
        return self.links.get(key) or UNMATCHED

    def link(self, key: str, category: str | None) -> None:
        if category:
            self.links[key] = category
        else:
            self.links.pop(key, None)


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def overview(store: PurchaseItems, purchases: list[dict[str, Any]], since: str, today: date,
             top: int = 30, per_category: int = 8) -> dict[str, Any]:
    """Most bought products, spending per category and unrecognised receipt lines since `since`.

    Receipt lines carry what was paid. Order lines don't, so those are estimated with the product's price.
    """
    in_range = [p for p in purchases if p["date"] >= since]
    stats: dict[str, dict[str, Any]] = {}
    covered = 0
    for pur in in_range:
        lines = store.lines.get(pur["id"])
        if lines is None:
            continue
        covered += 1
        seen: set[str] = set()
        for line in lines:
            key = line["key"]
            s = stats.setdefault(key, {"key": key, "name": line["name"], "times": 0, "online": 0, "winkel": 0,
                                       "qty": 0.0, "paid": 0.0, "est_qty": 0.0, "dates": []})
            if key not in seen:
                seen.add(key)
                s["times"] += 1
                s[pur["source"]] += 1
                s["dates"].append(pur["date"])
            s["qty"] += line.get("qty") or 0
            if line.get("amount") is not None:
                s["paid"] += line["amount"]
            else:
                s["est_qty"] += line.get("qty") or 0

    rows = []
    for key, s in stats.items():
        product = store.products.get(key)
        price = (product or {}).get("price")
        dates = sorted(s["dates"])
        interval = round(_days(dates[0], dates[-1]) / (len(dates) - 1)) if len(dates) > 1 else None
        rows.append({
            "key": key, "name": (product or {}).get("title") or s["name"], "receipt_name": s["name"],
            "product": product, "category": store.category(key),
            "times": s["times"], "online": s["online"], "winkel": s["winkel"], "quantity": round(s["qty"], 2),
            "amount": round(s["paid"] + s["est_qty"] * (price or 0), 2), "paid": round(s["paid"], 2),
            "estimated": s["est_qty"] > 0, "last": dates[-1], "interval": interval,
            "due": bool(interval and s["times"] >= 3 and _days(dates[-1], today.isoformat()) >= interval),
        })
    rows.sort(key=lambda r: (-r["times"], -r["quantity"], r["name"]))

    cats: dict[str, dict[str, Any]] = {}
    for r in rows:
        c = cats.setdefault(r["category"], {"name": r["category"], "amount": 0.0, "online": 0.0, "winkel": 0.0,
                                            "items": [], "count": 0})
        c["amount"] += r["amount"]
        c["winkel"] += r["paid"]
        c["online"] += r["amount"] - r["paid"]
        c["count"] += 1
        if len(c["items"]) < per_category:
            c["items"].append(r)
    total = sum(c["amount"] for c in cats.values()) or 1
    categories = sorted(cats.values(), key=lambda c: (c["name"] == UNMATCHED, -c["amount"]))
    for c in categories:
        c.update({k: round(c[k], 2) for k in ("amount", "online", "winkel")})
        c["share"] = round(c["amount"] / total * 100, 1)

    unmatched = [{**r, "guess": (store.hq.get(r["key"][2:]) or {}).get("guess")}
                 for r in rows if r["category"] == UNMATCHED]
    names = {p.get("category") for p in store.products.values() if p.get("category")} | set(store.links.values())
    return {
        "top": [r for r in rows if r["product"]][:top],
        "categories": categories,
        "unmatched": unmatched,
        "category_names": sorted(names),
        "covered": covered,
        "total": len(in_range),
    }
