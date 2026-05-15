"""When fireplace power is off, every entity except the power switch is unavailable."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.napoleon.const import DOMAIN

DSN = "AC000W032261383"

# (platform domain, unique-id suffix) for every non-power entity the integration
# creates. Mirrors what each platform's async_setup_entry registers.
NON_POWER_ENTITIES = [
    ("climate", "climate"),
    ("light", "ember_bed_light"),
    ("light", "top_light"),
    ("number", "flame_speed"),
    ("number", "orange_flame"),
    ("number", "yellow_flame"),
    ("select", "favourite"),
    ("switch", "eco_mode"),
    ("switch", "boost_mode"),
    ("switch", "ember_bed_cycling"),
    ("switch", "top_light_cycling"),
]


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


def _ent(hass: HomeAssistant, platform: str, suffix: str) -> str:
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id(platform, DOMAIN, f"{DSN}_{suffix}")
    assert eid is not None, f"entity not found for {platform}.{suffix}"
    return eid


async def test_power_off_marks_non_power_entities_unavailable(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.power = False
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)

    # Power switch stays available so the user can turn the fireplace back on.
    power_state = hass.states.get(_ent(hass, "switch", "power"))
    assert power_state is not None
    assert power_state.state == STATE_OFF

    for platform, suffix in NON_POWER_ENTITIES:
        state = hass.states.get(_ent(hass, platform, suffix))
        assert state is not None, f"{platform}.{suffix} missing"
        assert state.state == STATE_UNAVAILABLE, (
            f"{platform}.{suffix} expected unavailable when power off, got {state.state}"
        )


async def test_power_on_all_entities_available(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # Default fixture has power=True.
    await _setup(hass)

    assert hass.states.get(_ent(hass, "switch", "power")).state == STATE_ON

    for platform, suffix in NON_POWER_ENTITIES:
        state = hass.states.get(_ent(hass, platform, suffix))
        assert state is not None, f"{platform}.{suffix} missing"
        assert state.state != STATE_UNAVAILABLE, (
            f"{platform}.{suffix} unexpectedly unavailable when power on"
        )
