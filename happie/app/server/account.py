"""Account and status: login, logout, status, sync button, the panel page itself."""
from __future__ import annotations

import logging

from aiohttp import web

from ah.errors import AHAuthError
from ah.models import LOGIN_URL
from config import LOGIN_NOTIFICATION, STATIC_DIR

_LOGGER = logging.getLogger("happie")


class AccountMixin:
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

    async def run_sync_now(self) -> None:
        try:
            await self.sync.sync()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Sync mislukt: %s", err)

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

    async def sync_now(self, request: web.Request) -> web.Response:
        await self.sync.sync()
        return web.json_response({"ok": True, "last_sync": self.sync.last_sync})
