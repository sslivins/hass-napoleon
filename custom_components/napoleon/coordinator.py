"""DataUpdateCoordinator for Napoleon fireplaces."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pynapoleon import (
    Fireplace,
    FireplaceState,
    NapoleonAuthError,
    NapoleonConnectionError,
    NapoleonError,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class NapoleonCoordinator(DataUpdateCoordinator[FireplaceState]):
    """Polling coordinator for a single Napoleon fireplace.

    One coordinator per device; the integration creates one for each fireplace
    discovered on the account at setup time.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        fireplace: Fireplace,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {fireplace.dsn}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.fireplace = fireplace

    async def async_set_power(self, on: bool) -> None:
        """Write power and reflect it locally right away.

        Entities gate writes on ``data.power``; without this, a follow-up
        command issued before the (debounced) refresh lands would still see
        the fireplace as off.
        """
        await self.fireplace.set_power(on)
        if self.data is not None and self.data.power is not on:
            self.async_set_updated_data(dataclasses.replace(self.data, power=on))

    async def _async_update_data(self) -> FireplaceState:
        try:
            return await self.fireplace.refresh()
        except NapoleonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NapoleonConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except NapoleonError as err:
            raise UpdateFailed(str(err)) from err
