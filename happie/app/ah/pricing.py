"""Line totals with AH bonus mechanisms (2 voor 3.99, 1+1 gratis, ...)."""
from __future__ import annotations

import re
from typing import Any


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def bonus_line(price: float | None, price_before: float | None, qty: int, mechanism: str | None,
               is_bonus: bool = True) -> dict[str, Any]:
    """Line total for `qty` units, applying the AH bonus mechanism.

    Returns {"total", "regular", "saving", "applied", "hint"}; hint says how many more
    units are needed for a multi-buy deal (e.g. "nog 1 voor 2 voor 3.99").
    """
    unit = price_before or price or 0.0
    regular = round(unit * qty, 2)
    out = {"total": regular, "regular": regular, "saving": 0.0, "applied": False, "hint": None}
    if not unit or qty <= 0:
        return out
    # the current price already contains a per-unit discount (e.g. "volume voordeel", "VOOR 1.99")
    if price and price_before and price < price_before - 0.001:
        out["total"] = round(price * qty, 2)
    elif is_bonus and mechanism:
        m = mechanism.strip().lower()
        total = None
        if mt := re.fullmatch(r"(\d+)\s*voor\s*(?:€\s*)?(\d+(?:[.,]\d+)?)", m):  # 2 voor 3.99
            n, deal = int(mt.group(1)), _num(mt.group(2))
            groups, rest = divmod(qty, n)
            total = groups * deal + rest * unit
            if rest and deal < n * unit:
                out["hint"] = f"nog {n - rest} voor {mechanism.strip()}"
        elif mt := re.fullmatch(r"(\d+)\s*\+\s*(\d+)\s*gratis", m):  # 2 + 1 gratis
            pay, free = int(mt.group(1)), int(mt.group(2))
            groups, rest = divmod(qty, pay + free)
            total = (qty - groups * free) * unit
            if rest >= pay:
                out["hint"] = f"nog {pay + free - rest} gratis meenemen"
            elif rest:
                out["hint"] = f"nog {pay + free - rest} voor {mechanism.strip()}"
        elif mt := re.fullmatch(r"(\d+)e\s*halve\s*prijs", m):  # 2e halve prijs
            n = int(mt.group(1))
            groups, rest = divmod(qty, n)
            total = qty * unit - groups * unit / 2
            if rest:
                out["hint"] = f"nog {n - rest} voor {mechanism.strip()}"
        elif mt := re.fullmatch(r"(\d+)e\s*gratis", m):  # 2e gratis
            n = int(mt.group(1))
            total = (qty - qty // n) * unit
            if qty % n:
                out["hint"] = f"nog {n - qty % n} voor {mechanism.strip()}"
        elif mt := re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*%\s*korting", m):  # 25% korting
            total = qty * unit * (1 - _num(mt.group(1)) / 100)
        elif mt := re.fullmatch(r"voor\s*(?:€\s*)?(\d+(?:[.,]\d+)?)", m):  # VOOR 1.99
            total = qty * _num(mt.group(1))
        elif mt := re.fullmatch(r"(?:€\s*)?(\d+(?:[.,]\d+)?)\s*(?:euro\s*)?korting", m):  # 1 euro korting
            total = qty * max(0.0, unit - _num(mt.group(1)))
        if total is not None:
            out["total"] = round(min(total, regular), 2)
    out["saving"] = round(regular - out["total"], 2)
    out["applied"] = out["saving"] > 0.004
    return out


def line_for(product: dict[str, Any] | None, qty: int) -> dict[str, Any] | None:
    if not product or not (product.get("price") or product.get("price_before")):
        return None
    return bonus_line(product.get("price"), product.get("price_before"), qty, product.get("bonus"),
                      bool(product.get("is_bonus")))
