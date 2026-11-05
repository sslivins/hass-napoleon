"""Test the bundled Lovelace card registration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.napoleon.card import CARD_FILENAME, CARD_URL, async_register_card


async def test_card_registered_once(hass: HomeAssistant) -> None:
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await async_register_card(hass)
        await async_register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    (cfg,) = hass.http.async_register_static_paths.await_args.args[0]
    assert (Path(cfg.path) / CARD_FILENAME).is_file()
    add_js.assert_called_once()
    assert add_js.call_args.args[1].startswith(f"{CARD_URL}?v=")


async def test_card_skipped_without_http(hass: HomeAssistant) -> None:
    hass.http = None
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await async_register_card(hass)
    add_js.assert_not_called()
