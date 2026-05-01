"""Select platform: favourite scene picker."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pynapoleon.const import FAVOURITES

from . import NapoleonConfigEntry
from .coordinator import NapoleonCoordinator
from .entity import NapoleonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NapoleonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[SelectEntity] = []
    for coord in entry.runtime_data.coordinators:
        entities.append(NapoleonFavouriteSelect(coord))
    async_add_entities(entities)


class NapoleonFavouriteSelect(NapoleonEntity, SelectEntity):
    """Pick the active Napoleon favourite scene."""

    _attr_translation_key = "favourite"
    _attr_name = None
    _attr_icon = "mdi:palette"
    _attr_options = list(FAVOURITES)

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "favourite")

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if data is None or data.current_favourite is None:
            return None
        value = data.current_favourite
        return value if value in FAVOURITES else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.fireplace.apply_favourite(option)
        await self.coordinator.async_request_refresh()
