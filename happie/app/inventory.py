"""Household stock (voorraad), stored as JSON in the add-on's data folder."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from ah_client import normalize


def clean_gtin(gtin: str | None) -> str:
    return re.sub(r"\D", "", gtin or "")


def product_key(product: dict[str, Any] | None = None, name: str | None = None) -> str:
    if product and product.get("id"):
        return f"p{int(product['id'])}"
    return "t:" + normalize(name or (product or {}).get("title") or "")


class Inventory:
    def __init__(self, path: str) -> None:
        self._path = path
        data: dict[str, Any] = {}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            pass
        self.items: dict[str, dict[str, Any]] = data.get("items", {})
        self.gtin_map: dict[str, str] = data.get("gtin_map", {})
        self.unpacked_orders: list[Any] = data.get("unpacked_orders", [])

    # ------------------------------------------------------------- storage
    def save(self) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"items": self.items, "gtin_map": self.gtin_map, "unpacked_orders": self.unpacked_orders[-50:]},
                fh,
            )
        os.replace(tmp, self._path)

    # ------------------------------------------------------------- queries
    def list(self) -> list[dict[str, Any]]:
        out = [{"key": k, **v} for k, v in self.items.items()]
        out.sort(key=lambda i: (i["quantity"] <= 0, (i.get("category") or "~").casefold(), i["name"].casefold()))
        return out

    def get(self, key: str) -> dict[str, Any] | None:
        item = self.items.get(key)
        return {"key": key, **item} if item else None

    def find_by_gtin(self, gtin: str) -> dict[str, Any] | None:
        key = self.gtin_map.get(clean_gtin(gtin))
        return self.get(key) if key else None

    # ----------------------------------------------------------- mutations
    def _ensure(self, product: dict[str, Any] | None, name: str | None) -> str:
        key = product_key(product, name)
        item = self.items.get(key)
        if item is None:
            p = product or {}
            item = self.items[key] = {
                "product_id": p.get("id"),
                "name": p.get("title") or (name or "").strip(),
                "quantity": 0,
                "image": p.get("image"),
                "category": p.get("category"),
                "unit_size": p.get("unit_size"),
                "gtins": [],
            }
        elif product:
            # refresh product details we may not have had before
            for field, src in (("image", "image"), ("category", "category"), ("unit_size", "unit_size")):
                if product.get(src) and not item.get(field):
                    item[field] = product[src]
        return key

    def _touch(self, key: str) -> None:
        self.items[key]["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    def adjust(self, delta: int, key: str | None = None, product: dict[str, Any] | None = None,
               name: str | None = None, gtin: str | None = None) -> dict[str, Any]:
        """Change stock by delta (never below 0). Creates the item when adding by product/name."""
        if key and key in self.items:
            pass
        elif product or name:
            key = self._ensure(product, name)
        else:
            raise KeyError("Onbekend voorraaditem")
        if gtin:
            self.link_gtin(gtin, key, save=False)
        item = self.items[key]
        before = item["quantity"]
        item["quantity"] = max(0, before + int(delta))
        self._touch(key)
        self.save()
        return {"key": key, "before": before, **item}

    def set(self, key: str, quantity: int) -> dict[str, Any]:
        if key not in self.items:
            raise KeyError("Onbekend voorraaditem")
        before = self.items[key]["quantity"]
        self.items[key]["quantity"] = max(0, int(quantity))
        self._touch(key)
        self.save()
        return {"key": key, "before": before, **self.items[key]}

    def remove(self, key: str) -> None:
        item = self.items.pop(key, None)
        if item:
            self.gtin_map = {g: k for g, k in self.gtin_map.items() if k != key}
            self.save()

    def link_gtin(self, gtin: str, key: str, save: bool = True) -> None:
        gtin = clean_gtin(gtin)
        if not gtin or key not in self.items:
            return
        self.gtin_map[gtin] = key
        gtins = self.items[key].setdefault("gtins", [])
        if gtin not in gtins:
            gtins.append(gtin)
        if save:
            self.save()

    def unpack(self, order_id: Any, lines: list[dict[str, Any]]) -> dict[str, Any]:
        """Add all lines of a delivered order. Idempotent per order."""
        if order_id in self.unpacked_orders:
            return {"added": 0, "products": 0, "already": True}
        added = 0
        for line in lines:
            qty = int(line.get("quantity") or 0)
            product = line.get("product") or {}
            if qty <= 0 or not product.get("id"):
                continue
            key = self._ensure(product, None)
            self.items[key]["quantity"] += qty
            self._touch(key)
            added += qty
        self.unpacked_orders.append(order_id)
        self.save()
        return {"added": added, "products": len([l for l in lines if (l.get("quantity") or 0) > 0]), "already": False}

    # -------------------------------------------------------------- summary
    def summary(self) -> dict[str, Any]:
        in_stock = [i for i in self.items.values() if i["quantity"] > 0]
        return {
            "products": len(in_stock),
            "total_units": sum(i["quantity"] for i in in_stock),
            "items": {i["name"]: i["quantity"] for i in sorted(in_stock, key=lambda i: i["name"].casefold())},
            "empty": sorted(i["name"] for i in self.items.values() if i["quantity"] <= 0),
        }
