# Manx Utilities for Home Assistant

Imports half-hourly electricity usage and cost from a Manx Utilities (Isle of Man) smart meter
into Home Assistant's long-term statistics, for the Energy dashboard.

Unofficial. It uses the SmarterLiving portal's (smart.manxutilities.im) undocumented API, which
can change without notice.

## What it creates

Two external statistics, filled in hourly (UTC) and backfilled 30 days on first setup:

| Statistic | Unit | Notes |
|---|---|---|
| `manx_utilities:electricity_consumption` | kWh | Grid consumption |
| `manx_utilities:electricity_cost` | GBP | Unit costs plus the daily standing charge spread over 24 hours |

MU publishes data about 1.5 hours late, so the integration checks every 30 minutes and only
imports complete hours. Because the data is imported against the hour it was used (not when it
arrived), time-of-use costs line up correctly.

## Install

1. HACS → ⋮ → Custom repositories → add this repo as an **Integration**.
2. Download **Manx Utilities**, then restart Home Assistant.
3. Settings → Devices & services → Add integration → **Manx Utilities**, and sign in with your
   SmarterLiving email and password.
4. Settings → Dashboards → Energy: add `Manx Utilities electricity consumption` as grid
   consumption and `Manx Utilities electricity cost` as its total cost.

The standing charge (default 25.5p/day) can be changed under the integration's **Configure**.

## Limitations

- The meter resource IDs are currently fixed in `const.py` for one account.
- Cheap-rate windows follow the meter's clock, which runs on UTC.
