"""Inventory tests. Run: python tests/test_inventory.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))

from inventory import Inventory  # noqa: E402

path = os.path.join(tempfile.mkdtemp(), "inv.json")
inv = Inventory(path)
kip = {"id": 123, "title": "AH Kipfilet", "image": "img", "category": "Vlees", "unit_size": "300 g"}

# add by product, +1 / -1, never below 0
r = inv.adjust(2, product=kip)
assert r["key"] == "p123" and r["quantity"] == 2 and r["before"] == 0
assert inv.adjust(-1, key="p123")["quantity"] == 1
assert inv.adjust(-5, key="p123")["quantity"] == 0

# set
assert inv.set("p123", 4)["quantity"] == 4

# free text item, case-insensitive key
r = inv.adjust(1, name="Wc-papier")
assert r["key"] == "t:wc-papier"
assert inv.adjust(1, name="wc-papier ")["quantity"] == 2

# barcode linking (also for products AH doesn't know)
inv.adjust(1, name="Eigen jam", gtin="1234-5678")
assert inv.find_by_gtin("12345678")["name"] == "Eigen jam"
inv.link_gtin("8710000000001", "p123")
assert inv.find_by_gtin("8710000000001")["key"] == "p123"
assert "8710000000001" in inv.get("p123")["gtins"]

# unpack is idempotent per order
lines = [{"product": kip, "quantity": 2}, {"product": {"id": 9, "title": "Melk"}, "quantity": 3},
         {"product": {"id": 10, "title": "Weg"}, "quantity": 0}]
r = inv.unpack(555, lines)
assert r == {"added": 5, "products": 2, "already": False}, r
assert inv.get("p123")["quantity"] == 6 and inv.get("p9")["quantity"] == 3
assert inv.unpack(555, lines)["already"] and inv.get("p123")["quantity"] == 6

# persistence
inv2 = Inventory(path)
assert inv2.get("p9")["quantity"] == 3 and inv2.find_by_gtin("12345678") and 555 in inv2.unpacked_orders

# remove also drops barcode links
inv2.remove("t:eigen jam")
assert inv2.find_by_gtin("12345678") is None

# summary + ordering (empty items last)
inv2.set("t:wc-papier", 0)
s = inv2.summary()
assert s["products"] == 2 and s["total_units"] == 9 and s["empty"] == ["Wc-papier"], s
assert inv2.list()[-1]["key"] == "t:wc-papier"

try:
    inv2.adjust(1, key="nope")
    raise AssertionError("expected KeyError")
except KeyError:
    pass

print("all inventory tests passed")
