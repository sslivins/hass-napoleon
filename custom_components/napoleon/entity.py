"""Base entity for Napoleon Fireplace integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NapoleonCoordinator


class NapoleonEntity(CoordinatorEntity[NapoleonCoordinator]):
    """Common base for all Napoleon entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NapoleonCoordinator,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        info = coordinator.fireplace.info
        self._attr_unique_id = f"{info.dsn}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.dsn)},
            manufacturer=info.manufacturer or MANUFACTURER,
            model=info.model,
            name=info.name,
            sw_version=info.sw_version,
            serial_number=info.dsn,
        )
