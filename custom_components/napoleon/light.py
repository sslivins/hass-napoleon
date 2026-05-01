"""Light platform: ember bed and top accent lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NapoleonConfigEntry
from .coordinator import NapoleonCoordinator
from .entity import NapoleonEntity

DEVICE_BRIGHTNESS_MAX = 5  # ember_bed_brightness range is 0..5 on the wire


def _ha_to_device_brightness(ha_brightness: int) -> int:
    """Map HA brightness 1..255 to device brightness 1..5 (round-half-up)."""
    if ha_brightness <= 0:
        return 0
    scaled = round(ha_brightness * DEVICE_BRIGHTNESS_MAX / 255)
    return max(1, min(DEVICE_BRIGHTNESS_MAX, scaled))


def _device_to_ha_brightness(device_brightness: int) -> int:
    """Map device brightness 0..5 back to HA 0..255."""
    if device_brightness <= 0:
        return 0
    return min(255, round(device_brightness * 255 / DEVICE_BRIGHTNESS_MAX))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NapoleonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[LightEntity] = []
    for coord in entry.runtime_data.coordinators:
        entities.append(NapoleonEmberBedLight(coord))
        entities.append(NapoleonTopLight(coord))
    async_add_entities(entities)


class NapoleonEmberBedLight(NapoleonEntity, LightEntity):
    """Ember bed accent light: native 0..5 brightness + RGB color."""

    _attr_translation_key = "ember_bed"
    _attr_name = "Ember bed"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "ember_bed_light")

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None or data.ember_bed_brightness is None:
            return None
        return data.ember_bed_brightness > 0

    @property
    def brightness(self) -> int | None:
        data = self.coordinator.data
        if data is None or data.ember_bed_brightness is None:
            return None
        return _device_to_ha_brightness(data.ember_bed_brightness)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        data = self.coordinator.data
        return data.ember_bed_rgb if data else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        fp = self.coordinator.fireplace
        wrote = False

        if ATTR_RGB_COLOR in kwargs:
            await fp.set_ember_bed_rgb(tuple(kwargs[ATTR_RGB_COLOR]))
            wrote = True

        if ATTR_BRIGHTNESS in kwargs:
            target = _ha_to_device_brightness(int(kwargs[ATTR_BRIGHTNESS]))
        elif not self.is_on:
            target = DEVICE_BRIGHTNESS_MAX
        else:
            target = None

        if target is not None:
            current = self.coordinator.data.ember_bed_brightness if self.coordinator.data else None
            if current != target:
                await fp.set_ember_bed_brightness(target)
                wrote = True

        if wrote:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on is False:
            return
        await self.coordinator.fireplace.set_ember_bed_brightness(0)
        await self.coordinator.async_request_refresh()


class NapoleonTopLight(NapoleonEntity, LightEntity):
    """Top accent light: RGB-only; brightness synthesized from max channel."""

    _attr_translation_key = "top_light"
    _attr_name = "Top light"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator: NapoleonCoordinator) -> None:
        super().__init__(coordinator, "top_light")

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None or data.top_light_rgb is None:
            return None
        return any(c > 0 for c in data.top_light_rgb)

    @property
    def brightness(self) -> int | None:
        data = self.coordinator.data
        if data is None or data.top_light_rgb is None:
            return None
        return max(data.top_light_rgb)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        data = self.coordinator.data
        return data.top_light_rgb if data else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        current = (self.coordinator.data.top_light_rgb if self.coordinator.data else None) or (
            255,
            255,
            255,
        )
        cur_max = max(current) if any(c > 0 for c in current) else 0

        new_rgb: tuple[int, int, int] | None = None

        if ATTR_RGB_COLOR in kwargs:
            new_rgb = tuple(kwargs[ATTR_RGB_COLOR])
            if ATTR_BRIGHTNESS in kwargs:
                new_rgb = _scale_rgb_to_brightness(new_rgb, int(kwargs[ATTR_BRIGHTNESS]))
        elif ATTR_BRIGHTNESS in kwargs:
            base = current if cur_max > 0 else (255, 255, 255)
            new_rgb = _scale_rgb_to_brightness(base, int(kwargs[ATTR_BRIGHTNESS]))
        elif cur_max == 0:
            new_rgb = (255, 255, 255)

        if new_rgb is not None and tuple(new_rgb) != tuple(current):
            await self.coordinator.fireplace.set_top_light_rgb(new_rgb)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on is False:
            return
        await self.coordinator.fireplace.set_top_light_rgb((0, 0, 0))
        await self.coordinator.async_request_refresh()


def _scale_rgb_to_brightness(
    rgb: tuple[int, int, int],
    target_brightness: int,
) -> tuple[int, int, int]:
    """Rescale RGB so its max channel equals target_brightness (clamped 0..255)."""
    target = max(0, min(255, target_brightness))
    cur_max = max(rgb)
    if cur_max == 0:
        return (target, target, target)
    factor = target / cur_max
    return (
        max(0, min(255, round(rgb[0] * factor))),
        max(0, min(255, round(rgb[1] * factor))),
        max(0, min(255, round(rgb[2] * factor))),
    )
