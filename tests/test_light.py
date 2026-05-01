"""Test the light platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
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
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.napoleon.const import DOMAIN
from custom_components.napoleon.light import (
    _device_to_ha_brightness,
    _ha_to_device_brightness,
    _scale_rgb_to_brightness,
)


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


def _ember_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, "AC000W032261383_ember_bed_light")
    assert entry is not None
    return entry


def _top_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, "AC000W032261383_top_light")
    assert entry is not None
    return entry


# ---------------------------------------------------------------------------
# pure-function tests for the brightness mapping helpers
# ---------------------------------------------------------------------------


def test_brightness_mapping_round_trip() -> None:
    # Device 0 maps to HA 0
    assert _device_to_ha_brightness(0) == 0
    # Device 5 -> HA 255 -> device 5
    assert _device_to_ha_brightness(5) == 255
    assert _ha_to_device_brightness(255) == 5
    # HA 1 stays > 0 on the device
    assert _ha_to_device_brightness(1) == 1
    # HA 0 maps to device 0
    assert _ha_to_device_brightness(0) == 0


def test_scale_rgb_to_brightness() -> None:
    # Scaling (255,0,0) to brightness 128 gives ~(128,0,0)
    assert _scale_rgb_to_brightness((255, 0, 0), 128) == (128, 0, 0)
    # Black + brightness becomes that brightness as white
    assert _scale_rgb_to_brightness((0, 0, 0), 100) == (100, 100, 100)
    # Clamped to 0..255
    assert _scale_rgb_to_brightness((10, 20, 5), 999)[0] <= 255


# ---------------------------------------------------------------------------
# entity registry / state
# ---------------------------------------------------------------------------


async def test_lights_register_and_reflect_state(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    light_entities = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(light_entities) == 2

    ember = hass.states.get(_ember_id(hass))
    assert ember is not None
    assert ember.state == STATE_ON  # brightness=2 > 0
    assert ember.attributes["brightness"] == _device_to_ha_brightness(2)
    assert ember.attributes["rgb_color"] == (255, 100, 0)

    top = hass.states.get(_top_id(hass))
    assert top is not None
    assert top.state == STATE_ON  # rgb=(0,0,255)
    assert top.attributes["rgb_color"] == (0, 0, 255)
    assert top.attributes["brightness"] == 255  # max channel is 255


async def test_ember_off_when_brightness_zero(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.ember_bed_brightness = 0
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    ember = hass.states.get(_ember_id(hass))
    assert ember is not None
    assert ember.state == STATE_OFF


async def test_top_off_when_rgb_zero(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.top_light_rgb = (0, 0, 0)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    top = hass.states.get(_top_id(hass))
    assert top is not None
    assert top.state == STATE_OFF


# ---------------------------------------------------------------------------
# turn_on / turn_off — ember_bed
# ---------------------------------------------------------------------------


async def test_ember_turn_on_with_brightness_and_rgb(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.ember_bed_brightness = 0
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _ember_id(hass),
            ATTR_BRIGHTNESS: 128,
            ATTR_RGB_COLOR: (10, 20, 30),
        },
        blocking=True,
    )
    mock_fireplace.set_ember_bed_rgb.assert_awaited_once_with((10, 20, 30))
    mock_fireplace.set_ember_bed_brightness.assert_awaited_once()
    # 128/255 * 5 ≈ 2.51 → 3
    assert mock_fireplace.set_ember_bed_brightness.await_args.args[0] == 3


async def test_ember_turn_on_no_args_when_off_uses_max(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.ember_bed_brightness = 0
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _ember_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_ember_bed_brightness.assert_awaited_once_with(5)


async def test_ember_turn_on_no_op_when_already_at_target(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # State has brightness=2 and rgb=(255,100,0). turn_on with same values → no writes.
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _ember_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_ember_bed_brightness.assert_not_awaited()
    mock_fireplace.set_ember_bed_rgb.assert_not_awaited()


async def test_ember_turn_off_writes_zero(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _ember_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_ember_bed_brightness.assert_awaited_once_with(0)


async def test_ember_turn_off_no_op_when_already_off(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.ember_bed_brightness = 0
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _ember_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_ember_bed_brightness.assert_not_awaited()


# ---------------------------------------------------------------------------
# turn_on / turn_off — top_light
# ---------------------------------------------------------------------------


async def test_top_turn_on_with_rgb(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _top_id(hass), ATTR_RGB_COLOR: (200, 150, 50)},
        blocking=True,
    )
    mock_fireplace.set_top_light_rgb.assert_awaited_once_with((200, 150, 50))


async def test_top_turn_on_with_brightness_scales_existing_color(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    # Current rgb is (0, 0, 255). brightness 128 → max channel becomes ~128.
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _top_id(hass), ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    mock_fireplace.set_top_light_rgb.assert_awaited_once()
    rgb = mock_fireplace.set_top_light_rgb.await_args.args[0]
    assert rgb == (0, 0, 128)


async def test_top_turn_on_when_off_uses_white(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.top_light_rgb = (0, 0, 0)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _top_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_top_light_rgb.assert_awaited_once_with((255, 255, 255))


async def test_top_turn_off_writes_black(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _top_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_top_light_rgb.assert_awaited_once_with((0, 0, 0))


async def test_top_turn_off_no_op_when_already_off(
    hass: HomeAssistant, mock_client: MagicMock, mock_fireplace: MagicMock
) -> None:
    mock_fireplace.state.top_light_rgb = (0, 0, 0)
    mock_fireplace.refresh.return_value = mock_fireplace.state
    await _setup(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _top_id(hass)},
        blocking=True,
    )
    mock_fireplace.set_top_light_rgb.assert_not_awaited()


# ---------------------------------------------------------------------------
# unique_id stability
# ---------------------------------------------------------------------------


async def test_unique_ids_include_dsn(hass: HomeAssistant, mock_client: MagicMock) -> None:
    await _setup(hass)
    ent_reg = er.async_get(hass)
    ember = ent_reg.async_get(_ember_id(hass))
    top = ent_reg.async_get(_top_id(hass))
    assert ember is not None and ember.unique_id == "AC000W032261383_ember_bed_light"
    assert top is not None and top.unique_id == "AC000W032261383_top_light"
