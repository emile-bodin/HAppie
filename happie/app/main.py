"""HAppie app: web UI (ingress) + AH <-> HA to-do sync."""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from aiohttp import web

from config import DATA_DIR, load_options
from server.app import App
from server.middleware import ingress_only, json_errors, no_cache
from server.routes import setup_routes

_LOGGER = logging.getLogger("happie")


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

        web_app = web.Application(middlewares=[ingress_only, json_errors, no_cache])
        setup_routes(web_app, app)

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
        await app.install_integration()
        await app.announce_integration()
        await asyncio.gather(*tasks)


async def _set(app: App) -> None:
    app.request_sync()


if __name__ == "__main__":
    asyncio.run(main())
