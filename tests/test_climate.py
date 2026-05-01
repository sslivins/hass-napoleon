"""Test the climate platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pynapoleon import FireplaceState
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


def _ent_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id(CLIMATE_DOMAIN, DOMAIN, "AC000W032261383_climate")
    assert eid is not None, "climate entity not registered"
    return eid


async def test_entity_registered(hass: HomeAssistant, mock_client: MagicMock) -> None:
    await _setup(hass)
    _ent_id(hass)


async def test_state_off_when_heater_zero(hass: HomeAssistant, mock_client: MagicMock) -> None:
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes.get("preset_mode") is None
    assert state.attributes.get("temperature") == 20
    assert state.attributes.get("min_temp") == 18
    assert state.attributes.get("max_temp") == 23


async def test_state_heat_low(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state = FireplaceState(heater=1, setpoint_c=21)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get("preset_mode") == "low"


async def test_state_heat_high(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state = FireplaceState(heater=2, setpoint_c=22)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get("preset_mode") == "high"


async def test_set_hvac_mode_heat_calls_set_heater_low(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_fireplace.set_heater.assert_awaited_once_with(1)


async def test_set_hvac_mode_off_calls_set_heater_zero(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state = FireplaceState(heater=2, setpoint_c=20)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_fireplace.set_heater.assert_awaited_once_with(0)


async def test_set_hvac_mode_heat_noop_when_already_on(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state = FireplaceState(heater=2, setpoint_c=20)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_fireplace.set_heater.assert_not_awaited()


async def test_set_preset_low(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_PRESET_MODE: "low"},
        blocking=True,
    )
    mock_fireplace.set_heater.assert_awaited_once_with(1)


async def test_set_preset_high(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_PRESET_MODE: "high"},
        blocking=True,
    )
    mock_fireplace.set_heater.assert_awaited_once_with(2)


async def test_set_temperature_calls_setpoint(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_TEMPERATURE: 22},
        blocking=True,
    )
    mock_fireplace.set_setpoint_c.assert_awaited_once_with(22)


async def test_set_temperature_noop_when_unchanged(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    """Fixture setpoint is 20 — setting 20 again should be a no-op."""
    await _setup(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _ent_id(hass), ATTR_TEMPERATURE: 20},
        blocking=True,
    )
    mock_fireplace.set_setpoint_c.assert_not_awaited()
