"""HAppie app: web UI (ingress) + AH <-> HA to-do sync."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web

from ah_client import LOGIN_URL, AHAuthError, AHClient, AHError, AHOrderModeError, bonus_line, normalize


def line_for(product: dict[str, Any] | None, qty: int) -> dict[str, Any] | None:
    if not product or not (product.get("price") or product.get("price_before")):
        return None
    return bonus_line(product.get("price"), product.get("price_before"), qty, product.get("bonus"),
                      bool(product.get("is_bonus")))
from ha_client import HAClient
from inventory import Inventory, clean_gtin, product_key
from spending import HISTORY_DAYS, SpendingStore, aggregate, budget_status, summary as spending_summary
from sync import SyncEngine

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATIC_DIR = Path(__file__).parent / "static"
INGRESS_IP = "172.30.32.2"
DELIVERY_SENSOR = "sensor.happie_volgende_bezorging"
DELIVERY_REFRESH = 300  # seconds
LIST_SENSOR = "sensor.happie_lijst_items"
COST_SENSOR = "sensor.happie_geschatte_kosten"
BONUS_SENSOR = "sensor.happie_bonus_items"
LOGIN_NOTIFICATION = "happie_login"
BONUS_NOTIFICATION = "happie_bonus"
BONUS_CHECK_INTERVAL = 3 * 3600
FREQUENT_TTL = 6 * 3600
BONUS_TTL = 3600
INVENTORY_SENSOR = "sensor.happie_voorraad"
SPEND_WEEK_SENSOR = "sensor.happie_uitgaven_week"
SPEND_MONTH_SENSOR = "sensor.happie_uitgaven_maand"
BUDGET_SENSOR = "binary_sensor.happie_boven_budget"
BUDGET_NOTIFICATION = "happie_budget"
SPENDING_REFRESH = 6 * 3600
ORDER_LINES_TTL = 300  # open orders can still change; delivered ones are cached for good
DONE_STATES = ("DELIVERED", "COMPLETED")
CANCELLED_STATES = ("CANCELLED", "CANCELED")

_LOGGER = logging.getLogger("happie")


def load_options() -> dict[str, Any]:
    defaults = {
        "todo_entity": "todo.boodschappen",
        "sync_interval": 60,
        "auto_match_products": False,
        "bonus_notifications": True,
        "notify_service": "",
        "week_budget": 0,
        "log_level": "info",
    }
    try:
        with open(DATA_DIR / "options.json", encoding="utf-8") as fh:
            defaults.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return defaults


@web.middleware
async def ingress_only(request: web.Request, handler):
    if os.environ.get("SUPERVISOR_TOKEN") and request.remote not in (INGRESS_IP, "127.0.0.1", "::1"):
        raise web.HTTPForbidden()
    return await handler(request)


@web.middleware
async def json_errors(request: web.Request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except AHAuthError as err:
        return web.json_response({"error": str(err), "auth": True}, status=401)
    except AHOrderModeError as err:
        return web.json_response({"error": str(err), "order_mode": True}, status=409)
    except AHError as err:
        return web.json_response({"error": f"Albert Heijn: {err}"}, status=502)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Fout bij %s", request.path)
        return web.json_response({"error": str(err)}, status=500)


class App:
    def __init__(self, session: aiohttp.ClientSession, options: dict[str, Any]) -> None:
        self.options = options
        self.ah = AHClient(session, str(DATA_DIR / "tokens.json"))
        self.ha = HAClient(session, options["todo_entity"]) if os.environ.get("SUPERVISOR_TOKEN") else None
        self.sync = SyncEngine(
            self.ah, self.ha, str(DATA_DIR / "sync_state.json"), options["auto_match_products"]
        )
        self._product_cache: dict[int, dict[str, Any]] = {}
        self._member: dict[str, Any] | None = None
        self._delivery: dict[str, Any] | None = None
        self._delivery_at: float = 0
        self._frequent: list[dict[str, Any]] | None = None
        self._frequent_at: float = 0
        self._bonus: dict[str, Any] | None = None
        self._bonus_at: float = 0
        self._bonus_checked_at: float = 0
        self._login_notified = False
        self._published: dict[str, Any] = {}
        self._sync_event = asyncio.Event()
        self.inventory = Inventory(str(DATA_DIR / "inventory.json"))
        self.inv_lock = asyncio.Lock()
        self.spending = SpendingStore(str(DATA_DIR / "spending.json"))
        self._spending_lock = asyncio.Lock()
        self._list_cost: float | None = None
        self._order_lines: dict[str, tuple[float, bool, list[dict[str, Any]]]] = {}
        self._spending_stale = False

    # -------------------------------------------------------- background
    def request_sync(self) -> None:
        self._sync_event.set()

    async def sync_loop(self) -> None:
        interval = int(self.options["sync_interval"])
        while True:
            try:
                await asyncio.wait_for(self._sync_event.wait(), timeout=interval)
                await asyncio.sleep(1.5)  # debounce bursts of changes
            except asyncio.TimeoutError:
                pass
            self._sync_event.clear()
            try:
                await self.sync.sync()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sync mislukt: %s", err)
            if self.ah.logged_in and time.time() - self._delivery_at > DELIVERY_REFRESH:
                try:
                    await self.refresh_delivery()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Bezorging ophalen mislukt: %s", err)
            if self.ah.logged_in and (self._spending_stale or time.time() - self.spending.updated_at > SPENDING_REFRESH):
                try:
                    await self.refresh_spending()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Uitgaven ophalen mislukt: %s", err)
            try:
                await self.after_sync()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sensoren/meldingen bijwerken mislukt: %s", err)

    # ------------------------------------------------ sensors + notifications
    async def after_sync(self) -> None:
        if not self.ha:
            return
        await self.check_login_notification()
        if self.sync.last_exc is None and not self.sync.order_mode and self.sync.last_items is not None:
            await self.publish_list_sensors(self.sync.last_items)
        if self.spending.updated_at:
            await self.publish_spending_sensors()
            if self._list_cost is not None:
                await self.check_budget_notification()
        if (
            self.options.get("bonus_notifications")
            and self.ah.logged_in
            and self.sync.last_exc is None
            and time.time() - self._bonus_checked_at > BONUS_CHECK_INTERVAL
        ):
            self._bonus_checked_at = time.time()
            await self.check_bonus_notifications()

    async def check_login_notification(self) -> None:
        expired = self.ah.logged_in and isinstance(self.sync.last_exc, AHAuthError)
        if expired and not self._login_notified:
            _LOGGER.warning("AH-sessie verlopen; melding gestuurd")
            await self.ha.notify(
                "HAppie: opnieuw inloggen bij AH",
                "Je Albert Heijn-sessie is verlopen, daardoor staat de sync van je boodschappenlijst stil. "
                "Open **HAppie** in de zijbalk en log opnieuw in.",
                LOGIN_NOTIFICATION,
                self.options.get("notify_service", ""),
            )
            self._login_notified = True
        elif not expired and self._login_notified:
            await self.ha.dismiss(LOGIN_NOTIFICATION)
            self._login_notified = False

    async def _ensure_products(self, ids: list[int]) -> None:
        missing = [i for i in ids if i and i not in self._product_cache]
        for start in range(0, len(missing), 50):
            try:
                for p in await self.ah.products_by_id(missing[start:start + 50]):
                    if p.get("id"):
                        self._product_cache[int(p["id"])] = p
            except AHError as err:
                _LOGGER.debug("Productinfo ophalen mislukt: %s", err)

    async def _set_state_if_changed(self, entity_id: str, state: Any, attrs: dict[str, Any]) -> None:
        key = json.dumps([state, attrs], sort_keys=True, default=str)
        if self._published.get(entity_id) == key:
            return
        await self.ha.set_state(entity_id, str(state), attrs)
        self._published[entity_id] = key

    async def list_totals(self, items) -> tuple[float, float, int, list[str]]:
        """(estimated cost incl. bonus, bonus saving, items without price, bonus items) of the open items."""
        await self._ensure_products([i.product_id for i in items if i.product_id])
        cost, saving, unknown, bonus = 0.0, 0.0, 0, []
        for i in items:
            if i.checked:
                continue
            p = self._product_cache.get(i.product_id) if i.product_id else None
            line = line_for(p, i.quantity)
            if line:
                cost += line["total"]
                saving += line["saving"]
            else:
                unknown += 1
            if p and p.get("is_bonus"):
                bonus.append(f"{i.name} ({p.get('bonus') or 'bonus'})")
        return round(cost, 2), round(saving, 2), unknown, bonus

    async def publish_list_sensors(self, items) -> None:
        open_items = [i for i in items if not i.checked]
        cost, saving, unknown, bonus = await self.list_totals(items)
        self._list_cost = cost
        await self._set_state_if_changed(
            LIST_SENSOR,
            len(open_items),
            {
                "friendly_name": "AH boodschappenlijst",
                "icon": "mdi:cart-outline",
                "unit_of_measurement": "items",
                "state_class": "measurement",
                "items": [f"{i.quantity}× {i.name}" if i.quantity > 1 else i.name for i in open_items],
                "checked": len(items) - len(open_items),
                "total": len(items),
            },
        )
        await self._set_state_if_changed(
            COST_SENSOR,
            round(cost, 2),
            {
                "friendly_name": "AH geschatte kosten",
                "icon": "mdi:currency-eur",
                "unit_of_measurement": "EUR",
                "device_class": "monetary",
                "items_without_price": unknown,
                "bonus_saving": round(saving, 2),
            },
        )
        await self._set_state_if_changed(
            BONUS_SENSOR,
            len(bonus),
            {
                "friendly_name": "AH bonusitems op lijst",
                "icon": "mdi:sale",
                "unit_of_measurement": "items",
                "products": bonus,
            },
        )

    async def get_frequent(self, refresh: bool = False) -> list[dict[str, Any]]:
        if refresh or self._frequent is None or time.time() - self._frequent_at > FREQUENT_TTL:
            self._frequent = await self.ah.frequent_products()
            self._frequent_at = time.time()
        return self._frequent

    async def get_bonus(self, refresh: bool = False) -> dict[str, Any]:
        if refresh or self._bonus is None or time.time() - self._bonus_at > BONUS_TTL:
            self._bonus = await self.ah.bonus_for_you()
            self._bonus_at = time.time()
        return self._bonus

    async def check_bonus_notifications(self) -> None:
        """Notify (once per offer) when something on the list or a frequent buy is in the bonus."""
        candidates: dict[int, tuple[dict[str, Any], str]] = {}
        for i in self.sync.last_items or []:
            p = self._product_cache.get(i.product_id) if i.product_id else None
            if p and p.get("is_bonus") and not i.checked:
                candidates[p["id"]] = (p, "op je lijst")
        try:
            for p in (await self.get_frequent())[:25]:
                if p.get("is_bonus") and p.get("id") not in candidates:
                    candidates[p["id"]] = (p, f"koop je vaak ({p.get('times')}× in {p.get('orders')} bestellingen)")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Vaak gekocht ophalen mislukt: %s", err)

        path = DATA_DIR / "notified_bonus.json"
        try:
            notified: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            notified = {}
        current = {f"{pid}:{p.get('bonus') or ''}": (p, why) for pid, (p, why) in candidates.items()}
        new = [(p, why) for key, (p, why) in current.items() if key not in notified]
        # forget offers that ended, so they notify again next time they come back
        notified = {k: v for k, v in notified.items() if k in current}
        for key in current:
            notified.setdefault(key, time.strftime("%Y-%m-%d"))
        path.write_text(json.dumps(notified), encoding="utf-8")
        if not new:
            return
        lines = [f"- **{p['title']}**: {p.get('bonus') or 'in de bonus'} · {why}" for p, why in new[:15]]
        if len(new) > 15:
            lines.append(f"- … en nog {len(new) - 15}")
        _LOGGER.info("Bonusmelding voor %d producten", len(new))
        await self.ha.notify(
            "AH-bonus voor jou",
            "Nieuw in de bonus:\n" + "\n".join(lines),
            BONUS_NOTIFICATION,
            self.options.get("notify_service", ""),
        )

    # ------------------------------------------------------------ spending
    async def refresh_spending(self) -> None:
        """Fetch delivered online orders + in-store receipts and update the cache."""
        async with self._spending_lock:
            today = date.today()
            purchases = await self.ah.online_purchases()
            try:
                since = (today - timedelta(days=HISTORY_DAYS)).isoformat()
                purchases += await self.ah.store_purchases(since, known=self.spending.ids("winkel") or None)
                self.spending.receipts_ok = True
            except AHAuthError:
                raise
            except AHError as err:
                _LOGGER.warning("Kassabonnen ophalen mislukt: %s", err)
                self.spending.receipts_ok = False
            new = self.spending.merge(purchases, today)
            self._spending_stale = False
            self.spending.save(time.time())
            if new:
                _LOGGER.info("Uitgaven bijgewerkt: %d nieuwe aankopen", new)

    def spending_overview(self) -> dict[str, Any]:
        s = spending_summary(self.spending.list())
        s["budget"] = budget_status(s["this_week"], self._list_cost, float(self.options.get("week_budget") or 0))
        return s

    @staticmethod
    def _period_start(day: str) -> str:
        return datetime.fromisoformat(day).astimezone().isoformat()

    async def publish_spending_sensors(self) -> None:
        s = self.spending_overview()
        b = s["budget"]
        common = {"unit_of_measurement": "EUR", "device_class": "monetary", "state_class": "total",
                  "icon": "mdi:cash-register"}
        await self._set_state_if_changed(SPEND_WEEK_SENSOR, s["this_week"], {
            **common, "friendly_name": "AH uitgaven deze week", "last_reset": self._period_start(s["week_start"]),
            "online": s["this_week_online"], "winkel": s["this_week_winkel"], "purchases": s["this_week_count"],
            "previous": s["last_week"], "avg_week": s["avg_week"],
            **({"budget": b["budget"], "budget_remaining": b["remaining"]} if b else {}),
        })
        await self._set_state_if_changed(SPEND_MONTH_SENSOR, s["this_month"], {
            **common, "friendly_name": "AH uitgaven deze maand", "last_reset": self._period_start(s["month_start"]),
            "online": s["this_month_online"], "winkel": s["this_month_winkel"], "purchases": s["this_month_count"],
            "previous": s["last_month"],
        })
        if b:
            await self._set_state_if_changed(BUDGET_SENSOR, "on" if b["over"] else "off", {
                "friendly_name": "AH boven weekbudget", "icon": "mdi:wallet-outline", "device_class": "problem", **b,
            })

    async def check_budget_notification(self) -> None:
        """Notify once per week when spent this week + the list goes over the week budget."""
        b = self.spending_overview()["budget"]
        path = DATA_DIR / "notified_budget.json"
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        iso = date.today().isocalendar()
        week = f"{iso[0]}-W{iso[1]:02d}"
        if b and b["over"]:
            if state.get("week") == week and state.get("active"):
                return
            if state.get("week") != week:
                _LOGGER.info("Weekbudget overschreden (%.2f van %.2f); melding gestuurd", b["projected"], b["budget"])
                await self.ha.notify(
                    "AH: boven je weekbudget",
                    f"Deze week al **€ {b['spent']:.2f}** uitgegeven. Met je lijst erbij (€ {b['list_cost']:.2f}) "
                    f"kom je op **€ {b['projected']:.2f}**, € {-b['remaining']:.2f} boven je weekbudget van € {b['budget']:.2f}.",
                    BUDGET_NOTIFICATION,
                    self.options.get("notify_service", ""),
                )
            state = {"week": week, "active": True}
        elif state.get("active"):
            await self.ha.dismiss(BUDGET_NOTIFICATION)
            state = {**state, "active": False}
        else:
            return
        path.write_text(json.dumps(state), encoding="utf-8")

    async def spending_api(self, request: web.Request) -> web.Response:
        period = "month" if request.query.get("period") == "month" else "week"
        if self.ah.logged_in and (request.query.get("refresh") or not self.spending.updated_at):
            await self.refresh_spending()
        if self._list_cost is None and self.sync.last_items is not None:
            self._list_cost = (await self.list_totals(self.sync.last_items))[0]
        purchases = self.spending.list()
        sensors = [SPEND_WEEK_SENSOR, SPEND_MONTH_SENSOR] + ([BUDGET_SENSOR] if self.options.get("week_budget") else [])
        return web.json_response({
            "period": period,
            "buckets": aggregate(purchases, period, 12),
            "summary": self.spending_overview(),
            "receipts_ok": self.spending.receipts_ok,
            "updated_at": self.spending.updated_at or None,
            "recent": sorted(purchases, key=lambda p: p["date"], reverse=True)[:8],
            "sensors": sensors if self.ha else [],
        })

    @staticmethod
    def _local_iso(day: str | None, hhmm: str | None) -> str | None:
        """'2026-11-23' + '20:40' -> '2026-11-23T20:40:00+01:00' (local time zone)."""
        if not day or not hhmm:
            return None
        try:
            return datetime.fromisoformat(f"{day}T{hhmm}").astimezone().isoformat()
        except ValueError:
            return None

    async def refresh_delivery(self) -> dict[str, Any] | None:
        previous = (self._delivery or {}).get("order_id")
        self._delivery = await self.ah.get_next_delivery()
        if previous and previous != (self._delivery or {}).get("order_id"):
            self._spending_stale = True  # the previous order was delivered: fetch spending again
        self._delivery_at = time.time()
        if self.ha:
            d = self._delivery
            attrs: dict[str, Any] = {
                "friendly_name": "AH volgende bezorging",
                "icon": "mdi:truck-delivery",
                "device_class": "timestamp",
            }
            if d:
                attrs.update(
                    {
                        "date": d.get("date"),
                        "window": f"{d['start']}–{d['end']}" if d.get("start") else None,
                        "end": d.get("end_utc"),
                        "closing_time": d.get("closing_time"),
                        "order_state": d.get("state"),
                        "order_type": d.get("type"),
                        "total": d.get("total"),
                        "item_count": d.get("item_count"),
                        "eta_window": f"{d['eta_start']}–{d['eta_end']}" if d.get("eta_start") else None,
                        "eta_start": self._local_iso(d.get("date"), d.get("eta_start")),
                        "eta_end": self._local_iso(d.get("date"), d.get("eta_end")),
                        "eta_message": d.get("eta_message"),
                        "min_order": d.get("min_order"),
                    }
                )
                try:
                    lines = await self.get_order_lines(d["order_id"])
                    attrs["products"] = [
                        f"{l['quantity']}× {l['product'].get('title')}" if l["quantity"] > 1 else l["product"].get("title")
                        for l in lines[:100]
                    ]
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Producten van bestelling ophalen mislukt: %s", err)
            state = (d or {}).get("start_utc") or ((d or {}).get("date") and f"{d['date']}T00:00:00+01:00") or "unknown"
            try:
                await self.ha.set_state(DELIVERY_SENSOR, state, attrs)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Sensor %s bijwerken mislukt: %s", DELIVERY_SENSOR, err)
        return self._delivery

    # ------------------------------------------------------------ orders
    async def get_order_lines(self, order_id: Any, done: bool = False, refresh: bool = False) -> list[dict[str, Any]]:
        key = str(order_id)
        cached = self._order_lines.get(key)
        if cached and not refresh and (cached[1] or time.time() - cached[0] < ORDER_LINES_TTL):
            return cached[2]
        lines = await self.ah.order_lines(order_id)
        self._order_lines[key] = (time.time(), done, lines)
        for line in lines:
            if line["product"].get("id"):
                self._product_cache.setdefault(int(line["product"]["id"]), line["product"])
        return lines

    def _order_row(self, o: dict[str, Any]) -> dict[str, Any]:
        price = o.get("orderTotalPrice") or {}
        state = str(o.get("state", "")).upper()
        return {
            "order_id": o.get("orderId"),
            "date": o.get("deliveryDate"),
            "state": state,
            "done": state in DONE_STATES,
            "total": self.ah.order_total(o),
            "discount": price.get("priceDiscount"),
            "unpacked": str(o.get("orderId")) in {str(x) for x in self.inventory.unpacked_orders},
        }

    async def orders(self, request: web.Request) -> web.Response:
        """Upcoming orders (soonest first) and the last delivered ones (newest first)."""
        summaries = await self.ah.order_summaries()
        today = date.today().isoformat()
        upcoming = sorted(
            (o for o in summaries
             if (o.get("deliveryDate") or "") >= today
             and str(o.get("state", "")).upper() not in DONE_STATES + CANCELLED_STATES),
            key=lambda o: o.get("deliveryDate") or "",
        )[:4]
        done = sorted(
            (o for o in summaries if str(o.get("state", "")).upper() in DONE_STATES),
            key=lambda o: o.get("deliveryDate") or "", reverse=True,
        )[:6]
        return web.json_response({"orders": [self._order_row(o) for o in upcoming + done]})

    async def order(self, request: web.Request) -> web.Response:
        order_id = request.match_info["order_id"]
        done = request.query.get("done") == "1"
        lines = await self.get_order_lines(order_id, done, bool(request.query.get("refresh")))
        on_list = {i.product_id: i.quantity for i in (self.sync.last_items or []) if i.product_id and not i.checked}
        out = []
        for l in lines:
            p = l["product"]
            out.append({
                "product": p,
                "quantity": l["quantity"],
                "ordered": l.get("ordered") or l["quantity"],
                "line": line_for(p, l["quantity"]),
                "on_list": on_list.get(p.get("id")),
            })
        return web.json_response({
            "order_id": order_id,
            "lines": out,
            "items": sum(l["quantity"] for l in out),
            "unpacked": str(order_id) in {str(x) for x in self.inventory.unpacked_orders},
        })

    async def run_sync_now(self) -> None:
        try:
            await self.sync.sync()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Sync mislukt: %s", err)

    # ------------------------------------------------------------ routes
    async def index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    async def status(self, request: web.Request) -> web.Response:
        todo_exists = None
        if self.ha:
            try:
                todo_exists = await self.ha.entity_exists()
            except Exception:  # noqa: BLE001
                todo_exists = None
        # login state: "logged_out" | "ok" | "expired" (token no longer accepted) | "unknown"
        account_state = "logged_out"
        if self.ah.logged_in:
            account_state = "ok"
            if self._member is None:
                try:
                    self._member = await self.ah.get_member()
                except AHAuthError:
                    account_state = "expired"
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Accountnaam ophalen mislukt: %s", err)
                    account_state = "unknown"
            if isinstance(self.sync.last_exc, AHAuthError):
                account_state = "expired"
        return web.json_response(
            {
                "logged_in": self.ah.logged_in,
                "account_state": account_state,
                "account": self._member if self.ah.logged_in else None,
                "login_url": LOGIN_URL,
                "todo_entity": self.options["todo_entity"],
                "ha_connected": self.ha is not None,
                "todo_exists": todo_exists,
                "last_sync": self.sync.last_sync,
                "last_error": self.sync.last_error,
                "warnings": self.sync.warnings,
                "order_mode": self.sync.order_mode,
                "auto_match": self.options["auto_match_products"],
            }
        )

    async def login(self, request: web.Request) -> web.Response:
        body = await request.json()
        await self.ah.login_with_code(body.get("code", ""))
        await self._after_login()
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def _after_login(self) -> None:
        self._member = None
        self._frequent = self._bonus = None
        if self.ha and self._login_notified:
            try:
                await self.ha.dismiss(LOGIN_NOTIFICATION)
            except Exception:  # noqa: BLE001
                pass
            self._login_notified = False
        # First sync after login merges both lists.
        self.sync.reset()

    async def logout(self, request: web.Request) -> web.Response:
        self.ah.logout()
        self._member = None
        self.sync.reset()
        return web.json_response({"ok": True})

    async def _enrich(self, items: list[dict[str, Any]]) -> None:
        await self._ensure_products([i["product_id"] for i in items if i["product_id"]])
        for i in items:
            i["product"] = self._product_cache.get(i["product_id"]) if i["product_id"] else None
            i["line"] = line_for(i["product"], i["quantity"])

    async def get_list(self, request: web.Request) -> web.Response:
        items = [i.to_json() for i in await self.ah.get_list()]
        await self._enrich(items)
        items.sort(key=lambda i: (i["checked"], (i["product"] or {}).get("category") or "~", i["name"].casefold()))
        return web.json_response({"items": items})

    async def _find(self, key: str):
        for item in await self.ah.get_list():
            if item.key == key:
                return item
        raise web.HTTPNotFound(text=json.dumps({"error": "Item niet gevonden"}), content_type="application/json")

    async def add_to_list(self, name: str, product_id: Any = None, quantity: int = 1) -> None:
        name = (name or "").strip()
        if not name:
            raise web.HTTPBadRequest(text='{"error":"Naam ontbreekt"}', content_type="application/json")
        async with self.sync.lock:
            existing = {i.key: i for i in await self.ah.get_list()}.get(normalize(name))
            if existing and not existing.checked:
                await self.ah.set_quantity(existing, existing.quantity + quantity)
            else:
                await self.ah.add_item(name, int(product_id) if product_id else None, quantity)
        await self.run_sync_now()

    async def add(self, request: web.Request) -> web.Response:
        body = await request.json()
        await self.add_to_list(body.get("name"), body.get("product_id"), max(1, int(body.get("quantity") or 1)))
        return web.json_response({"ok": True})

    # ------------------------------------------------------------ voorraad
    def _inv_item(self, item: dict[str, Any] | None) -> dict[str, Any] | None:
        if item and item.get("product_id"):
            p = self._product_cache.get(int(item["product_id"]))
            if p:
                item = {**item, "price": p.get("price"), "is_bonus": p.get("is_bonus"), "bonus": p.get("bonus"),
                        "image": item.get("image") or p.get("image")}
        return item

    async def publish_inventory_sensor(self) -> None:
        if not self.ha:
            return
        s = self.inventory.summary()
        try:
            await self._set_state_if_changed(
                INVENTORY_SENSOR,
                s["products"],
                {
                    "friendly_name": "Voorraad",
                    "icon": "mdi:fridge-outline",
                    "unit_of_measurement": "producten",
                    "items": s["items"],
                    "total_units": s["total_units"],
                    "empty": s["empty"],
                },
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Sensor %s bijwerken mislukt: %s", INVENTORY_SENSOR, err)

    async def _inv_changed(self, result: Any) -> web.Response:
        await self.publish_inventory_sensor()
        return web.json_response({"ok": True, "item": self._inv_item(result) if isinstance(result, dict) else None})

    async def inv_list(self, request: web.Request) -> web.Response:
        items = self.inventory.list()
        await self._ensure_products([int(i["product_id"]) for i in items if i.get("product_id")])
        return web.json_response({"items": [self._inv_item(i) for i in items], "summary": self.inventory.summary()})

    async def inv_adjust(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.inv_lock:
            try:
                result = self.inventory.adjust(
                    int(body.get("delta", 1)), key=body.get("key"), product=body.get("product"),
                    name=body.get("name"), gtin=body.get("gtin"),
                )
            except KeyError as err:
                raise web.HTTPNotFound(text=json.dumps({"error": str(err.args[0])}), content_type="application/json")
        return await self._inv_changed(result)

    async def inv_set(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.inv_lock:
            try:
                result = self.inventory.set(body["key"], int(body.get("quantity") or 0))
            except KeyError as err:
                raise web.HTTPNotFound(text=json.dumps({"error": str(err.args[0])}), content_type="application/json")
        return await self._inv_changed(result)

    async def inv_remove(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.inv_lock:
            self.inventory.remove(body["key"])
        return await self._inv_changed(None)

    async def inv_scan(self, request: web.Request) -> web.Response:
        gtin = clean_gtin(request.match_info["gtin"])
        local = self.inventory.find_by_gtin(gtin)
        if local:
            return web.json_response({"gtin": gtin, "item": self._inv_item(local), "product": None, "source": "local"})
        product = await self.ah.product_by_gtin(gtin)
        if product and product.get("id"):
            self._product_cache[int(product["id"])] = product
            existing = self.inventory.get(product_key(product))
            if existing:  # known product, new barcode: remember it
                async with self.inv_lock:
                    self.inventory.link_gtin(gtin, existing["key"])
            return web.json_response({"gtin": gtin, "item": self._inv_item(existing), "product": product, "source": "ah"})
        return web.json_response({"gtin": gtin, "item": None, "product": None, "source": None})

    async def inv_link(self, request: web.Request) -> web.Response:
        """Link an unknown barcode to a name or product and add it (quantity delta, default +1)."""
        body = await request.json()
        if not (body.get("name") or body.get("product")) or not clean_gtin(body.get("gtin")):
            raise web.HTTPBadRequest(text='{"error":"Barcode en naam of product nodig"}', content_type="application/json")
        async with self.inv_lock:
            result = self.inventory.adjust(
                int(body.get("delta", 1)), product=body.get("product"), name=body.get("name"), gtin=body["gtin"]
            )
        return await self._inv_changed(result)

    async def inv_orders(self, request: web.Request) -> web.Response:
        orders = await self.ah.delivered_orders(5)
        lines = await asyncio.gather(*(self.ah.order_lines(o["orderId"]) for o in orders))
        return web.json_response(
            {
                "orders": [
                    {
                        "order_id": o["orderId"],
                        "date": o.get("deliveryDate"),
                        "products": len(ls),
                        "items": sum(l["quantity"] for l in ls),
                        "unpacked": o["orderId"] in self.inventory.unpacked_orders,
                    }
                    for o, ls in zip(orders, lines)
                ]
            }
        )

    async def inv_unpack(self, request: web.Request) -> web.Response:
        body = await request.json()
        order_id = body["order_id"]
        lines = await self.ah.order_lines(order_id)
        if not lines:
            raise web.HTTPNotFound(text='{"error":"Geen producten gevonden in deze bestelling"}', content_type="application/json")
        for line in lines:
            if line["product"].get("id"):
                self._product_cache.setdefault(int(line["product"]["id"]), line["product"])
        async with self.inv_lock:
            result = self.inventory.unpack(order_id, lines)
        await self.publish_inventory_sensor()
        return web.json_response({"ok": True, **result})

    async def inv_to_list(self, request: web.Request) -> web.Response:
        body = await request.json()
        item = self.inventory.get(body["key"])
        if not item:
            raise web.HTTPNotFound(text='{"error":"Onbekend voorraaditem"}', content_type="application/json")
        await self.add_to_list(item["name"], item.get("product_id"), 1)
        return web.json_response({"ok": True})

    async def check(self, request: web.Request) -> web.Response:
        body = await request.json()
        async with self.sync.lock:
            item = await self._find(body["key"])
            await self.ah.set_checked(item, bool(body.get("checked")))
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def quantity(self, request: web.Request) -> web.Response:
        body = await request.json()
        qty = int(body.get("quantity") or 0)
        async with self.sync.lock:
            item = await self._find(body["key"])
            if qty <= 0:
                await self.ah.remove_items([item])
            else:
                await self.ah.set_quantity(item, qty)
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def remove(self, request: web.Request) -> web.Response:
        body = await request.json()
        keys = set(body.get("keys") or [body.get("key")])
        async with self.sync.lock:
            items = [i for i in await self.ah.get_list() if i.key in keys]
            await self.ah.remove_items(items)
        await self.run_sync_now()
        return web.json_response({"ok": True})

    async def search(self, request: web.Request) -> web.Response:
        q = request.query.get("q", "").strip()
        if not q:
            return web.json_response({"products": []})
        products = await self.ah.search(q)
        for p in products:
            if p.get("id"):
                self._product_cache[int(p["id"])] = p
        return web.json_response({"products": products})

    async def suggestions(self, request: web.Request) -> web.Response:
        try:
            items = await self.ah.get_list()
        except AHOrderModeError:
            items = []
        on_list = {i.product_id for i in items if i.product_id}
        products = await self.ah.suggestions([pid for pid in on_list], limit=16)
        products = [p for p in products if p.get("id") not in on_list][:12]
        for p in products:
            if p.get("id"):
                self._product_cache[int(p["id"])] = p
        return web.json_response({"products": products})

    async def _on_list_ids(self) -> set[int]:
        try:
            return {i.product_id for i in await self.ah.get_list() if i.product_id}
        except AHOrderModeError:
            return set()

    async def frequent(self, request: web.Request) -> web.Response:
        products = await self.get_frequent(bool(request.query.get("refresh")))
        on_list = await self._on_list_ids()
        return web.json_response({"products": [{**p, "on_list": p.get("id") in on_list} for p in products]})

    async def bonus(self, request: web.Request) -> web.Response:
        data = await self.get_bonus(bool(request.query.get("refresh")))
        on_list = await self._on_list_ids()
        mark = lambda ps: [{**p, "on_list": p.get("id") in on_list} for p in ps]  # noqa: E731
        return web.json_response({"personal": mark(data["personal"]), "previously_bought": mark(data["previously_bought"])})

    async def barcode(self, request: web.Request) -> web.Response:
        product = await self.ah.product_by_gtin(request.match_info["gtin"])
        if product and product.get("id"):
            self._product_cache[int(product["id"])] = product
        return web.json_response({"product": product})

    async def delivery(self, request: web.Request) -> web.Response:
        if request.query.get("refresh") or time.time() - self._delivery_at > DELIVERY_REFRESH:
            await self.refresh_delivery()
        return web.json_response({"delivery": self._delivery, "sensor": DELIVERY_SENSOR if self.ha else None})

    async def sync_now(self, request: web.Request) -> web.Response:
        await self.sync.sync()
        return web.json_response({"ok": True, "last_sync": self.sync.last_sync})


async def main() -> None:
    options = load_options()
    logging.basicConfig(
        level=getattr(logging, str(options["log_level"]).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        app = App(session, options)
        if os.environ.get("HAPPIE_MOCK"):
            from mock import install_mocks

            # HAPPIE_MOCK=ah -> only fake the AH list, talk to a real HA
            install_mocks(app, mock_ha=os.environ["HAPPIE_MOCK"] != "ah")

        web_app = web.Application(middlewares=[ingress_only, json_errors])
        r = web_app.router
        r.add_get("/", app.index)
        r.add_get("/api/status", app.status)
        r.add_post("/api/login", app.login)
        r.add_post("/api/logout", app.logout)
        r.add_get("/api/list", app.get_list)
        r.add_post("/api/list/add", app.add)
        r.add_post("/api/list/check", app.check)
        r.add_post("/api/list/quantity", app.quantity)
        r.add_post("/api/list/remove", app.remove)
        r.add_get("/api/search", app.search)
        r.add_get("/api/suggestions", app.suggestions)
        r.add_get("/api/delivery", app.delivery)
        r.add_get("/api/orders", app.orders)
        r.add_get("/api/orders/{order_id}", app.order)
        r.add_get("/api/frequent", app.frequent)
        r.add_get("/api/bonus", app.bonus)
        r.add_get("/api/barcode/{gtin}", app.barcode)
        r.add_get("/api/inventory", app.inv_list)
        r.add_post("/api/inventory/adjust", app.inv_adjust)
        r.add_post("/api/inventory/set", app.inv_set)
        r.add_post("/api/inventory/remove", app.inv_remove)
        r.add_get("/api/inventory/scan/{gtin}", app.inv_scan)
        r.add_post("/api/inventory/link", app.inv_link)
        r.add_get("/api/inventory/orders", app.inv_orders)
        r.add_post("/api/inventory/unpack", app.inv_unpack)
        r.add_post("/api/inventory/to-list", app.inv_to_list)
        r.add_get("/api/spending", app.spending_api)
        r.add_post("/api/sync", app.sync_now)
        r.add_static("/static", STATIC_DIR)

        runner = web.AppRunner(web_app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8099))
        await web.TCPSite(runner, "0.0.0.0", port).start()
        _LOGGER.info("HAppie draait op poort %s (to-do: %s)", port, options["todo_entity"])

        tasks = [asyncio.create_task(app.sync_loop())]
        if app.ha:
            tasks.append(asyncio.create_task(app.ha.listen(lambda: _set(app))))
        app.request_sync()
        await app.publish_inventory_sensor()
        await asyncio.gather(*tasks)


async def _set(app: App) -> None:
    app.request_sync()


if __name__ == "__main__":
    asyncio.run(main())
