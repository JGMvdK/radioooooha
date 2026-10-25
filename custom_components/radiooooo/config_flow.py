"""Config flow: optional Radiooooo account, otherwise anonymous."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import RadiooooAuthError, RadiooooClient, RadiooooError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN


class RadiooooConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            client = RadiooooClient(async_create_clientsession(self.hass))
            email = user_input.get(CONF_EMAIL, "")
            try:
                if email:
                    await client.login(email, user_input.get(CONF_PASSWORD, ""))
                await client.islands()
            except RadiooooAuthError:
                errors["base"] = "invalid_auth"
            except RadiooooError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Radiooooo", data=user_input)

        schema = vol.Schema(
            {vol.Optional(CONF_EMAIL, default=""): str, vol.Optional(CONF_PASSWORD, default=""): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
