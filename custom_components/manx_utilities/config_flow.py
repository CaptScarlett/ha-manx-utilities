"""Config flow for Manx Utilities."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ManxUtilitiesApi, MUAuthError, MUError
from .const import (
    CONF_BACKFILL_DAYS,
    CONF_STANDING_PENCE,
    DEFAULT_BACKFILL_DAYS,
    DEFAULT_STANDING_PENCE,
    DOMAIN,
)

USER_SCHEMA = vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})


class ManxUtilitiesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].strip().lower())
            self._abort_if_unique_id_configured()
            api = ManxUtilitiesApi(
                async_get_clientsession(self.hass),
                user_input[CONF_USERNAME].strip(),
                user_input[CONF_PASSWORD],
            )
            try:
                await api.login()
            except MUAuthError:
                errors["base"] = "invalid_auth"
            except MUError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Manx Utilities ({user_input[CONF_USERNAME].strip()})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ManxUtilitiesOptionsFlow()


class ManxUtilitiesOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STANDING_PENCE,
                        default=opts.get(CONF_STANDING_PENCE, DEFAULT_STANDING_PENCE),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required(
                        CONF_BACKFILL_DAYS,
                        default=opts.get(CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
                }
            ),
        )
