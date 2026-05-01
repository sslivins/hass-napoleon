"""The Napoleon Fireplace integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from pynapoleon import (
    NapoleonAuthError,
    NapoleonClient,
    NapoleonConnectionError,
    NapoleonError,
)

from .const import PLATFORMS
from .coordinator import NapoleonCoordinator


@dataclass
class NapoleonRuntimeData:
    """Per-config-entry runtime state."""

    client: NapoleonClient
    coordinators: list[NapoleonCoordinator]


type NapoleonConfigEntry = ConfigEntry[NapoleonRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: NapoleonConfigEntry) -> bool:
    """Set up Napoleon Fireplace from a config entry."""
    client = NapoleonClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await client.login()
        fireplaces = await client.fireplaces()
    except NapoleonAuthError as err:
        await client.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except (NapoleonConnectionError, NapoleonError) as err:
        await client.close()
        raise ConfigEntryNotReady(str(err)) from err

    if not fireplaces:
        await client.close()
        raise ConfigEntryNotReady("No Napoleon fireplaces found on this account")

    coordinators: list[NapoleonCoordinator] = []
    for fp in fireplaces:
        coord = NapoleonCoordinator(hass, entry, fp)
        await coord.async_config_entry_first_refresh()
        coordinators.append(coord)

    entry.runtime_data = NapoleonRuntimeData(client=client, coordinators=coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NapoleonConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
