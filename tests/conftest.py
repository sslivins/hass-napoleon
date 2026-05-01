"""Common test fixtures for hass-napoleon."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pynapoleon import FireplaceInfo, FireplaceState

# pytest-homeassistant-custom-component auto-enables custom integrations via this
# fixture name (must be present even if it does nothing extra).


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # type: ignore[no-untyped-def]
    """Automatically enable loading of custom_components in every test."""
    yield


@pytest.fixture
def fireplace_state() -> FireplaceState:
    return FireplaceState(
        power=True,
        flame_speed=3,
        orange_flame=2,
        yellow_flame=1,
        heater=0,
        setpoint_c=20,
        eco_mode=False,
        boost_mode=False,
        ember_bed_rgb=(255, 100, 0),
        ember_bed_brightness=2,
        ember_bed_cycling=False,
        top_light_rgb=(0, 0, 255),
        top_light_cycling=False,
        current_favourite=None,
    )


@pytest.fixture
def fireplace_info() -> FireplaceInfo:
    return FireplaceInfo(
        dsn="AC000W032261383",
        name="Living Room",
        manufacturer="Napoleon",
        model="Astound",
        oem_model="Astound",
        sw_version=None,
        mac="aa:bb:cc:dd:ee:ff",
        lan_ip=None,
    )


@pytest.fixture
def mock_fireplace(fireplace_state: FireplaceState, fireplace_info: FireplaceInfo) -> MagicMock:
    """Build a fake pynapoleon.Fireplace for tests."""
    fp = MagicMock(name="Fireplace")
    fp.dsn = fireplace_info.dsn
    fp.name = fireplace_info.name
    fp.info = fireplace_info
    fp.state = fireplace_state
    fp.refresh = AsyncMock(return_value=fireplace_state)
    fp.set_power = AsyncMock(return_value=None)
    fp.set_flame_speed = AsyncMock(return_value=None)
    fp.set_orange_flame = AsyncMock(return_value=None)
    fp.set_yellow_flame = AsyncMock(return_value=None)
    fp.set_ember_bed_rgb = AsyncMock(return_value=None)
    fp.set_ember_bed_brightness = AsyncMock(return_value=None)
    fp.set_top_light_rgb = AsyncMock(return_value=None)
    fp.apply_favourite = AsyncMock(return_value=None)
    fp.set_heater = AsyncMock(return_value=None)
    fp.set_setpoint_c = AsyncMock(return_value=None)
    fp.set_eco_mode = AsyncMock(return_value=None)
    fp.set_boost_mode = AsyncMock(return_value=None)
    fp.set_ember_bed_cycling = AsyncMock(return_value=None)
    fp.set_top_light_cycling = AsyncMock(return_value=None)
    return fp


@pytest.fixture
def mock_client(mock_fireplace: MagicMock) -> Generator[MagicMock]:
    """Patch NapoleonClient everywhere the integration imports it."""
    instance = MagicMock(name="NapoleonClient")
    instance.login = AsyncMock(return_value=None)
    instance.fireplaces = AsyncMock(return_value=[mock_fireplace])
    instance.close = AsyncMock(return_value=None)

    with (
        patch("custom_components.napoleon.NapoleonClient", return_value=instance) as init_patch,
        patch(
            "custom_components.napoleon.config_flow.NapoleonClient",
            return_value=instance,
        ) as flow_patch,
    ):
        instance._init_patch = init_patch  # type: ignore[attr-defined]
        instance._flow_patch = flow_patch  # type: ignore[attr-defined]
        yield instance
