"""Talks to Home Assistant Core through the Supervisor proxy."""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import aiohttp

_LOGGER = logging.getLogger(__name__)


class HAError(Exception):
    pass


@dataclass
class TodoItem:
    uid: str
    summary: str
    completed: bool


class HAClient:
    def __init__(self, session: aiohttp.ClientSession, entity_id: str) -> None:
        self._session = session
        self.entity_id = entity_id
        self._token = os.environ.get("SUPERVISOR_TOKEN", "")
        base = os.environ.get("HA_URL", "http://supervisor/core")
        self._api = base + "/api"
        # Supervisor proxy serves the websocket at /core/websocket, Core itself at /api/websocket
        ws_path = "/websocket" if base.rstrip("/").endswith("supervisor/core") else "/api/websocket"
        self._ws_url = base.replace("http", "ws", 1) + ws_path

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def _service(self, domain: str, service: str, data: dict[str, Any], response: bool = False) -> Any:
        url = f"{self._api}/services/{domain}/{service}"
        if response:
            url += "?return_response"
        async with self._session.post(
            url, json=data, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise HAError(f"{domain}.{service} gaf {resp.status}: {text[:300]}")
            return await resp.json(content_type=None) if text else None

    async def entity_exists(self) -> bool:
        async with self._session.get(
            f"{self._api}/states/{self.entity_id}", headers=self._headers()
        ) as resp:
            return resp.status == 200

    async def get_items(self) -> list[TodoItem]:
        data = await self._service(
            "todo",
            "get_items",
            {"entity_id": self.entity_id, "status": ["needs_action", "completed"]},
            response=True,
        )
        resp = (data or {}).get("service_response", data or {})
        items = (resp.get(self.entity_id) or {}).get("items", [])
        return [
            TodoItem(uid=i["uid"], summary=i.get("summary", ""), completed=i.get("status") == "completed")
            for i in items
            if i.get("summary")
        ]

    async def add_item(self, summary: str, completed: bool = False) -> None:
        await self._service("todo", "add_item", {"entity_id": self.entity_id, "item": summary})
        if completed:
            await self._service(
                "todo", "update_item", {"entity_id": self.entity_id, "item": summary, "status": "completed"}
            )

    async def set_completed(self, item: TodoItem, completed: bool) -> None:
        await self._service(
            "todo",
            "update_item",
            {
                "entity_id": self.entity_id,
                "item": item.uid,
                "status": "completed" if completed else "needs_action",
            },
        )

    async def remove_items(self, items: list[TodoItem]) -> None:
        if items:
            await self._service(
                "todo", "remove_item", {"entity_id": self.entity_id, "item": [i.uid for i in items]}
            )

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Create/update a (non-persistent) entity state, e.g. a sensor published by the add-on."""
        async with self._session.post(
            f"{self._api}/states/{entity_id}",
            json={"state": state, "attributes": attributes},
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status >= 400:
                raise HAError(f"Status van {entity_id} zetten gaf {resp.status}: {(await resp.text())[:200]}")

    async def notify(self, title: str, message: str, notification_id: str, service: str = "") -> None:
        """Persistent notification in HA, plus an optional notify service (e.g. notify.mobile_app_phone)."""
        await self._service(
            "persistent_notification",
            "create",
            {"notification_id": notification_id, "title": title, "message": message},
        )
        if service:
            domain, _, name = service.partition(".")
            if domain != "notify" or not name:
                _LOGGER.warning("notify_service '%s' moet de vorm notify.<naam> hebben", service)
                return
            # phones don't render markdown
            await self._service("notify", name, {"title": title, "message": message.replace("**", "")})

    async def dismiss(self, notification_id: str) -> None:
        await self._service("persistent_notification", "dismiss", {"notification_id": notification_id})

    async def listen(self, on_change: Callable[[], Awaitable[None]]) -> None:
        """Call on_change whenever the to-do entity changes. Reconnects forever."""
        while True:
            try:
                async with self._session.ws_connect(self._ws_url, heartbeat=30) as ws:
                    msg = await ws.receive_json()  # auth_required
                    await ws.send_json({"type": "auth", "access_token": self._token})
                    msg = await ws.receive_json()
                    if msg.get("type") != "auth_ok":
                        raise HAError(f"Websocket-auth mislukt: {msg}")
                    await ws.send_json(
                        {
                            "id": 1,
                            "type": "subscribe_trigger",
                            "trigger": {"platform": "state", "entity_id": self.entity_id},
                        }
                    )
                    _LOGGER.info("Luistert naar wijzigingen van %s", self.entity_id)
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        data = msg.json()
                        if data.get("type") == "event":
                            await on_change()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Websocket naar HA verbroken (%s); opnieuw over 15s", err)
            await asyncio.sleep(15)
