"""Availability follows Napoleon's cloud connection status.

Ayla keeps serving a fireplace's last-known properties while it is off
Wi-Fi (the Sun Peaks Living Room unit sat offline for months looking
healthy). Every entity must go unavailable when the cloud says the device
is offline, and the Connection sensor must report it.
"""

from __future__ import annotations

import dataclasses
import logging

import pytest
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pynapoleon import FireplaceState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.napoleon.const import DOMAIN

DSN = "AC000W032261383"
CONNECTIVITY_UID = f"{DSN}_connectivity"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entities(hass: HomeAssistant, entry: MockConfigEntry) -> list[er.RegistryEntry]:
    """Every entity the integration created, so new platforms are covered too."""
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entries) > 10
    return entries


def _set_online(mock_fireplace, fireplace_state: FireplaceState, online: bool | None) -> None:
    state = dataclasses.replace(fireplace_state, online=online)
    mock_fireplace.state = state
    mock_fireplace.refresh.return_value = state


@pytest.mark.parametrize(
    ("online", "connectivity"),
    [(True, STATE_ON), (None, STATE_UNKNOWN), (False, STATE_OFF)],
)
async def test_every_entity_follows_cloud_connection(
    hass: HomeAssistant,
    mock_client,
    mock_fireplace,
    fireplace_state: FireplaceState,
    online: bool | None,
    connectivity: str,
) -> None:
    _set_online(mock_fireplace, fireplace_state, online)
    entry = await _setup(hass)

    for ent in _entities(hass, entry):
        state = hass.states.get(ent.entity_id)
        assert state is not None, ent.entity_id
        if ent.unique_id == CONNECTIVITY_UID:
            assert state.state == connectivity
        elif online is False:
            assert state.state == STATE_UNAVAILABLE, ent.entity_id
        else:
            assert state.state != STATE_UNAVAILABLE, ent.entity_id


async def test_dropping_offline_and_recovering(
    hass: HomeAssistant,
    mock_client,
    mock_fireplace,
    fireplace_state: FireplaceState,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_online(mock_fireplace, fireplace_state, True)
    entry = await _setup(hass)
    coord = entry.runtime_data.coordinators[0]
    ents = _entities(hass, entry)

    _set_online(mock_fireplace, fireplace_state, False)
    with caplog.at_level(logging.WARNING):
        await coord.async_refresh()
        await coord.async_refresh()
    await hass.async_block_till_done()
    assert caplog.text.count("is offline in Napoleon's cloud") == 1
    for ent in ents:
        expected = STATE_OFF if ent.unique_id == CONNECTIVITY_UID else STATE_UNAVAILABLE
        assert hass.states.get(ent.entity_id).state == expected, ent.entity_id

    _set_online(mock_fireplace, fireplace_state, True)
    await coord.async_refresh()
    await hass.async_block_till_done()
    for ent in ents:
        assert hass.states.get(ent.entity_id).state != STATE_UNAVAILABLE, ent.entity_id


async def test_connectivity_unavailable_when_cloud_unreachable(
    hass: HomeAssistant, mock_client, mock_fireplace, fireplace_state: FireplaceState
) -> None:
    from pynapoleon import NapoleonConnectionError

    _set_online(mock_fireplace, fireplace_state, True)
    entry = await _setup(hass)
    mock_fireplace.refresh.side_effect = NapoleonConnectionError("down")
    await entry.runtime_data.coordinators[0].async_refresh()
    await hass.async_block_till_done()

    eid = er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, CONNECTIVITY_UID)
    assert hass.states.get(eid).state == STATE_UNAVAILABLE
