"""Client for the Manx Utilities SmarterLiving API."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import aiohttp

from .const import API_URL, APP_ID

CHUNK_SECONDS = 6 * 86400  # requests over ~7 days fail
TIMEOUT = aiohttp.ClientTimeout(total=60)


class MUError(Exception):
    """API call failed."""


class MUAuthError(MUError):
    """Login rejected."""


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")


class ManxUtilitiesApi:
    """Minimal async client: login and half-hourly readings."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_exp = 0.0

    async def login(self) -> None:
        try:
            async with self._session.post(
                f"{API_URL}/auth/",
                headers={"applicationId": APP_ID},
                json={"username": self._username, "password": self._password},
                timeout=TIMEOUT,
            ) as resp:
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MUError(f"login request failed: {err}") from err
        if not isinstance(body, dict) or not body.get("valid") or not body.get("token"):
            # Key names only: never log the token or credentials.
            keys = sorted(body) if isinstance(body, dict) else type(body).__name__
            raise MUAuthError(f"login rejected (HTTP {resp.status}, response keys {keys})")
        self._token = body["token"]
        self._token_exp = float(body.get("exp") or time.time() + 3600)

    async def _get(self, path: str, params: dict) -> dict:
        if not self._token or self._token_exp - time.time() < 3600:
            await self.login()
        for attempt in range(2):
            try:
                async with self._session.get(
                    f"{API_URL}{path}",
                    headers={"applicationId": APP_ID, "token": self._token, "X-GLOW-Version": "144"},
                    params=params,
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        await self.login()
                        continue
                    if resp.status != 200:
                        raise MUError(f"GET {path} returned HTTP {resp.status}")
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise MUError(f"GET {path} failed: {err}") from err
        raise MUError(f"GET {path} unauthorised after re-login")

    async def readings(self, resource: str, start: int, end: int) -> dict[int, float | None]:
        """Half-hourly sums for [start, end), keyed by true UTC bucket start."""
        out: dict[int, float | None] = {}
        t = start
        while t < end:
            chunk_end = min(t + CHUNK_SECONDS, end)
            data = await self._get(
                f"/resource/{resource}/readings",
                {
                    "nulls": "1",
                    "from": _iso(t),
                    "to": _iso(chunk_end - 1),
                    "period": "PT30M",
                    "offset": "0",  # other offsets shift labels to local wall-clock time
                    "function": "sum",
                },
            )
            for row in data.get("data", []):
                out[int(row[0])] = row[1]
            t = chunk_end
        return out
