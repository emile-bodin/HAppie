"""Minimal async client for the (unofficial) Albert Heijn mobile API.

The endpoints are reverse engineered from the AH mobile app; they are not
documented by AH and can change without notice.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

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


class AHError(Exception):
    """Error returned by the AH API."""


class AHAuthError(AHError):
    """Not logged in or token rejected."""


class AHOrderModeError(AHError):
    """HTTP 412 'Server in order mode': an online order is open for changes, the list is locked."""


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


class AHClient:
    def __init__(self, session: aiohttp.ClientSession, token_file: str) -> None:
        self._session = session
        self._token_file = token_file
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._anon_token: str | None = None
        self._anon_expires_at: float = 0
        self._load_tokens()

    # ------------------------------------------------------------------ auth
    @property
    def logged_in(self) -> bool:
        return bool(self._refresh_token or self._access_token)

    def _load_tokens(self) -> None:
        try:
            with open(self._token_file, encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as err:
            _LOGGER.warning("Kon tokens niet lezen: %s", err)
            return
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        self._expires_at = data.get("expires_at", 0)

    def _save_tokens(self) -> None:
        tmp = self._token_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                    "expires_at": self._expires_at,
                },
                fh,
            )
        os.replace(tmp, self._token_file)

    def _store_token_response(self, data: dict[str, Any]) -> None:
        self._access_token = data.get("access_token")
        # keep the previous refresh token if a new one isn't returned
        self._refresh_token = data.get("refresh_token") or self._refresh_token
        # refresh a minute early
        self._expires_at = time.time() + int(data.get("expires_in") or 0) - 60
        self._save_tokens()

    async def login_with_code(self, code_or_url: str) -> None:
        code = extract_code(code_or_url)
        if not code:
            raise AHAuthError("Geen code opgegeven")
        data = await self._raw(
            "POST",
            "/mobile-auth/v1/auth/token",
            json_body={"clientId": CLIENT_ID, "code": code},
            auth=False,
        )
        if not data or not data.get("access_token"):
            raise AHAuthError("AH gaf geen token terug; de code is mogelijk verlopen")
        self._store_token_response(data)

    def logout(self) -> None:
        self._access_token = self._refresh_token = None
        self._expires_at = 0
        try:
            os.remove(self._token_file)
        except FileNotFoundError:
            pass

    async def _refresh(self) -> None:
        if not self._refresh_token:
            raise AHAuthError("Niet ingelogd")
        try:
            data = await self._raw(
                "POST",
                "/mobile-auth/v1/auth/token/refresh",
                json_body={"clientId": CLIENT_ID, "refreshToken": self._refresh_token},
                auth=False,
            )
        except AHError as err:
            raise AHAuthError(f"Token vernieuwen mislukt: {err}") from err
        self._store_token_response(data)

    async def _user_token(self) -> str:
        if not self.logged_in:
            raise AHAuthError("Niet ingelogd bij Albert Heijn")
        if not self._access_token or time.time() >= self._expires_at:
            await self._refresh()
        return self._access_token  # type: ignore[return-value]

    async def _any_token(self) -> str:
        """User token if logged in, otherwise an anonymous token (search only)."""
        if self.logged_in:
            return await self._user_token()
        return await self._anonymous_token()

    async def _anonymous_token(self) -> str:
        if not self._anon_token or time.time() >= self._anon_expires_at:
            data = await self._raw(
                "POST",
                "/mobile-auth/v1/auth/token/anonymous",
                json_body={"clientId": CLIENT_ID},
                auth=False,
            )
            self._anon_token = data["access_token"]
            self._anon_expires_at = time.time() + int(data.get("expires_in") or 0) - 60
        return self._anon_token

    # ---------------------------------------------------------------- http
    async def _raw(
        self,
        method: str,
        path: str,
        *,
        params: Any = None,
        json_body: Any = None,
        auth: bool | str = True,
    ) -> Any:
        headers = {
            "User-Agent": USER_AGENT,
            "x-client-name": CLIENT_ID,
            "x-client-version": CLIENT_VERSION,
            "x-application": "AHWEBSHOP",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if auth == "any":
            headers["Authorization"] = f"Bearer {await self._any_token()}"
        elif auth:
            headers["Authorization"] = f"Bearer {await self._user_token()}"

        _LOGGER.debug("AH %s %s %s", method, path, json_body if json_body is not None else "")
        async with self._session.request(
            method,
            BASE_URL + path,
            params=params,
            json=json_body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            text = await resp.text()
            if resp.status in (401, 403) and auth is True:
                # force a refresh next time
                self._expires_at = 0
                raise AHAuthError(f"AH weigerde toegang ({resp.status})")
            if resp.status == 412 and "order mode" in text.lower():
                raise AHOrderModeError("Bestelling staat open voor wijzigingen (order mode)")
            if resp.status >= 400:
                msg = text[:300]
                try:
                    err = json.loads(text)
                    msg = err.get("message") or err.get("code") or msg
                except ValueError:
                    pass
                raise AHError(f"{resp.status}: {msg}")
            if not text:
                return None
            try:
                return json.loads(text)
            except ValueError:
                return text

    # ---------------------------------------------------------- shopping list
    async def get_list(self) -> list[ListItem]:
        data = await self._raw("GET", "/mobile-services/shoppinglist/v2/items")
        items: list[ListItem] = []
        for raw in (data or {}).get("items", []) if isinstance(data, dict) else data or []:
            details = ((raw.get("productDetails") or {}).get("product")) or {}
            product_id = raw.get("productId") or details.get("webshopId")
            name = raw.get("description") or details.get("title") or ""
            checked = bool(
                raw.get("strikedthrough", raw.get("strikeThrough", raw.get("strikethrough", False)))
            )
            if not name:
                continue
            items.append(
                ListItem(
                    name=name,
                    quantity=int(raw.get("quantity") or 1),
                    checked=checked,
                    product_id=int(product_id) if product_id else None,
                    raw=raw,
                )
            )
        return items

    @staticmethod
    def _item_body(name: str, product_id: int | None, quantity: int, checked: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "description": name,
            "quantity": quantity,
            "type": "SHOPPABLE",
            "strikeThrough": checked,
        }
        if product_id:
            body["productId"] = product_id
            body["originCode"] = "PRD"
            body["searchTerm"] = name
        else:
            body["originCode"] = "TXT"
        return body

    async def _patch(self, items: list[dict[str, Any]]) -> None:
        if items:
            await self._raw("PATCH", "/mobile-services/shoppinglist/v2/items", json_body={"items": items})

    async def add_item(
        self, name: str, product_id: int | None = None, quantity: int = 1, checked: bool = False
    ) -> None:
        await self._patch([self._item_body(name, product_id, quantity, checked)])

    async def set_checked(self, item: ListItem, checked: bool) -> None:
        await self._patch([self._item_body(item.name, item.product_id, item.quantity, checked)])

    async def set_quantity(self, item: ListItem, quantity: int) -> None:
        await self._patch([self._item_body(item.name, item.product_id, quantity, item.checked)])

    async def remove_items(self, items: list[ListItem]) -> None:
        await self._patch([self._item_body(i.name, i.product_id, 0, i.checked) for i in items])

    # ----------------------------------------------------------------- search
    async def search(self, query: str, size: int = 24) -> list[dict[str, Any]]:
        data = await self._raw(
            "GET",
            "/mobile-services/product/search/v2",
            params={"query": query, "page": 0, "size": size, "sortOn": "RELEVANCE"},
            auth="any",
        )
        return [parse_product(p) for p in (data or {}).get("products", [])]

    async def get_member(self) -> dict[str, Any]:
        """Account name of the logged in member."""
        data = await self._raw(
            "POST", "/graphql", json_body={"query": "query { member { id name { first last } } }"}
        )
        member = ((data or {}).get("data") or {}).get("member") or {}
        name = member.get("name") or {}
        return {
            "id": member.get("id"),
            "first_name": name.get("first"),
            "name": " ".join(p for p in (name.get("first"), name.get("last")) if p),
        }

    # ---------------------------------------------------------------- orders
    async def order_summaries(self) -> list[dict[str, Any]]:
        data = await self._raw("GET", "/mobile-services/order/v1/summaries", params={"sortBy": "DEFAULT"})
        if isinstance(data, dict):
            data = data.get("orders") or data.get("content") or []
        return data or []

    async def delivered_orders(self, n: int = 8) -> list[dict[str, Any]]:
        """Most recent delivered online orders (summaries), newest first."""
        return sorted(
            (o for o in await self.order_summaries() if str(o.get("state", "")).upper() in ("DELIVERED", "COMPLETED")),
            key=lambda o: o.get("deliveryDate") or "",
            reverse=True,
        )[:n]

    async def order_details(self, order_id: Any) -> dict[str, Any]:
        try:
            return await self._raw("GET", f"/mobile-services/order/v1/{order_id}/details-grouped-by-taxonomy") or {}
        except AHOrderModeError:
            raise
        except AHError as err:
            _LOGGER.debug("Bestelling %s ophalen mislukt: %s", order_id, err)
            return {}

    @staticmethod
    def raw_order_lines(details: dict[str, Any]) -> list[dict[str, Any]]:
        return [l for g in details.get("groupedProductsInTaxonomy") or [] for l in g.get("orderedProducts") or []]

    @staticmethod
    def line_quantity(line: dict[str, Any]) -> int:
        return int(line.get("allocatedQuantity") or line.get("quantity") or 0)

    async def order_lines(self, order_id: Any) -> list[dict[str, Any]]:
        """Products in an order: [{product (parsed), quantity}]."""
        details = await self.order_details(order_id)
        return [
            {"product": parse_product(l.get("product") or {}), "quantity": self.line_quantity(l),
             "ordered": int(l.get("amount") or l.get("quantity") or 0)}
            for l in self.raw_order_lines(details)
            if (l.get("product") or {}).get("webshopId")
        ]

    async def get_next_delivery(self) -> dict[str, Any] | None:
        """Next upcoming online order (delivery or pickup), or None."""
        summaries = await self.order_summaries()
        today = time.strftime("%Y-%m-%d")
        upcoming = [
            o for o in summaries
            if (o.get("deliveryDate") or "") >= today
            and str(o.get("state", "")).upper() not in ("DELIVERED", "CANCELLED", "CANCELED", "COMPLETED")
        ]
        if not upcoming:
            return None
        upcoming.sort(key=lambda o: o.get("deliveryDate") or "")
        order = upcoming[0]
        result: dict[str, Any] = {
            "order_id": order.get("orderId"),
            "state": order.get("state"),
            "date": order.get("deliveryDate"),
            "closing_time": order.get("closingTime"),
            "start": None, "end": None, "start_utc": None, "end_utc": None,
            "type": None, "total": None, "item_count": None,
            **parse_eta(order.get("trackTraceInfo")),
        }
        # the active order has the time window, total and products
        try:
            active = await self._raw(
                "GET", "/mobile-services/order/v1/summaries/active", params={"sortBy": "DEFAULT"}
            )
        except AHError:
            active = None
        if isinstance(active, dict) and active.get("id") == result["order_id"]:
            info = active.get("deliveryInformation") or {}
            products = active.get("orderedProducts") or []
            result.update(
                {
                    "type": active.get("shoppingType"),
                    "start": info.get("deliveryStartTime"),
                    "end": info.get("deliveryEndTime"),
                    "start_utc": info.get("deliveryUtcStartTime"),
                    "end_utc": info.get("deliveryUtcEndTime"),
                    "total": (active.get("totalPrice") or {}).get("priceTotalPayable"),
                    "item_count": sum(int(p.get("allocatedQuantity") or p.get("quantity") or 0) for p in products),
                    "product_count": len(products),
                }
            )
        else:
            # confirmed orders aren't "active"; the order details have the time window and products
            details = await self.order_details(result["order_id"])
            period = details.get("deliveryTimePeriod") or {}
            lines = self.raw_order_lines(details)
            if period:
                result.update(
                    {
                        "type": "PICKUP" if str(details.get("deliveryType", "")).upper() == "PICKUP" else "DELIVERY",
                        "start": (period.get("startDateTime") or "")[11:16] or None,
                        "end": (period.get("endDateTime") or "")[11:16] or None,
                        "start_utc": period.get("startTimeUtc"),
                        "end_utc": period.get("endTimeUtc"),
                    }
                )
            if lines:
                result["item_count"] = sum(self.line_quantity(l) for l in lines)
                result["product_count"] = len(lines)
        return result

    # -------------------------------------------------------------- spending
    @staticmethod
    def order_total(summary: dict[str, Any]) -> float | None:
        """Amount paid for an order, from its summary (orderTotalPrice.priceTotalPayable)."""
        price = summary.get("orderTotalPrice") or summary.get("totalPrice") or {}
        value = price.get("priceTotalPayable", price.get("priceAfterDiscount"))
        return float(value) if value is not None else None

    async def online_purchases(self) -> list[dict[str, Any]]:
        """Delivered online orders as purchases: [{id, source, date, total}]."""
        out = []
        for o in await self.order_summaries():
            if str(o.get("state", "")).upper() not in ("DELIVERED", "COMPLETED"):
                continue
            total = self.order_total(o)
            if total is None or not o.get("deliveryDate"):
                continue
            out.append({"id": f"order:{o.get('orderId')}", "source": "online",
                        "date": o["deliveryDate"][:10], "total": round(total, 2)})
        return out

    async def store_purchases(self, since: str, page_size: int = 50, max_pages: int = 20,
                              known: set[str] | None = None) -> list[dict[str, Any]]:
        """In-store receipts (kassabonnen) since `since` (YYYY-MM-DD), newest first.

        Stops early at a page that only holds receipts already in `known`.
        """
        query = (
            "query($offset: Int!, $limit: Int!) { posReceiptsPage(pagination: {offset: $offset, limit: $limit}) "
            "{ posReceipts { id dateTime totalAmount { amount } } } }"
        )
        out: list[dict[str, Any]] = []
        for page in range(max_pages):
            data = await self._raw("POST", "/graphql", json_body={
                "query": query, "variables": {"offset": page * page_size, "limit": page_size}})
            if isinstance(data, dict) and data.get("errors") and not data.get("data"):
                raise AHError(str(data["errors"][0].get("message")))
            receipts = (((data or {}).get("data") or {}).get("posReceiptsPage") or {}).get("posReceipts") or []
            done = not receipts
            new_on_page = 0
            for r in receipts:
                date = local_date(r.get("dateTime") or "")
                amount = (r.get("totalAmount") or {}).get("amount")
                if not date or amount is None:
                    continue
                if date < since:
                    done = True
                    continue
                rid = f"receipt:{r.get('id')}"
                if known is None or rid not in known:
                    new_on_page += 1
                out.append({"id": rid, "source": "winkel", "date": date, "total": round(float(amount), 2)})
            if done or len(receipts) < page_size or (known is not None and not new_on_page):
                break
        return out

    async def suggestions(self, basket_product_ids: list[int], limit: int = 12) -> list[dict[str, Any]]:
        """Personal 'Suggesties voor jou' (the app's don't-forget lane for the list).

        AH bases them on purchase history and adapts them to what's already on the list.
        """
        data = await self._raw(
            "POST",
            "/mobile-services/v2/recommendations/dontforgetlane",
            json_body={
                "positiveCmOnly": True,
                "offset": 0,
                "usecaseId": "app_mylist",
                "basketItems": [
                    {"quantity": 1, "position": n, "productId": pid}
                    for n, pid in enumerate(basket_product_ids, start=1)
                ],
                "limit": limit,
            },
        )
        return [parse_product(p) for p in (data or {}).get("productCards", [])]

    async def frequent_products(self, max_orders: int = 8, limit: int = 40) -> list[dict[str, Any]]:
        """Products you buy most often, aggregated from your last delivered online orders."""
        delivered = await self.delivered_orders(max_orders)
        orders = await asyncio.gather(*(self.order_details(o["orderId"]) for o in delivered))
        stats: dict[int, dict[str, Any]] = {}
        for order in orders:
            for line in self.raw_order_lines(order):
                p = line.get("product") or {}
                pid = p.get("webshopId")
                if not pid:
                    continue
                s = stats.setdefault(pid, {"times": 0, "quantity": 0, "last": "", "raw": p})
                s["times"] += 1
                s["quantity"] += self.line_quantity(line)
                s["last"] = max(s["last"], order.get("deliveryDate") or "")
        ranked = sorted(stats.items(), key=lambda kv: (-kv[1]["times"], -kv[1]["quantity"]))[:limit]
        # refresh price/bonus info, order history has stale prices
        fresh = {}
        try:
            fresh = {p["id"]: p for p in await self.products_by_id([pid for pid, _ in ranked])}
        except AHError:
            pass
        out = []
        for pid, s in ranked:
            product = fresh.get(pid) or parse_product(s["raw"])
            product.update({"times": s["times"], "orders": len(delivered), "last_bought": s["last"]})
            out.append(product)
        return out

    @staticmethod
    def _bonus_entries(data: Any) -> list[dict[str, Any]]:
        out = []
        for entry in (data or {}).get("bonusGroupOrProducts") or []:
            if entry.get("product"):
                out.append(parse_product(entry["product"]))
            elif entry.get("bonusGroup"):
                group = entry["bonusGroup"]
                for p in group.get("products") or []:
                    item = parse_product(p)
                    item["bonus"] = item.get("bonus") or group.get("discountDescription") or group.get("bonusMechanism")
                    item["is_bonus"] = True
                    out.append(item)
        return out

    async def bonus_for_you(self) -> dict[str, list[dict[str, Any]]]:
        """Personal bonus offers + previously bought products that are in the bonus now."""
        today = time.strftime("%Y-%m-%d")
        params = {"application": "AHWEBSHOP", "date": today}
        personal = await self._raw("GET", "/mobile-services/bonuspage/v2/section/personal", params=params)
        previous = await self._raw("GET", "/mobile-services/bonuspage/v2/section/previously-bought", params=params)
        return {"personal": self._bonus_entries(personal), "previously_bought": self._bonus_entries(previous)}

    async def product_by_gtin(self, gtin: str) -> dict[str, Any] | None:
        """Look up a product by its barcode (EAN/GTIN)."""
        gtin = re.sub(r"\D", "", gtin or "")
        if not gtin:
            return None
        try:
            data = await self._raw("GET", f"/mobile-services/product/search/v1/gtin/{gtin}", auth="any")
        except AHError as err:
            if str(err).startswith("404"):
                return None
            raise
        return parse_product(data) if isinstance(data, dict) and data.get("webshopId") else None

    async def products_by_id(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        params = [("ids", str(i)) for i in ids] + [("sortOn", "INPUT_PRODUCT_IDS")]
        data = await self._raw(
            "GET", "/mobile-services/product/search/v2/products", params=params, auth="any"
        )
        if isinstance(data, dict):
            data = data.get("products", [])
        return [parse_product(p) for p in data or []]
