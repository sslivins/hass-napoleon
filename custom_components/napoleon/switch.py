"""Switch platform: power and miscellaneous toggle features."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NapoleonConfigEntry
from .coordinator import NapoleonCoordinator
from .entity import NapoleonEntity

if TYPE_CHECKING:
    from pynapoleon import FireplaceState


@dataclass(frozen=True, kw_only=True)
class NapoleonToggleDescription(SwitchEntityDescription):
    """Describes a fireplace boolean toggle exposed as a switch."""

    value_fn: Callable[[FireplaceState], bool | None]
    setter_name: str
    entity_category: EntityCategory | None = None


TOGGLES: tuple[NapoleonToggleDescription, ...] = (
    NapoleonToggleDescription(
        key="eco_mode",
        translation_key="eco_mode",
        value_fn=lambda s: s.eco_mode,
        setter_name="set_eco_mode",
    ),
    NapoleonToggleDescription(
        key="boost_mode",
        translation_key="boost_mode",
        value_fn=lambda s: s.boost_mode,
        setter_name="set_boost_mode",
    ),
    NapoleonToggleDescription(
        key="ember_bed_cycling",
        translation_key="ember_bed_cycling",
        value_fn=lambda s: s.ember_bed_cycling,
        setter_name="set_ember_bed_cycling",
    ),
    NapoleonToggleDescription(
        key="top_light_cycling",
        translation_key="top_light_cycling",
        value_fn=lambda s: s.top_light_cycling,
        setter_name="set_top_light_cycling",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NapoleonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[SwitchEntity] = []
    for coord in entry.runtime_data.coordinators:
        entities.append(NapoleonPowerSwitch(coord))
        entities.extend(NapoleonToggleSwitch(coord, desc) for desc in TOGGLES)
    async_add_entities(entities)


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


class NapoleonToggleSwitch(NapoleonEntity, SwitchEntity):
    """Generic boolean fireplace feature toggle."""

    entity_description: NapoleonToggleDescription

    def __init__(
        self,
        coordinator: NapoleonCoordinator,
        description: NapoleonToggleDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    async def _call_setter(self, value: bool) -> None:
        setter: Callable[[bool], Awaitable[None]] = getattr(
            self.coordinator.fireplace, self.entity_description.setter_name
        )
        await setter(value)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.is_on is True:
            return
        await self._call_setter(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on is False:
            return
        await self._call_setter(False)
