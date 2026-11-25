"""AH token refresh tests. Run: python tests/test_auth.py"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "happie", "app"))

from ah import AHClient  # noqa: E402
from ah.errors import AHError  # noqa: E402


class RotatingAH:
    """Fake token endpoint that rotates the refresh token, like AH may do."""

    def __init__(self) -> None:
        self.valid = "r0"
        self.calls = 0

    async def raw(self, method, path, json_body=None, auth=True, **_):
        assert path.endswith("/token/refresh"), path
        self.calls += 1
        await asyncio.sleep(0.01)  # let other callers pile up
        if json_body["refreshToken"] != self.valid:
            raise AHError("400: refresh token already used")
        self.valid = f"r{self.calls}"
        return {"access_token": f"a{self.calls}", "refresh_token": self.valid, "expires_in": 3600}


def make_client(tmp: str, expires_at: float) -> tuple[AHClient, RotatingAH]:
    path = os.path.join(tmp, "tokens.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"access_token": "old", "refresh_token": "r0", "expires_at": expires_at}, fh)
    client = AHClient(None, path)  # type: ignore[arg-type]
    fake = RotatingAH()
    client._raw = fake.raw  # type: ignore[method-assign]
    return client, fake


async def test_concurrent_refresh_once(tmp: str) -> None:
    client, fake = make_client(tmp, 0)  # expired
    tokens = await asyncio.gather(*(client._user_token() for _ in range(5)))
    assert fake.calls == 1, fake.calls
    assert set(tokens) == {"a1"}, tokens
    with open(os.path.join(tmp, "tokens.json"), encoding="utf-8") as fh:
        assert json.load(fh)["refresh_token"] == "r1"


async def test_valid_token_no_refresh(tmp: str) -> None:
    client, fake = make_client(tmp, 9e12)  # far in the future
    assert await client._user_token() == "old"
    assert fake.calls == 0


async def main() -> None:
    for test in (test_concurrent_refresh_once, test_valid_token_no_refresh):
        with tempfile.TemporaryDirectory() as tmp:
            await test(tmp)
    print("all auth tests passed")


asyncio.run(main())
