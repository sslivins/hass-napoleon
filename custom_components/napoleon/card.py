"""Serve and auto-load the bundled Napoleon fireplace Lovelace card."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "napoleon-fireplace-card.js"
CARD_URL_BASE = f"/{DOMAIN}_static"
CARD_URL = f"{CARD_URL_BASE}/{CARD_FILENAME}"
_REGISTERED = f"{DOMAIN}_card_registered"


async def async_register_card(hass: HomeAssistant) -> None:
    """Expose the card JS and add it to every frontend page (once per HA run)."""
    if hass.data.get(_REGISTERED) or hass.http is None:
        return
    hass.data[_REGISTERED] = True

    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    path = Path(__file__).parent / "frontend"
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, str(path), cache_headers=False)]
        )
    except RuntimeError:
        # Route already exists (e.g. integration reloaded after a failed setup).
        _LOGGER.debug("Static path %s already registered", CARD_URL_BASE)

    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
