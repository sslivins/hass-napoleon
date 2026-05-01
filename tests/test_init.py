"""Test integration setup / unload."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pynapoleon import NapoleonAuthError, NapoleonConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.napoleon.const import DOMAIN


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_unload(hass: HomeAssistant, mock_client: MagicMock) -> None:
    entry = await _setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_client.close.assert_awaited()


async def test_setup_auth_error_triggers_reauth(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.login.side_effect = NapoleonAuthError("bad creds")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_connection_error_retries(hass: HomeAssistant, mock_client: MagicMock) -> None:
    mock_client.fireplaces.side_effect = NapoleonConnectionError("network")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_fireplaces(hass: HomeAssistant, mock_client: MagicMock) -> None:
    mock_client.fireplaces.return_value = []
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_client")
async def test_runtime_data_populated(hass: HomeAssistant, mock_client: MagicMock) -> None:
    entry = await _setup_entry(hass)
    rt = entry.runtime_data
    assert rt.client is mock_client
    assert len(rt.coordinators) == 1
    assert rt.coordinators[0].fireplace.dsn == "AC000W032261383"
