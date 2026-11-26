"""Articles per purchase (online orders and store receipts): most bought products and spending per category."""
from __future__ import annotations

import json
import logging
import os
import re
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


def discount_key(name: str) -> str:
    """What a receipt discount's name ("ALLEROBIJN", "MBAHSNOEPGRO") has in common with its lines' texts."""
    key = re.sub(r"[^A-Z0-9]", "", name.upper())
    for prefix in ("ALLE", "MB", "AH"):  # "alle Robijn", "meer bonus", "AH ..."
        if key.startswith(prefix) and len(key) > len(prefix) + 3:
            key = key[len(prefix):]
    return key[:5]


def _share(cents: int, weights: list[int]) -> list[int]:
    """Split `cents` over the weights; the rounding rest goes to the largest, so the parts add up exactly."""
    if not weights:
        return []
    total = sum(weights)
    if total <= 0:
        weights, total = [1] * len(weights), len(weights)
    parts = [int(cents * w / total) for w in weights]
    parts[weights.index(max(weights))] += cents - sum(parts)
    return parts


def allocate_receipt(lines: list[dict[str, Any]], discounts: list[dict[str, Any]],
                     titles: list[str | None]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Put a receipt's discounts and deposits on its lines, so the lines add up to what was paid.

    lines:     [{key, name, qty, amount (before discounts), deposit}]; titles: product title per line or None
    A discount goes to the lines whose receipt text or product title has its name in it, by their price;
    one that fits no line (Air Miles, most coupons) is spread over the whole receipt.
    Returns the lines as [{key, name, qty, gross, deposit, bonus, spread, amount}] and the discounts with `matched`.
    """
    def cents(x: Any) -> int:
        return round((x or 0) * 100)

    gross = [cents(l.get("amount")) for l in lines]
    texts = [re.sub(r"[^A-Z0-9]", "", f"{l['name']} {t or ''}".upper()) for l, t in zip(lines, titles)]
    bonus = [0] * len(lines)
    spread = [0] * len(lines)
    out_discounts = []
    for d in discounts:
        key = discount_key(d["name"])
        hits = [i for i, t in enumerate(texts) if len(key) >= 3 and key in t]
        target, idx = (bonus, hits) if hits else (spread, list(range(len(lines))))
        for i, part in zip(idx, _share(cents(d["amount"]), [gross[i] for i in idx])):
            target[i] += part
        out_discounts.append({**d, "matched": bool(hits)})
    out = []
    for n, l in enumerate(lines):
        dep = cents(l.get("deposit"))
        out.append({"key": l["key"], "name": l["name"], "qty": l["qty"], "gross": gross[n] / 100,
                    "deposit": dep / 100, "bonus": bonus[n] / 100, "spread": spread[n] / 100,
                    "amount": (gross[n] + dep + bonus[n] + spread[n]) / 100})
    return out, out_discounts


class PurchaseItems:
    """Lines per purchase, cached on disk. Finished purchases never change, so each one is fetched once.

    lines:     purchase id -> [{key, name, qty, amount}]; amount is what was paid (receipts, after discounts and
               with statiegeld; see allocate_receipt) or None (orders)
    discounts: receipt purchase id -> [{name, type, amount, matched}]
    products:  "p:<webshopId>" -> {id, title, category, image, price}
    hq:        str(hqId) -> {key: product key or None, guess: category of the best search hit}
    links:     receipt key ("r:...") -> category the user picked for an unrecognised receipt line
    """

    # 2: receipt lines carry their discounts and statiegeld; older receipt lines are fetched again
    VERSION = 2

    def __init__(self, path: str) -> None:
        self.path = path
        self.lines: dict[str, list[dict[str, Any]]] = {}
        self.discounts: dict[str, list[dict[str, Any]]] = {}
        self.products: dict[str, dict[str, Any]] = {}
        self.hq: dict[str, dict[str, Any]] = {}
        self.links: dict[str, str] = {}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.lines = data.get("lines") or {}
            self.discounts = data.get("discounts") or {}
            self.products = data.get("products") or {}
            self.hq = data.get("hq") or {}
            self.links = data.get("links") or {}
            if data.get("version") != self.VERSION:
                self.lines = {k: v for k, v in self.lines.items() if not k.startswith("receipt:")}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as err:
            _LOGGER.warning("Kon artikelen van aankopen niet lezen: %s", err)

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": self.VERSION, "lines": self.lines, "discounts": self.discounts,
                       "products": self.products, "hq": self.hq, "links": self.links}, fh)
        os.replace(tmp, self.path)

    def pending(self, purchases: list[dict[str, Any]], since: str) -> list[dict[str, Any]]:
        """Purchases since `since` whose lines aren't known yet, newest first."""
        todo = [p for p in purchases if p["date"] >= since and p["id"] not in self.lines]
        return sorted(todo, key=lambda p: p["date"], reverse=True)

    def prune(self, keep: set[str]) -> None:
        self.lines = {k: v for k, v in self.lines.items() if k in keep}
        self.discounts = {k: v for k, v in self.discounts.items() if k in keep}

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
