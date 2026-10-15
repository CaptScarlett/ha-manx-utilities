"""Manx Utilities smart meter usage and cost as Home Assistant statistics."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api import ManxUtilitiesApi, MUAuthError, MUError
from .const import (
    CONF_BACKFILL_DAYS,
    CONF_STANDING_PENCE,
    DEFAULT_BACKFILL_DAYS,
    DEFAULT_STANDING_PENCE,
    UPDATE_INTERVAL_MINUTES,
)
from .importer import StatisticsImporter

type ManxUtilitiesConfigEntry = ConfigEntry[StatisticsImporter]


async def async_setup_entry(hass: HomeAssistant, entry: ManxUtilitiesConfigEntry) -> bool:
    api = ManxUtilitiesApi(
        async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    try:
        await api.login()
    except MUAuthError as err:
        raise ConfigEntryError(f"Manx Utilities login failed: {err}") from err
    except MUError as err:
        raise ConfigEntryNotReady(str(err)) from err

    importer = StatisticsImporter(
        hass,
        api,
        entry.options.get(CONF_STANDING_PENCE, DEFAULT_STANDING_PENCE),
        entry.options.get(CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS),
    )
    entry.runtime_data = importer
    entry.async_on_unload(
        async_track_time_interval(
            hass, importer.async_run, timedelta(minutes=UPDATE_INTERVAL_MINUTES)
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    # The first run may backfill weeks of data; don't hold up HA startup for it.
    entry.async_create_background_task(hass, importer.async_run(), "manx_utilities_import")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ManxUtilitiesConfigEntry) -> bool:
    return True


async def _async_reload(hass: HomeAssistant, entry: ManxUtilitiesConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
