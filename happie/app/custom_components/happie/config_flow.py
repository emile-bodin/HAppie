"""Config flow: found through Supervisor discovery, or the app's URL entered by hand."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

try:
    from homeassistant.helpers.service_info.hassio import HassioServiceInfo
except ImportError:  # Home Assistant before 2025.1
    from homeassistant.components.hassio import HassioServiceInfo

from .const import CONF_URL, DEFAULT_URL, DOMAIN
from .coordinator import HAppieError, fetch_entities


class HAppieConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None

    async def _validate(self, url: str) -> str | None:
        try:
            await fetch_entities(self.hass, url)
        except HAppieError:
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if not (error := await self._validate(url)):
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured(updates={CONF_URL: url})
                return self.async_create_entry(title="HAppie", data={CONF_URL: url})
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL, default=(user_input or {}).get(CONF_URL, DEFAULT_URL)): str}
            ),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """The app announced itself to the Supervisor with its host name and port."""
        config = discovery_info.config
        self._url = f"http://{config['host']}:{config['port']}"
        await self.async_set_unique_id(DOMAIN)
        # The host name changes when the app is reinstalled from another repository
        self._abort_if_unique_id_configured(updates={CONF_URL: self._url})
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._url
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (error := await self._validate(self._url)):
                return self.async_create_entry(title="HAppie", data={CONF_URL: self._url})
            errors["base"] = error
        return self.async_show_form(step_id="hassio_confirm", errors=errors)
