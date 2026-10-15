"""Turn half-hourly meter buckets into complete hourly rows (no HA imports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HourRow:
    start: int  # UTC epoch at the top of the hour
    kwh: float
    gbp: float  # usage cost plus 1/24 of the daily standing charge
    kwh_sum: float
    cost_sum: float


def build_hours(
    kwh: dict[int, float | None],
    cost: dict[int, float | None],
    last_hour: int,
    kwh_sum: float,
    cost_sum: float,
    now: int,
    standing_pence: float,
    gap_grace_hours: int,
) -> tuple[list[HourRow], list[int]]:
    """Aggregate buckets for hours after last_hour.

    Stops at the first recent incomplete hour so cumulative sums stay contiguous.
    Incomplete hours older than gap_grace_hours are imported as zero use.
    Returns the rows and the start of every hour that was filled as a gap.
    """
    rows: list[HourRow] = []
    gaps: list[int] = []
    h = last_hour + 3600
    while h + 3600 <= now:
        k1, k2 = kwh.get(h), kwh.get(h + 1800)
        if k1 is None or k2 is None:
            if h + 3600 > now - gap_grace_hours * 3600:
                break
            gaps.append(h)
        hour_kwh = (k1 or 0) + (k2 or 0)
        # Unpublished cost buckets come back as 0, so kWh decides completeness.
        hour_gbp = ((cost.get(h) or 0) + (cost.get(h + 1800) or 0) + standing_pence / 24) / 100
        kwh_sum = round(kwh_sum + hour_kwh, 4)
        cost_sum = round(cost_sum + hour_gbp, 5)
        rows.append(HourRow(h, hour_kwh, hour_gbp, kwh_sum, cost_sum))
        h += 3600
    return rows, gaps
