"""Number platform: flame intensity controls."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NapoleonConfigEntry
from .coordinator import NapoleonCoordinator
from .entity import NapoleonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NapoleonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[NumberEntity] = []
    for coord in entry.runtime_data.coordinators:
        entities.append(NapoleonFlameSpeedNumber(coord))
        entities.append(NapoleonOrangeFlameNumber(coord))
        entities.append(NapoleonYellowFlameNumber(coord))
    async_add_entities(entities)


class _NapoleonNumberBase(NapoleonEntity, NumberEntity):
    """Common base for Napoleon number entities."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1


class NapoleonFlameSpeedNumber(_NapoleonNumberBase):
    """Flame speed (1..5)."""

    _attr_translation_key = "flame_speed"
    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "flame_speed")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None or data.flame_speed is None:
            return None
        return float(data.flame_speed)

    async def async_set_native_value(self, value: float) -> None:
        new_value = int(value)
        current = self.native_value
        if current is not None and int(current) == new_value:
            return
        await self.coordinator.fireplace.set_flame_speed(new_value)
        await self.coordinator.async_request_refresh()


class NapoleonOrangeFlameNumber(_NapoleonNumberBase):
    """Orange flame intensity (0..5)."""

    _attr_translation_key = "orange_flame"
    _attr_native_min_value = 0
    _attr_native_max_value = 5
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "orange_flame")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None or data.orange_flame is None:
            return None
        return float(data.orange_flame)

    async def async_set_native_value(self, value: float) -> None:
        new_value = int(value)
        current = self.native_value
        if current is not None and int(current) == new_value:
            return
        await self.coordinator.fireplace.set_orange_flame(new_value)
        await self.coordinator.async_request_refresh()


class NapoleonYellowFlameNumber(_NapoleonNumberBase):
    """Yellow flame intensity (0..5)."""

    _attr_translation_key = "yellow_flame"
    _attr_native_min_value = 0
    _attr_native_max_value = 5
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "yellow_flame")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None or data.yellow_flame is None:
            return None
        return float(data.yellow_flame)

    async def async_set_native_value(self, value: float) -> None:
        new_value = int(value)
        current = self.native_value
        if current is not None and int(current) == new_value:
            return
        await self.coordinator.fireplace.set_yellow_flame(new_value)
        await self.coordinator.async_request_refresh()
