"""aiohttp middlewares: ingress-only access (plus read-only sensors for HA Core), JSON errors, no stale panel files."""
from __future__ import annotations

import logging
import os

from aiohttp import web

from ah.errors import AHAuthError, AHError, AHOrderModeError
from config import CORE_IP, INGRESS_IP

_LOGGER = logging.getLogger("happie")


@web.middleware
async def ingress_only(request: web.Request, handler):
    if os.environ.get("SUPERVISOR_TOKEN") and request.remote not in (INGRESS_IP, "127.0.0.1", "::1"):
        # HA Core itself may only read the sensor values (for the HAppie integration)
        if not (request.remote == CORE_IP and request.method == "GET" and request.path == "/api/entities"):
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


@web.middleware
async def no_cache(request: web.Request, handler):
    """The panel is several files: let the browser revalidate them so an update never mixes versions."""
    response = await handler(request)
    if request.path == "/" or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response
