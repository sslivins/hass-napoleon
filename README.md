<h1 align="center">
  <img src="custom_components/napoleon/brand/icon.png" width="96" alt="Napoleon Fireplace"><br>
  Napoleon Fireplace for Home Assistant
</h1>

<p align="center">
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="https://github.com/sslivins/hass-napoleon/releases/latest"><img src="https://img.shields.io/github/v/release/sslivins/hass-napoleon?display_name=tag&sort=semver" alt="GitHub release"></a>
  <a href="https://github.com/sslivins/hass-napoleon/actions/workflows/validate.yml"><img src="https://github.com/sslivins/hass-napoleon/actions/workflows/validate.yml/badge.svg" alt="HACS / Hassfest"></a>
  <a href="https://github.com/sslivins/hass-napoleon/actions/workflows/unit_tests.yml"><img src="https://github.com/sslivins/hass-napoleon/actions/workflows/unit_tests.yml/badge.svg" alt="Unit Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/sslivins/hass-napoleon" alt="License"></a>
</p>

<p align="center">
  Control your <a href="https://www.napoleon.com">Napoleon Astound</a>-series
  fireplaces from Home Assistant — power, accent lights, flame intensity,
  favourite scenes, heater + setpoint, and the auxiliary toggles.
</p>

---

## Features

- 🔌 **One-click install** via HACS (button below).
- 🔥 **`switch.<name>`** — main fireplace power.
- 💡 **`light.<name>_ember_bed`** / **`light.<name>_top_light`** — accent
  lights with brightness 0–255 (mapped to the device's 0–5 scale).
- 🎚️ **`number.<name>_flame_intensity`** — flame height 0–5.
- 🎨 **`select.<name>_favourite`** — preset scene (`partytime`,
  `campfirewarmth`, `summerday`, `glowingsunset`).
- 🌡️ **`climate.<name>`** — heater stage (off / low / high) + setpoint
  18–23 °C.
- 🪛 **`switch.<name>_eco_mode`** / **`_boost_mode`** /
  **`_ember_bed_cycling`** / **`_top_light_cycling`** — auxiliary toggles.
- ⚡ **Snappy UI** — every command is immediately followed by a re-poll
  so the entity state updates within a second.

## Quick install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sslivins&repository=hass-napoleon&category=Integration)

Click the button above on a device that has access to your Home
Assistant. It takes you straight to the **Add custom repository**
dialog in HACS with everything pre-filled.

After it installs:

1. **Restart Home Assistant.**
2. Go to **Settings → Devices & Services → Add Integration**, search
   for **Napoleon Fireplace**.
3. Sign in with the same email + password you use in the Napoleon
   mobile app.

## Requirements

- Home Assistant **2026.5** or newer
- [HACS](https://hacs.xyz) installed
- A working Napoleon mobile-app account
- At least one Astound-series fireplace already paired with the app

## Manual install (without HACS)

If you don't run HACS:

1. Copy the entire `custom_components/napoleon/` directory into your
   Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & Services**.

## How it works

The integration is a thin wrapper around
[`pynapoleon`](https://github.com/sslivins/pynapoleon)
([PyPI](https://pypi.org/project/pynapoleon/)), which talks to
Napoleon's cloud (an Ayla Networks IoT tenant) on your behalf. Each
fireplace is polled once per minute via Home Assistant's
`DataUpdateCoordinator`.

Napoleon's push channel is broken on this tenant
(`subscriptions.json` returns 403), so the integration polls instead.

## Limitations

- **No fan / blower control** — this fireplace model has no blower
  datapoint, so there is nothing to expose.
- **No ambient temperature sensor** — this model does not report a
  room temperature, so the climate entity is setpoint-only.
- **No push updates** — see above; Napoleon's push channel is broken.

## Credentials

Your Napoleon password is stored only in the Home Assistant config
entry (encrypted at rest like every other HA credential) and is never
written to logs by this integration.

## Development

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1     # Windows PowerShell
# or:  source .venv/bin/activate # macOS / Linux
pip install -e ".[tests]"

ruff check custom_components/napoleon tests
mypy custom_components/napoleon
pytest
```

> **Note:** running the full pytest suite locally on Windows fails
> because `pytest-homeassistant-custom-component` ultimately imports
> `fcntl`, which is Unix-only. Tests run cleanly on Linux CI.

## Contributing

Bug reports and PRs welcome on the
[issue tracker](https://github.com/sslivins/hass-napoleon/issues).

## License

[MIT](LICENSE) © [sslivins](https://github.com/sslivins)
