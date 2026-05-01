"""Test the switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
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

DSN = "AC000W032261383"


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


def _ent(hass: HomeAssistant, suffix: str) -> str:
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, f"{DSN}_{suffix}")
    assert eid is not None, f"entity not found for suffix {suffix}"
    return eid


async def test_switch_state_reflects_coordinator(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    states = hass.states.async_entity_ids(SWITCH_DOMAIN)
    # Power + 4 toggles
    assert len(states) == 5
    state = hass.states.get(_ent(hass, "power"))
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_turn_on_off_calls_set_power(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.power = False
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)

    eid = _ent(hass, "power")
    assert hass.states.get(eid).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    mock_fireplace.set_power.assert_awaited_once_with(True)
    assert mock_fireplace.refresh.await_count >= 2

    mock_fireplace.state.power = True
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    mock_fireplace.set_power.assert_awaited_with(False)


async def test_switch_no_op_writes_suppressed(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    eid = _ent(hass, "power")
    assert hass.states.get(eid).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    mock_fireplace.set_power.assert_not_awaited()


async def test_switch_unique_id_and_device_info(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    eid = _ent(hass, "power")
    entity = ent_reg.async_get(eid)
    assert entity is not None
    assert entity.unique_id == f"{DSN}_power"
    assert entity.device_id is not None
    device = dev_reg.async_get(entity.device_id)
    assert device is not None
    assert (DOMAIN, DSN) in device.identifiers
    assert device.manufacturer == "Napoleon"
    assert device.model == "Astound"
    assert device.serial_number == DSN


@pytest.mark.parametrize(
    ("suffix", "state_attr", "setter"),
    [
        ("eco_mode", "eco_mode", "set_eco_mode"),
        ("boost_mode", "boost_mode", "set_boost_mode"),
        ("ember_bed_cycling", "ember_bed_cycling", "set_ember_bed_cycling"),
        ("top_light_cycling", "top_light_cycling", "set_top_light_cycling"),
    ],
)
async def test_toggle_switch_state_and_set(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_fireplace: MagicMock,
    suffix: str,
    state_attr: str,
    setter: str,
) -> None:
    setattr(mock_fireplace.state, state_attr, False)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)

    eid = _ent(hass, suffix)
    state = hass.states.get(eid)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    getattr(mock_fireplace, setter).assert_awaited_once_with(True)

    setattr(mock_fireplace.state, state_attr, True)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    getattr(mock_fireplace, setter).assert_awaited_with(False)


@pytest.mark.parametrize(
    ("suffix", "state_attr", "setter"),
    [
        ("eco_mode", "eco_mode", "set_eco_mode"),
        ("boost_mode", "boost_mode", "set_boost_mode"),
        ("ember_bed_cycling", "ember_bed_cycling", "set_ember_bed_cycling"),
        ("top_light_cycling", "top_light_cycling", "set_top_light_cycling"),
    ],
)
async def test_toggle_switch_no_op_suppressed(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_fireplace: MagicMock,
    suffix: str,
    state_attr: str,
    setter: str,
) -> None:
    setattr(mock_fireplace.state, state_attr, True)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    eid = _ent(hass, suffix)
    assert hass.states.get(eid).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    getattr(mock_fireplace, setter).assert_not_awaited()


async def test_toggle_switch_unique_ids(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup(hass)
    for suffix in (
        "eco_mode",
        "boost_mode",
        "ember_bed_cycling",
        "top_light_cycling",
    ):
        # _ent asserts the unique_id resolves
        _ent(hass, suffix)
