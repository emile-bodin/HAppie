"""End-to-end sync test: add-on (python dev/run_addon.py --mock-ah) + dev HA. Run: python dev/e2e_test.py"""
import asyncio, aiohttp, sys
env = dict(l.split("=",1) for l in open("dev/.env") if "=" in l and not l.startswith("#"))
HA, T = env["HA_URL"].strip(), env["HA_TOKEN"].strip()
H = {"Authorization": f"Bearer {T}"}
E = "todo.boodschappen"
async def ha_items(s):
    async with s.post(f"{HA}/api/services/todo/get_items?return_response", json={"entity_id": E}, headers=H) as r:
        d = await r.json()
    return sorted((i["summary"], i["status"]) for i in d["service_response"][E]["items"])
async def addon(s):
    async with s.get("http://localhost:8099/api/list") as r:
        return sorted((i["name"], i["checked"]) for i in (await r.json())["items"])
async def svc(s, name, data):
    async with s.post(f"{HA}/api/services/todo/{name}", json={"entity_id": E, **data}, headers=H) as r:
        r.raise_for_status()
async def main():
    async with aiohttp.ClientSession() as s:
        async with s.post("http://localhost:8099/api/sync") as r: print("sync", r.status)
        print("1 eerste sync  HA:", await ha_items(s)); print("             AH:", await addon(s))
        await svc(s, "add_item", {"item": "Kaas"}); await asyncio.sleep(5)
        print("2 HA +Kaas    AH:", await addon(s))
        await svc(s, "update_item", {"item": "Brood", "status": "completed"}); await asyncio.sleep(5)
        print("3 HA vink Brood AH:", await addon(s))
        async with s.post("http://localhost:8099/api/list/add", json={"name": "Eieren"}) as r: r.raise_for_status()
        print("4 paneel +Eieren HA:", await ha_items(s))
        async with s.post("http://localhost:8099/api/list/remove", json={"key": "kaas"}) as r: r.raise_for_status()
        print("5 paneel -Kaas  HA:", await ha_items(s))
asyncio.run(main())
