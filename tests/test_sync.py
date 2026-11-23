"""Sync engine tests with in-memory fakes. Run: python tests/test_sync.py"""
import asyncio
import os
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))

from ah_client import AHClient  # noqa: E402
from mock import FakeHA, install_mocks  # noqa: E402
from sync import SyncEngine  # noqa: E402


def make():
    tmp = tempfile.mkdtemp()
    ah = AHClient(None, os.path.join(tmp, "t.json"))
    app = SimpleNamespace(ah=ah, options={"todo_entity": "todo.x"})
    app.sync = SyncEngine(ah, None, os.path.join(tmp, "s.json"))
    install_mocks(app)
    return app


async def names_ah(app):
    return sorted((i.name, i.checked) for i in await app.ah.get_list())


def names_ha(app):
    return sorted((i.summary, i.completed) for i in app.fake_ha.items)


async def main():
    app = make()
    s = app.sync

    # 1. first sync merges both lists
    await s.sync()
    assert await names_ah(app) == names_ha(app), (await names_ah(app), names_ha(app))
    assert len(names_ha(app)) == 4

    # 2. add in HA -> appears at AH
    await app.fake_ha.add_item("Kaas")
    await s.sync()
    assert ("Kaas", False) in await names_ah(app)

    # 3. add at AH -> appears in HA
    await app.ah.add_item("Eieren")
    await s.sync()
    assert ("Eieren", False) in names_ha(app)

    # 4. check off in HA -> struck through at AH
    kaas = next(i for i in app.fake_ha.items if i.summary == "Kaas")
    await app.fake_ha.set_completed(kaas, True)
    await s.sync()
    assert ("Kaas", True) in await names_ah(app)

    # 5. check off at AH -> completed in HA
    brood = next(i for i in await app.ah.get_list() if i.name == "Brood")
    await app.ah.set_checked(brood, True)
    await s.sync()
    assert ("Brood", True) in names_ha(app)

    # 6. remove in HA -> removed at AH
    await app.fake_ha.remove_items([i for i in app.fake_ha.items if i.summary == "Bananen"])
    await s.sync()
    assert all(n != "Bananen" for n, _ in await names_ah(app))

    # 7. remove at AH -> removed in HA (case-insensitive match)
    milk = [i for i in await app.ah.get_list() if i.name == "AH Halfvolle melk"]
    await app.ah.remove_items(milk)
    await s.sync()
    assert all(n != "AH Halfvolle melk" for n, _ in names_ha(app))

    # 8. stable: another sync changes nothing
    before = (await names_ah(app), names_ha(app))
    await s.sync()
    assert before == (await names_ah(app), names_ha(app))
    assert await names_ah(app) == names_ha(app)

    # 9. AH removal that doesn't stick -> tombstone, not resurrected in HA
    orig = app.ah._patch

    async def broken_patch(items):
        await orig([b for b in items if b["quantity"] != 0])

    app.ah._patch = broken_patch
    await app.fake_ha.remove_items([i for i in app.fake_ha.items if i.summary == "Eieren"])
    await s.sync()
    await s.sync()
    assert all(n != "Eieren" for n, _ in names_ha(app))
    assert s.tombstones == ["eieren"] and s.warnings
    app.ah._patch = orig

    # 10. order mode (412): sync pauses without touching either side
    from ah_client import AHOrderModeError

    before = (await names_ah(app), names_ha(app))
    orig_get = app.ah.get_list

    async def locked():
        raise AHOrderModeError("order mode")

    app.ah.get_list = locked
    await app.fake_ha.add_item("Tijdens bestelling")
    await s.sync()
    assert s.order_mode and s.last_error is None
    assert ("Tijdens bestelling", False) in names_ha(app)
    app.ah.get_list = orig_get
    await s.sync()
    assert not s.order_mode
    assert ("Tijdens bestelling", False) in await names_ah(app)  # pushed once the lock is gone
    assert set(before[0]) <= set(await names_ah(app))

    print("all sync tests passed")


asyncio.run(main())
