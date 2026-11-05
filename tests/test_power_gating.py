"""Power is the master switch: behaviour of every entity while it is off.

Verified live against the device: while powered off it silently discards
writes to everything except power, and on power-up it resumes its last
stored state. So entities stay available while off, report what is
physically true, power the unit up for 'activate' requests, and reject
settings writes rather than sending them.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pynapoleon import FireplaceState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.napoleon.const import DOMAIN

DSN = "AC000W032261383"

ALL_ENTITIES = [
    ("switch", "power"),
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


async def _setup(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _ent(hass: HomeAssistant, platform: str, suffix: str) -> str:
    eid = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{DSN}_{suffix}")
    assert eid is not None, f"entity not found for {platform}.{suffix}"
    return eid


def _set_off(mock_fireplace: MagicMock, **overrides: Any) -> None:
    base = {
        "power": False,
        "flame_speed": 3,
        "orange_flame": 2,
        "yellow_flame": 1,
        "heater": 0,
        "setpoint_c": 20,
        "eco_mode": True,
        "boost_mode": False,
        "ember_bed_rgb": (255, 100, 0),
        "ember_bed_brightness": 2,
        "ember_bed_cycling": False,
        "top_light_rgb": (0, 0, 255),
        "top_light_cycling": False,
        "current_favourite": "partytime",
    }
    base.update(overrides)
    mock_fireplace.state = FireplaceState(**base)
    mock_fireplace.refresh.return_value = mock_fireplace.state


def _record_calls(mock_fireplace: MagicMock) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []
    for name in (
        "set_power",
        "set_heater",
        "set_setpoint_c",
        "set_ember_bed_brightness",
        "set_ember_bed_rgb",
        "set_top_light_rgb",
        "set_flame_speed",
        "set_eco_mode",
        "apply_favourite",
    ):
        getattr(mock_fireplace, name).side_effect = lambda *a, _n=name: calls.append(
            (_n, a[0] if a else None)
        )
    return calls


async def test_power_off_entities_available_and_report_off(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # Stored state says the heater and lights are on; the unit is dark.
    _set_off(mock_fireplace, heater=2)
    await _setup(hass)

    for platform, suffix in ALL_ENTITIES:
        state = hass.states.get(_ent(hass, platform, suffix))
        assert state is not None
        assert state.state != STATE_UNAVAILABLE, f"{platform}.{suffix} unavailable"

    assert hass.states.get(_ent(hass, "switch", "power")).state == STATE_OFF
    climate = hass.states.get(_ent(hass, "climate", "climate"))
    assert climate.state == "off"
    assert climate.attributes.get("preset_mode") is None
    assert hass.states.get(_ent(hass, "light", "ember_bed_light")).state == STATE_OFF
    assert hass.states.get(_ent(hass, "light", "top_light")).state == STATE_OFF
    # Settings keep their stored values.
    assert hass.states.get(_ent(hass, "number", "flame_speed")).state == "3.0"
    assert hass.states.get(_ent(hass, "switch", "eco_mode")).state == STATE_ON
    assert hass.states.get(_ent(hass, "select", "favourite")).state == "partytime"


async def test_coordinator_failure_still_marks_unavailable(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    from pynapoleon import NapoleonConnectionError

    _set_off(mock_fireplace)
    await _setup(hass)
    mock_fireplace.refresh.side_effect = NapoleonConnectionError("down")
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await entry.runtime_data.coordinators[0].async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(_ent(hass, "climate", "climate")).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("stored_heater", "expected"),
    [
        (0, [("set_power", True), ("set_heater", 1)]),
        # Power-up resumes the stored stage, so no heater write is needed.
        (2, [("set_power", True)]),
    ],
)
async def test_climate_heat_while_off_powers_on(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_fireplace: MagicMock,
    stored_heater: int,
    expected: list[tuple[str, Any]],
) -> None:
    _set_off(mock_fireplace, heater=stored_heater)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _ent(hass, "climate", "climate"), "hvac_mode": "heat"},
        blocking=True,
    )
    assert calls == expected


async def test_climate_preset_while_off_powers_on_then_sets_stage(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    _set_off(mock_fireplace, heater=1)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: _ent(hass, "climate", "climate"), "preset_mode": "high"},
        blocking=True,
    )
    assert calls == [("set_power", True), ("set_heater", 2)]


async def test_turning_things_off_while_off_is_a_noop(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    _set_off(mock_fireplace, heater=2)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _ent(hass, "climate", "climate"), "hvac_mode": "off"},
        blocking=True,
    )
    for suffix in ("ember_bed_light", "top_light"):
        await hass.services.async_call(
            "light", "turn_off", {ATTR_ENTITY_ID: _ent(hass, "light", suffix)}, blocking=True
        )
    assert calls == []


async def test_heater_off_while_on_never_cuts_master_power(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.heater = 1
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _ent(hass, "climate", "climate"), "hvac_mode": "off"},
        blocking=True,
    )
    assert calls == [("set_heater", 0)]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        # Power-up resumes stored brightness 2.
        ({}, [("set_power", True)]),
        ({"brightness": 255}, [("set_power", True), ("set_ember_bed_brightness", 5)]),
    ],
)
async def test_ember_light_on_while_off_powers_on(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_fireplace: MagicMock,
    data: dict[str, Any],
    expected: list[tuple[str, Any]],
) -> None:
    _set_off(mock_fireplace)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: _ent(hass, "light", "ember_bed_light"), **data},
        blocking=True,
    )
    assert calls == expected


async def test_ember_light_on_while_off_with_stored_zero_sets_max(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    _set_off(mock_fireplace, ember_bed_brightness=0)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: _ent(hass, "light", "ember_bed_light")},
        blocking=True,
    )
    assert calls == [("set_power", True), ("set_ember_bed_brightness", 5)]


async def test_top_light_on_while_off_powers_on(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    _set_off(mock_fireplace)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: _ent(hass, "light", "top_light")},
        blocking=True,
    )
    assert calls == [("set_power", True)]


async def test_favourite_while_off_powers_on_then_applies(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    _set_off(mock_fireplace)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: _ent(hass, "select", "favourite"), "option": "summerday"},
        blocking=True,
    )
    assert calls == [("set_power", True), ("apply_favourite", "summerday")]


@pytest.mark.parametrize(
    ("domain", "service", "suffix", "data"),
    [
        ("number", "set_value", "flame_speed", {"value": 5}),
        ("switch", "turn_off", "eco_mode", {}),
        ("climate", "set_temperature", "climate", {"temperature": 22}),
    ],
)
async def test_settings_writes_while_off_are_rejected(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_fireplace: MagicMock,
    domain: str,
    service: str,
    suffix: str,
    data: dict[str, Any],
) -> None:
    _set_off(mock_fireplace)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: _ent(hass, domain, suffix), **data},
            blocking=True,
        )
    assert exc.value.translation_key == "fireplace_off"
    assert calls == []


async def test_settings_noop_while_off_does_not_raise(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    _set_off(mock_fireplace)
    await _setup(hass)
    calls = _record_calls(mock_fireplace)
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: _ent(hass, "number", "flame_speed"), "value": 3},
        blocking=True,
    )
    assert calls == []


async def test_followup_commands_after_auto_power_on_see_power_on(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # Refresh is debounced (10 s cooldown), so a quick follow-up command must
    # not depend on it to learn that power is now on.
    _set_off(mock_fireplace, heater=1)
    await _setup(hass)
    coord = hass.config_entries.async_entries(DOMAIN)[0].runtime_data.coordinators[0]
    coord.async_request_refresh = AsyncMock()
    calls = _record_calls(mock_fireplace)

    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: _ent(hass, "light", "ember_bed_light")}, blocking=True
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: _ent(hass, "number", "flame_speed"), "value": 5},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _ent(hass, "climate", "climate"), "hvac_mode": "off"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: _ent(hass, "switch", "power")}, blocking=True
    )
    assert calls == [
        ("set_power", True),
        ("set_flame_speed", 5),
        ("set_heater", 0),
        ("set_power", False),
    ]
