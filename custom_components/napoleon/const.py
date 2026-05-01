"""Constants for the Napoleon Fireplace integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "napoleon"
MANUFACTURER = "Napoleon"

PLATFORMS: list[str] = ["light", "switch"]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"  # noqa: S105 - field name, not a value

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
