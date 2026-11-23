"""Onboard the local dev Home Assistant and prepare it for the add-on.

- creates a test owner account (credentials written to dev/.env)
- creates a long-lived access token (used as SUPERVISOR_TOKEN by the add-on)
- creates the Local To-do list "Boodschappen" (todo.boodschappen)

Idempotent: safe to run again. Run: python dev/setup_ha.py
"""
import asyncio
import os
import secrets
import sys
from pathlib import Path

import aiohttp

HA = os.environ.get("HA_URL", "http://localhost:8123")
CLIENT_ID = HA + "/"
ENV_FILE = Path(__file__).parent / ".env"


def read_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def write_env(env: dict) -> None:
    lines = ["# Lokale dev-HA (alleen voor testen, niet committen)"]
    lines += [f"{k}={v}" for k, v in env.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def wait_for_ha(s: aiohttp.ClientSession) -> None:
    for i in range(120):
        try:
            async with s.get(HA + "/manifest.json") as r:
                if r.status == 200:
                    return
        except aiohttp.ClientError:
            pass
        if i == 0:
            print("Wachten tot Home Assistant opgestart is...")
        await asyncio.sleep(3)
    sys.exit("Home Assistant reageert niet op " + HA)


async def onboard(s: aiohttp.ClientSession, env: dict) -> str:
    """Returns a short-lived access token."""
    async with s.get(HA + "/api/onboarding") as r:
        steps = {st["step"]: st["done"] for st in await r.json()}

    if not steps.get("user"):
        env["HA_USERNAME"] = "dev"
        env["HA_PASSWORD"] = secrets.token_urlsafe(12)
        write_env(env)
        async with s.post(
            HA + "/api/onboarding/users",
            json={
                "client_id": CLIENT_ID,
                "name": "Dev",
                "username": env["HA_USERNAME"],
                "password": env["HA_PASSWORD"],
                "language": "nl",
            },
        ) as r:
            r.raise_for_status()
            code = (await r.json())["auth_code"]
        print("Testgebruiker aangemaakt")
    else:
        # login with stored credentials via the login flow
        if "HA_PASSWORD" not in env:
            sys.exit("HA is al onboarded, maar dev/.env mist de inloggegevens.")
        async with s.post(
            HA + "/auth/login_flow",
            json={"client_id": CLIENT_ID, "handler": ["homeassistant", None], "redirect_uri": CLIENT_ID},
        ) as r:
            flow = await r.json()
        async with s.post(
            HA + f"/auth/login_flow/{flow['flow_id']}",
            json={"client_id": CLIENT_ID, "username": env["HA_USERNAME"], "password": env["HA_PASSWORD"]},
        ) as r:
            res = await r.json()
            code = res["result"]

    async with s.post(
        HA + "/auth/token",
        data={"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID},
    ) as r:
        r.raise_for_status()
        token = (await r.json())["access_token"]

    h = {"Authorization": f"Bearer {token}"}
    for step, body in (
        ("core_config", {}),
        ("analytics", {}),
        ("integration", {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID}),
    ):
        if not steps.get(step):
            async with s.post(HA + f"/api/onboarding/{step}", json=body, headers=h) as r:
                if r.status >= 400 and r.status != 403:
                    print(f"Onboarding-stap {step}: {r.status} {await r.text()}")
    return token


async def ws_call(s: aiohttp.ClientSession, token: str, msg: dict) -> dict:
    async with s.ws_connect(HA.replace("http", "ws", 1) + "/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": token})
        if (await ws.receive_json())["type"] != "auth_ok":
            sys.exit("Websocket-auth mislukt")
        await ws.send_json({"id": 1, **msg})
        return await ws.receive_json()


async def main() -> None:
    env = read_env()
    async with aiohttp.ClientSession() as s:
        await wait_for_ha(s)
        token = await onboard(s, env)
        h = {"Authorization": f"Bearer {token}"}

        if "HA_TOKEN" not in env:
            res = await ws_call(
                s, token, {"type": "auth/long_lived_access_token", "client_name": "happie-dev", "lifespan": 3650}
            )
            env["HA_URL"] = HA
            env["HA_TOKEN"] = res["result"]
            write_env(env)
            print("Long-lived token aangemaakt")

        async with s.get(HA + "/api/states/todo.boodschappen", headers=h) as r:
            exists = r.status == 200
        if not exists:
            async with s.post(
                HA + "/api/config/config_entries/flow", json={"handler": "local_todo"}, headers=h
            ) as r:
                flow = await r.json()
            async with s.post(
                HA + f"/api/config/config_entries/flow/{flow['flow_id']}",
                json={"todo_list_name": "Boodschappen"},
                headers=h,
            ) as r:
                res = await r.json()
            print("To-do-lijst:", res.get("type"), res.get("title"))
        else:
            print("todo.boodschappen bestaat al")

    print(f"\nKlaar. Open {HA} en log in met de gegevens uit dev/.env")


asyncio.run(main())
