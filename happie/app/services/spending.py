"""Spending overview: purchases (online orders + in-store receipts) per week or month."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)

MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
HISTORY_DAYS = 400  # how far back purchases are fetched and kept


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_start(d: date) -> date:
    return d.replace(day=1)


def _prev_month(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def _parse(s: str) -> date | None:
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


class SpendingStore:
    """Purchases cached on disk: {id: {id, source, date, total}}. Finished purchases never change."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.purchases: dict[str, dict[str, Any]] = {}
        self.updated_at: float = 0
        self.receipts_ok: bool | None = None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.purchases = {p["id"]: p for p in data.get("purchases", [])}
            self.updated_at = data.get("updated_at", 0)
            self.receipts_ok = data.get("receipts_ok")
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError) as err:
            _LOGGER.warning("Kon uitgaven niet lezen: %s", err)

    def ids(self, source: str | None = None) -> set[str]:
        return {k for k, p in self.purchases.items() if source is None or p["source"] == source}

    def merge(self, purchases: list[dict[str, Any]], today: date | None = None) -> int:
        """Add or update purchases; drop ones older than HISTORY_DAYS. Returns how many were new."""
        cutoff = ((today or date.today()) - timedelta(days=HISTORY_DAYS)).isoformat()
        new = 0
        for p in purchases:
            if p["id"] not in self.purchases:
                new += 1
            self.purchases[p["id"]] = {k: p[k] for k in ("id", "source", "date", "total")}
        self.purchases = {k: p for k, p in self.purchases.items() if p["date"] >= cutoff}
        return new

    def save(self, updated_at: float) -> None:
        self.updated_at = updated_at
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"updated_at": updated_at, "receipts_ok": self.receipts_ok,
                       "purchases": sorted(self.purchases.values(), key=lambda p: p["date"])}, fh)
        os.replace(tmp, self.path)

    def list(self) -> list[dict[str, Any]]:
        return list(self.purchases.values())


def aggregate(purchases: list[dict[str, Any]], period: str = "week", count: int = 12,
              today: date | None = None) -> list[dict[str, Any]]:
    """Buckets (oldest first) for the last `count` weeks (ISO, Monday) or calendar months."""
    today = today or date.today()
    starts: list[date] = []
    cur = week_start(today) if period == "week" else month_start(today)
    for _ in range(count):
        starts.append(cur)
        cur = cur - timedelta(days=7) if period == "week" else _prev_month(cur)
    starts.reverse()
    buckets = []
    for s in starts:
        if period == "week":
            end = s + timedelta(days=7)
            label = f"wk {s.isocalendar()[1]}"
        else:
            end = (s + timedelta(days=32)).replace(day=1)
            label = MONTHS[s.month - 1] + (f" '{s.year % 100:02d}" if s.month == 1 else "")
        buckets.append({"start": s.isoformat(), "end": (end - timedelta(days=1)).isoformat(), "label": label,
                        "online": 0.0, "winkel": 0.0, "total": 0.0, "count": 0, "_s": s, "_e": end})
    for p in purchases:
        d = _parse(p.get("date"))
        if not d:
            continue
        for b in buckets:
            if b["_s"] <= d < b["_e"]:
                b[p["source"]] = b.get(p["source"], 0.0) + float(p["total"])
                b["total"] += float(p["total"])
                b["count"] += 1
                break
    for b in buckets:
        del b["_s"], b["_e"]
        for k in ("online", "winkel", "total"):
            b[k] = round(b[k], 2)
    return buckets


def summary(purchases: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    weeks = aggregate(purchases, "week", 9, today)
    months = aggregate(purchases, "month", 2, today)
    this_w, last_w, this_m, last_m = weeks[-1], weeks[-2], months[-1], months[-2]
    full = weeks[:-1]  # last 8 complete weeks; empty weeks count
    return {
        "this_week": this_w["total"], "this_week_online": this_w["online"], "this_week_winkel": this_w["winkel"],
        "this_week_count": this_w["count"], "week_start": this_w["start"],
        "last_week": last_w["total"],
        "this_month": this_m["total"], "this_month_online": this_m["online"], "this_month_winkel": this_m["winkel"],
        "this_month_count": this_m["count"], "month_start": this_m["start"],
        "last_month": last_m["total"],
        "avg_week": round(sum(b["total"] for b in full) / len(full), 2) if full else 0.0,
    }


def budget_status(spent: float, list_cost: float | None, budget: float) -> dict[str, Any] | None:
    if not budget or budget <= 0:
        return None
    list_cost = round(list_cost or 0.0, 2)
    projected = round(spent + list_cost, 2)
    return {
        "budget": round(budget, 2), "spent": round(spent, 2), "list_cost": list_cost, "projected": projected,
        "remaining": round(budget - projected, 2), "over": projected > budget + 0.004,
    }
