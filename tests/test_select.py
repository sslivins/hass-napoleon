"""Test the select platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_EMAIL, CONF_PASSWORD, STATE_UNKNOWN
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
    eid = ent_reg.async_get_entity_id(SELECT_DOMAIN, DOMAIN, "AC000W032261383_favourite")
    assert eid is not None, "favourite select not registered"
    return eid


async def test_entity_registered(hass: HomeAssistant, mock_client: MagicMock) -> None:
    await _setup(hass)
    _ent_id(hass)


async def test_options_match_pynapoleon(hass: HomeAssistant, mock_client: MagicMock) -> None:
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.attributes["options"] == [
        "partytime",
        "campfirewarmth",
        "summerday",
        "glowingsunset",
    ]


async def test_current_option_when_unset(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Fixture has current_favourite=None -> entity reports unknown."""
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_current_option_reflects_state(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state = FireplaceState(current_favourite="partytime")
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.state == "partytime"


async def test_current_option_unknown_value_is_none(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    """A value not in FAVOURITES surfaces as unknown rather than crashing."""
    mock_fireplace.state = FireplaceState(current_favourite="bogus")
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    state = hass.states.get(_ent_id(hass))
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_select_option_calls_apply(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    eid = _ent_id(hass)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eid, ATTR_OPTION: "campfirewarmth"},
        blocking=True,
    )
    mock_fireplace.apply_favourite.assert_awaited_once_with("campfirewarmth")
