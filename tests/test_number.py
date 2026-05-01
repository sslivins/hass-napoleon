"""Test the number platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
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


def _ent_id(hass: HomeAssistant, suffix: str) -> str:
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id(NUMBER_DOMAIN, DOMAIN, f"AC000W032261383_{suffix}")
    assert eid is not None, f"entity not found for suffix {suffix}"
    return eid


async def test_entities_registered(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """All three number entities are registered with stable unique_ids."""
    await _setup(hass)
    for suffix in ("flame_speed", "orange_flame", "yellow_flame"):
        _ent_id(hass, suffix)


async def test_native_values_reflect_state(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Number entities expose the current FireplaceState values."""
    await _setup(hass)
    flame = hass.states.get(_ent_id(hass, "flame_speed"))
    orange = hass.states.get(_ent_id(hass, "orange_flame"))
    yellow = hass.states.get(_ent_id(hass, "yellow_flame"))
    assert flame is not None and float(flame.state) == 3.0
    assert orange is not None and float(orange.state) == 2.0
    assert yellow is not None and float(yellow.state) == 1.0


async def test_set_flame_speed_calls_setter(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    """Setting a new value writes through and refreshes."""
    await _setup(hass)
    eid = _ent_id(hass, "flame_speed")
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: eid, ATTR_VALUE: 5},
        blocking=True,
    )
    mock_fireplace.set_flame_speed.assert_awaited_once_with(5)


async def test_set_orange_flame_calls_setter(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    eid = _ent_id(hass, "orange_flame")
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: eid, ATTR_VALUE: 4},
        blocking=True,
    )
    mock_fireplace.set_orange_flame.assert_awaited_once_with(4)


async def test_set_yellow_flame_calls_setter(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    eid = _ent_id(hass, "yellow_flame")
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: eid, ATTR_VALUE: 0},
        blocking=True,
    )
    mock_fireplace.set_yellow_flame.assert_awaited_once_with(0)


async def test_setting_same_value_is_no_op(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    """Writing the current value does not call the setter."""
    await _setup(hass)
    eid = _ent_id(hass, "flame_speed")
    # state is 3 from fixture
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: eid, ATTR_VALUE: 3},
        blocking=True,
    )
    mock_fireplace.set_flame_speed.assert_not_called()


async def test_bounds(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Min/max values are exposed correctly per entity."""
    await _setup(hass)
    flame = hass.states.get(_ent_id(hass, "flame_speed"))
    orange = hass.states.get(_ent_id(hass, "orange_flame"))
    assert flame is not None
    assert flame.attributes["min"] == 1
    assert flame.attributes["max"] == 5
    assert flame.attributes["step"] == 1
    assert orange is not None
    assert orange.attributes["min"] == 0
    assert orange.attributes["max"] == 5
