"""AH API constants, the shopping list item and parsers for AH responses."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

BASE_URL = "https://api.ah.nl"

LOGIN_BASE_URL = "https://login.ah.nl"

CLIENT_ID = "appie-ios"

CLIENT_VERSION = "9.28"

USER_AGENT = f"Appie/{CLIENT_VERSION} (iPhone17,3; iPhone; CPU OS 26_1 like Mac OS X)"

REDIRECT_URI = "appie://login-exit"

LOGIN_URL = (
    f"{LOGIN_BASE_URL}/login?client_id={CLIENT_ID}"
    f"&response_type=code&redirect_uri={REDIRECT_URI}"
)


def normalize(name: str) -> str:
    """Key used to match items between AH and Home Assistant."""
    return re.sub(r"\s+", " ", (name or "").strip()).casefold()


def extract_code(text: str) -> str:
    """Accept either a raw code or the full appie://login-exit?code=... URL."""
    text = (text or "").strip()
    match = re.search(r"[?&]code=([^&\s]+)", text)
    return match.group(1) if match else text


@dataclass
class ListItem:
    name: str
    quantity: int = 1
    checked: bool = False
    product_id: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def key(self) -> str:
        return normalize(self.name)

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "quantity": self.quantity,
            "checked": self.checked,
            "product_id": self.product_id,
        }


def parse_eta(info: dict[str, Any] | None) -> dict[str, Any]:
    """Expected arrival from the order's track & trace info.

    AH sends e.g. {"state": "OUT_FOR_DELIVERY", "message": "Onze bezorger verwacht tussen 20:40 en 21:40 uur bij je te zijn."}
    """
    info = info or {}
    message = info.get("message") or None
    m = re.search(r"(\d{1,2}[:.]\d{2})\s*(?:en|tot|-|–)\s*(\d{1,2}[:.]\d{2})", message or "")
    fmt = lambda t: t.replace(".", ":").zfill(5)  # noqa: E731
    # a reserved but (nearly) empty slot: "Vul je bestelling aan tot €45 vóór zondag om 18:00. ..."
    fill = re.search(r"aan tot\s*€\s*(\d+(?:[.,]\d{1,2})?)", message or "")
    fill_by = re.search(r"om\s+(\d{1,2}[:.]\d{2})", message or "") if fill else None
    return {
        "eta_start": fmt(m.group(1)) if m else None,
        "eta_end": fmt(m.group(2)) if m else None,
        "eta_message": message,
        "track_state": info.get("state"),
        "min_order": float(fill.group(1).replace(",", ".")) if fill else None,
        "fill_by": fmt(fill_by.group(1)) if fill_by else None,
    }


def local_date(iso: str) -> str | None:
    """'2026-11-18T23:36:00.000Z' -> local (container TZ) date '2026-11-19'."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d")
    except ValueError:
        return iso[:10]


def parse_product(p: dict[str, Any]) -> dict[str, Any]:
    images = p.get("images") or []
    image = None
    if images:
        # pick a medium sized image
        images = sorted(images, key=lambda i: i.get("width") or 0)
        image = next((i["url"] for i in images if (i.get("width") or 0) >= 200), images[-1].get("url"))
    now = p.get("currentPrice") or p.get("priceBeforeBonus")
    bonus = p.get("bonusMechanism")
    if not bonus and p.get("discountLabels"):
        label = p["discountLabels"][0]
        bonus = label.get("defaultDescription") or label.get("description") if isinstance(label, dict) else str(label)
    return {
        "id": p.get("webshopId"),
        "title": p.get("title"),
        "brand": p.get("brand"),
        "unit_size": p.get("salesUnitSize"),
        "unit_price": p.get("unitPriceDescription"),
        "price": now,
        "price_before": p.get("priceBeforeBonus"),
        "is_bonus": bool(p.get("isBonus")),
        "bonus": bonus,
        "image": image,
        "orderable": p.get("isOrderable", True),
        "category": p.get("mainCategory"),
    }
