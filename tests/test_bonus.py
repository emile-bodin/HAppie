"""Bonus price calculation tests. Run: python tests/test_bonus.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))

from ah import bonus_line  # noqa: E402


def check(price, before, qty, mech, total, hint=None):
    r = bonus_line(price, before, qty, mech)
    assert abs(r["total"] - total) < 0.005, (mech, qty, r)
    if hint is not None:
        assert (r["hint"] or "") == hint, (mech, qty, r)
    return r


# multi-buy
check(2.99, 2.99, 2, "2 voor 3.99", 3.99)
check(2.99, 2.99, 1, "2 voor 3.99", 2.99, "nog 1 voor 2 voor 3.99")
check(2.99, 2.99, 3, "2 voor 3.99", 6.98, "nog 1 voor 2 voor 3.99")
check(2.29, 2.29, 3, "3 VOOR 5.00", 5.00)
# x + y gratis
check(1.99, 1.99, 3, "2 + 1 gratis", 3.98)
check(1.99, 1.99, 2, "2 + 1 gratis", 3.98, "nog 1 gratis meenemen")
check(1.99, 1.99, 6, "2 + 1 GRATIS", 7.96)
check(1.0, 1.0, 2, "1 + 1 gratis", 1.0)
# percentages / fixed
check(4.0, 4.0, 2, "25% korting", 6.0)
check(4.0, 4.0, 1, "VOOR 2.49", 2.49)
check(3.0, 3.0, 2, "1 euro korting", 4.0)
check(2.0, 2.0, 2, "2e Halve Prijs", 3.0)
check(2.0, 2.0, 3, "2e halve prijs", 5.0, "nog 1 voor 2e halve prijs")
# already discounted per unit (volume voordeel)
check(8.62, 9.96, 2, "13.5% volume voordeel", 17.24)
# unknown mechanism -> regular price
check(2.0, 2.0, 2, "pakketkorting", 4.0)
check(2.0, 2.0, 2, "ACTIE", 4.0)
# never more expensive than regular
check(1.0, 1.0, 2, "2 voor 3.00", 2.0)
r = check(2.99, 2.99, 2, "2 voor 3.99", 3.99)
assert r["saving"] == 1.99 and r["applied"]

print("all bonus tests passed")
