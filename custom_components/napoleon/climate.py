"""Climate platform: heater stage + setpoint."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NapoleonConfigEntry
from .coordinator import NapoleonCoordinator
from .entity import NapoleonEntity

PRESET_LOW = "low"
PRESET_HIGH = "high"

_HEATER_TO_PRESET = {1: PRESET_LOW, 2: PRESET_HIGH}
_PRESET_TO_HEATER = {PRESET_LOW: 1, PRESET_HIGH: 2}

SETPOINT_MIN_C = 18
SETPOINT_MAX_C = 23


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NapoleonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(NapoleonClimate(coord) for coord in entry.runtime_data.coordinators)


class NapoleonClimate(NapoleonEntity, ClimateEntity):
    """Heater + setpoint exposed as a climate entity."""

    _attr_translation_key = "fireplace"
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_min_temp = SETPOINT_MIN_C
    _attr_max_temp = SETPOINT_MAX_C
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [PRESET_LOW, PRESET_HIGH]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "climate")

    @property
    def hvac_mode(self) -> HVACMode | None:
        data = self.coordinator.data
        if data is None or data.heater is None:
            return None
        return HVACMode.OFF if data.heater == 0 else HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        data = self.coordinator.data
        if data is None or data.heater is None:
            return None
        return _HEATER_TO_PRESET.get(data.heater)

    @property
    def target_temperature(self) -> float | None:
        data = self.coordinator.data
        if data is None or data.setpoint_c is None:
            return None
        return float(data.setpoint_c)

    @property
    def current_temperature(self) -> float | None:
        # Napoleon Astound exposes no ambient temperature reading.
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        data = self.coordinator.data
        current = data.heater if data is not None else None
        if hvac_mode == HVACMode.OFF:
            if current == 0:
                return
            await self.coordinator.fireplace.set_heater(0)
        elif hvac_mode == HVACMode.HEAT:
            if current in (1, 2):
                return
            # Default to low when turning on.
            await self.coordinator.fireplace.set_heater(1)
        else:
            raise ValueError(f"Unsupported hvac_mode: {hvac_mode}")
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        target = _PRESET_TO_HEATER.get(preset_mode)
        if target is None:
            raise ValueError(f"Unsupported preset_mode: {preset_mode}")
        data = self.coordinator.data
        if data is not None and data.heater == target:
            return
        await self.coordinator.fireplace.set_heater(target)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        new_value = int(round(float(temp)))
        new_value = max(SETPOINT_MIN_C, min(SETPOINT_MAX_C, new_value))
        data = self.coordinator.data
        if data is not None and data.setpoint_c == new_value:
            return
        await self.coordinator.fireplace.set_setpoint_c(new_value)
        await self.coordinator.async_request_refresh()
