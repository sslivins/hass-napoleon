"""Base entity for Napoleon Fireplace integration."""

from __future__ import annotations

from homeassistant.exceptions import ServiceValidationError
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

    # Power is a master switch: while it is off the device silently discards
    # every other write and, on power-up, resumes its last stored state
    # (verified live). Entities therefore stay available while off (only
    # cloud failures make them unavailable) and route writes through the
    # helpers below so nothing is sent that the device would ignore.

    @property
    def power_off(self) -> bool:
        data = self.coordinator.data
        return data is not None and data.power is False

    async def _async_ensure_power_on(self) -> None:
        """Power the fireplace on before an 'activate' style write.

        No settle delay is needed: a write sent immediately after power-on
        sticks.
        """
        if self.power_off:
            await self.coordinator.async_set_power(True)

    def _raise_if_power_off(self) -> None:
        """Reject a settings write the device would discard while off."""
        if self.power_off:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="fireplace_off",
                translation_placeholders={"name": self.coordinator.fireplace.info.name},
            )
