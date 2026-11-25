"""Binary sensor platform: cloud connectivity of each fireplace."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
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
    async_add_entities(
        NapoleonConnectivitySensor(coord) for coord in entry.runtime_data.coordinators
    )


class NapoleonConnectivitySensor(NapoleonEntity, BinarySensorEntity):
    """Whether the fireplace's Wi-Fi module is connected to Napoleon's cloud.

    Stays available while the fireplace is offline (that is what it reports),
    so it can drive "fireplace dropped off Wi-Fi" alerts.
    """

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "connectivity")

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return None if data is None else data.online
