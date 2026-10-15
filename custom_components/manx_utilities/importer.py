"""Import Manx Utilities readings as Home Assistant external statistics."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .aggregate import build_hours
from .api import ManxUtilitiesApi, MUError
from .const import (
    COST_RESOURCE,
    COST_STATISTIC_ID,
    DOMAIN,
    GAP_GRACE_HOURS,
    KWH_RESOURCE,
    KWH_STATISTIC_ID,
)

_LOGGER = logging.getLogger(__name__)


def _dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=UTC)


class StatisticsImporter:
    """Fetch new complete hours and append them to the cumulative statistics."""

    def __init__(
        self, hass: HomeAssistant, api: ManxUtilitiesApi, standing_pence: float, backfill_days: int
    ) -> None:
        self.hass = hass
        self.api = api
        self.standing_pence = standing_pence
        self.backfill_days = backfill_days
        self._lock = asyncio.Lock()

    async def async_run(self, _now: datetime | None = None) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            try:
                await self._import()
            except MUError as err:
                _LOGGER.warning("Manx Utilities update failed: %s", err)

    async def _sum_at(self, statistic_id: str, hour: float) -> float:
        rows = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass, _dt(hour), _dt(hour + 3600), {statistic_id}, "hour", None, {"sum"},
        )
        return rows[statistic_id][0]["sum"]

    async def _resume_point(self, now: int) -> tuple[int, float, float]:
        """Last imported hour and the running sums at that hour, from the recorder."""
        recorder = get_instance(self.hass)
        last = {}
        for sid in (KWH_STATISTIC_ID, COST_STATISTIC_ID):
            rows = await recorder.async_add_executor_job(
                get_last_statistics, self.hass, 1, sid, False, {"sum"}
            )
            last[sid] = rows[sid][0] if rows.get(sid) else None

        kwh_last, cost_last = last[KWH_STATISTIC_ID], last[COST_STATISTIC_ID]
        if kwh_last is None or cost_last is None:
            first = (now - self.backfill_days * 86400) // 3600 * 3600
            _LOGGER.info("No existing statistics, backfilling %s days", self.backfill_days)
            return first - 3600, 0.0, 0.0

        hour = int(min(kwh_last["start"], cost_last["start"]))
        kwh_sum = kwh_last["sum"] if kwh_last["start"] == hour else await self._sum_at(KWH_STATISTIC_ID, hour)
        cost_sum = cost_last["sum"] if cost_last["start"] == hour else await self._sum_at(COST_STATISTIC_ID, hour)
        return hour, kwh_sum, cost_sum

    async def _import(self) -> None:
        now = int(dt_util.utcnow().timestamp())
        last_hour, kwh_sum, cost_sum = await self._resume_point(now)
        start, end = last_hour + 3600, now // 1800 * 1800
        if start + 3600 > end:
            return

        kwh = await self.api.readings(KWH_RESOURCE, start, end)
        cost = await self.api.readings(COST_RESOURCE, start, end)
        rows, gaps = build_hours(
            kwh, cost, last_hour, kwh_sum, cost_sum, now, self.standing_pence, GAP_GRACE_HOURS
        )
        if gaps:
            _LOGGER.warning(
                "No data from Manx Utilities for %s hour(s) older than %sh (first %s); imported as zero use",
                len(gaps), GAP_GRACE_HOURS, _dt(gaps[0]).isoformat(),
            )
        if not rows:
            _LOGGER.debug("No new complete hours yet")
            return

        async_add_external_statistics(
            self.hass,
            {
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Manx Utilities electricity consumption",
                "source": DOMAIN,
                "statistic_id": KWH_STATISTIC_ID,
                "unit_class": "energy",
                "unit_of_measurement": "kWh",
            },
            [{"start": _dt(r.start), "state": r.kwh_sum, "sum": r.kwh_sum} for r in rows],
        )
        async_add_external_statistics(
            self.hass,
            {
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Manx Utilities electricity cost",
                "source": DOMAIN,
                "statistic_id": COST_STATISTIC_ID,
                "unit_class": None,
                "unit_of_measurement": "GBP",
            },
            [{"start": _dt(r.start), "state": r.cost_sum, "sum": r.cost_sum} for r in rows],
        )
        _LOGGER.info(
            "Imported %s hour(s) up to %s: %.3f kWh, GBP %.2f",
            len(rows), _dt(rows[-1].start).isoformat(),
            sum(r.kwh for r in rows), sum(r.gbp for r in rows),
        )
