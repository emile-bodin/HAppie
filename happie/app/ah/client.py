"""Minimal async client for the (unofficial) Albert Heijn mobile API.

Authentication and HTTP live here; the endpoints are grouped in mixins per topic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import aiohttp

from ah.errors import AHAuthError, AHError, AHOrderModeError
from ah.models import BASE_URL, CLIENT_ID, CLIENT_VERSION, USER_AGENT, extract_code
from ah.orders import OrdersMixin
from ah.products import ProductsMixin
from ah.purchases import PurchasesMixin
from ah.shopping_list import ShoppingListMixin

_LOGGER = logging.getLogger(__name__)


class AHClient(ShoppingListMixin, OrdersMixin, PurchasesMixin, ProductsMixin):
    def __init__(self, session: aiohttp.ClientSession, token_file: str) -> None:
        self._session = session
        self._token_file = token_file
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._anon_token: str | None = None
        self._anon_expires_at: float = 0
        # one refresh at a time: AH may rotate the refresh token, so a second
        # concurrent refresh would send an already-used token and log us out
        self._refresh_lock = asyncio.Lock()
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
            async with self._refresh_lock:
                # another caller may have refreshed while we waited
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
