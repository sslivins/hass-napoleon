"""Switch platform: main fireplace power."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities(NapoleonPowerSwitch(coord) for coord in entry.runtime_data.coordinators)


class NapoleonPowerSwitch(NapoleonEntity, SwitchEntity):
    """Main on/off switch for the fireplace."""

    _attr_translation_key = "fireplace_power"
    _attr_name = None  # use device name only (has_entity_name=True)

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "power")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.power if self.coordinator.data else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.is_on:
            return
        await self.coordinator.fireplace.set_power(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on is False:
            return
        await self.coordinator.fireplace.set_power(False)
        await self.coordinator.async_request_refresh()
