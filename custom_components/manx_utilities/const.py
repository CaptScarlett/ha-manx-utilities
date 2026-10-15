"""Constants for the Manx Utilities integration."""

import os

DOMAIN = "manx_utilities"

# Unofficial SmarterLiving portal API (Hildebrand Glowmarkt platform).
# The env override exists only for local testing against a fake server.
API_URL = os.environ.get("MANX_UTILITIES_API_URL", "https://api.manxutilities.im/api/v0-1")
APP_ID = "8f56d0c3-351b-43aa-bf86-b49dbacd18dc"  # app-wide, not personal
KWH_RESOURCE = "603beb2c-b7b8-47ab-9b27-aa6054ca4072"
COST_RESOURCE = "df5aa0cc-6c25-4098-abe4-75f31fc21640"

KWH_STATISTIC_ID = f"{DOMAIN}:electricity_consumption"
COST_STATISTIC_ID = f"{DOMAIN}:electricity_cost"

CONF_STANDING_PENCE = "standing_pence"
CONF_BACKFILL_DAYS = "backfill_days"
DEFAULT_STANDING_PENCE = 25.5  # "Comfy Heat Extra" standing charge per day
DEFAULT_BACKFILL_DAYS = 30

# MU publishes half-hourly data about 1.5h late; polling faster gains nothing.
UPDATE_INTERVAL_MINUTES = 30
# Incomplete hours older than this are imported as zero use instead of blocking.
GAP_GRACE_HOURS = 72
