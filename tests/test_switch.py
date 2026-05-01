"""Test the switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.napoleon.const import DOMAIN


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


async def test_switch_state_reflects_coordinator(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    states = hass.states.async_entity_ids(SWITCH_DOMAIN)
    assert len(states) == 1
    state = hass.states.get(states[0])
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_turn_on_off_calls_set_power(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # Start with power off so turn_on isn't a no-op
    mock_fireplace.state.power = False
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)

    [entity_id] = hass.states.async_entity_ids(SWITCH_DOMAIN)
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_fireplace.set_power.assert_awaited_once_with(True)
    assert mock_fireplace.refresh.await_count >= 2  # initial + post-write

    # Now turn off
    mock_fireplace.state.power = True
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_fireplace.set_power.assert_awaited_with(False)


async def test_switch_no_op_writes_suppressed(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # Power already on; turn_on should not call set_power
    await _setup(hass)
    [entity_id] = hass.states.async_entity_ids(SWITCH_DOMAIN)
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_fireplace.set_power.assert_not_awaited()


async def test_switch_unique_id_and_device_info(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    [entity_id] = hass.states.async_entity_ids(SWITCH_DOMAIN)
    entity = ent_reg.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == "AC000W032261383_power"
    assert entity.device_id is not None
    device = dev_reg.async_get(entity.device_id)
    assert device is not None
    assert (DOMAIN, "AC000W032261383") in device.identifiers
    assert device.manufacturer == "Napoleon"
    assert device.model == "Astound"
    assert device.serial_number == "AC000W032261383"
