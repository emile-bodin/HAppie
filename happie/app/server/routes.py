"""URL routes of the panel and its API."""
from __future__ import annotations

from aiohttp import web

from config import STATIC_DIR
from server.app import App


def setup_routes(web_app: web.Application, app: App) -> None:
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
    r.add_get("/api/spending/items", app.spending_items_api)
    r.add_get("/api/spending/purchase/{purchase_id}", app.spending_purchase_api)
    r.add_post("/api/spending/link", app.spending_link_api)
    r.add_post("/api/sync", app.sync_now)
    r.add_get("/api/settings", app.settings_api)
    r.add_post("/api/settings", app.save_settings_api)
    r.add_get("/api/entities", app.entities_api)
    r.add_static("/static", STATIC_DIR)
