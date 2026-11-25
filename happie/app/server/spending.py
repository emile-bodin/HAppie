"""Spending per week and month, the week and month budget and their sensors."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any

from aiohttp import web

from ah.errors import AHAuthError, AHError
from config import BUDGET_MONTH_NOTIFICATION, BUDGET_NOTIFICATION, BUDGET_SENSOR, DATA_DIR, SPEND_MONTH_SENSOR, SPEND_WEEK_SENSOR
from services.spending import HISTORY_DAYS, aggregate, budget_status, summary as spending_summary

_LOGGER = logging.getLogger("happie")


class SpendingMixin:
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
        s["month_budget"] = budget_status(s["this_month"], self._list_cost, float(self.options.get("month_budget") or 0))
        return s

    @staticmethod
    def _period_start(day: str) -> str:
        return datetime.fromisoformat(day).astimezone().isoformat()

    async def publish_spending_sensors(self) -> None:
        s = self.spending_overview()
        b, m = s["budget"], s["month_budget"]
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
            **({"budget": m["budget"], "budget_remaining": m["remaining"]} if m else {}),
        })
        if b:
            await self._set_state_if_changed(BUDGET_SENSOR, "on" if b["over"] else "off", {
                "friendly_name": "AH boven weekbudget", "icon": "mdi:wallet-outline", "device_class": "problem", **b,
            })

    async def check_budget_notification(self) -> None:
        """Notify once per week / month when spent + the list goes over the week / month budget."""
        s = self.spending_overview()
        iso = date.today().isocalendar()
        await self._check_budget(
            s["budget"], f"{iso[0]}-W{iso[1]:02d}", "week", "notified_budget.json", BUDGET_NOTIFICATION,
            "weekbudget", "Deze week",
        )
        await self._check_budget(
            s["month_budget"], date.today().strftime("%Y-%m"), "month", "notified_budget_month.json",
            BUDGET_MONTH_NOTIFICATION, "maandbudget", "Deze maand",
        )

    async def _check_budget(
        self, b: dict[str, Any] | None, period: str, key: str, filename: str, notification_id: str,
        name: str, this_period: str,
    ) -> None:
        path = DATA_DIR / filename
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if b and b["over"]:
            if state.get(key) == period and state.get("active"):
                return
            if state.get(key) != period:
                _LOGGER.info("%s overschreden (%.2f van %.2f); melding gestuurd",
                             name.capitalize(), b["projected"], b["budget"])
                await self.ha.notify(
                    f"AH: boven je {name}",
                    f"{this_period} al **€ {b['spent']:.2f}** uitgegeven. Met je lijst erbij (€ {b['list_cost']:.2f}) "
                    f"kom je op **€ {b['projected']:.2f}**, € {-b['remaining']:.2f} boven je {name} van € {b['budget']:.2f}.",
                    notification_id,
                    self.options.get("notify_service", ""),
                )
            state = {key: period, "active": True}
        elif state.get("active"):
            await self.ha.dismiss(notification_id)
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
            "recent": sorted(purchases, key=lambda p: p["date"], reverse=True)[:300],
            "sensors": sensors if self.ha else [],
        })
