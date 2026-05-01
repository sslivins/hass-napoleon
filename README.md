# hass-napoleon

Home Assistant custom integration for **Napoleon Astound**-series fireplaces.

This integration is a thin wrapper around [`pynapoleon`](https://github.com/sslivins/pynapoleon),
which talks to Napoleon's cloud (an Ayla Networks IoT tenant) on your behalf.

> **Status: beta.** All planned platforms for this fireplace model are
> implemented: power, accent lights, flame intensity, favourite scene,
> heater + setpoint, and extra toggles (eco / boost / ember-bed cycling /
> top-light cycling). [`pynapoleon`](https://pypi.org/project/pynapoleon/)
> is published; HACS default-repo submission is pending.

## Requirements

- Home Assistant 2024.11 or newer
- A working Napoleon mobile-app account (email + password)
- A Napoleon Astound-series fireplace already paired with the app

## Installation (HACS)

This integration is not yet in the default HACS list. To install it now:

1. In HACS, choose **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/sslivins/hass-napoleon` as an **Integration**.
3. Install **Napoleon Fireplace**.
4. Restart Home Assistant.
5. **Settings → Devices & Services → Add Integration → Napoleon Fireplace**,
   sign in with your Napoleon app credentials.

## What it does

Polls each fireplace on your Napoleon account once per minute and exposes:

- **`switch.<name>`** — main fireplace power
- **`switch.<name>_eco_mode`**, **`_boost_mode`**, **`_ember_bed_cycling`**,
  **`_top_light_cycling`** — auxiliary toggles
- **`light.<name>_ember_bed`**, **`<name>_top_light`** — accent lights with
  brightness 0–255 (mapped to the device's 0–5 scale)
- **`number.<name>_flame_intensity`** — flame height 0–5
- **`select.<name>_favourite`** — preset scene
  (`partytime` / `campfirewarmth` / `summerday` / `glowingsunset`)
- **`climate.<name>`** — heater stage (off / low / high) + setpoint
  18–23 °C

After every command the integration immediately re-polls the device, so the
UI reflects the new state within a second or two.

## What it does *not* do

- **Fan / blower control.** This fireplace model has no blower datapoint;
  there is nothing to expose.
- **Ambient temperature sensor.** This model does not report a room
  temperature, so the climate entity is setpoint-only.
- **Push updates.** Napoleon's push channel is broken on this tenant
  (`subscriptions.json` returns 403), so the integration polls instead.

## Credentials

Your Napoleon password is stored only in the Home Assistant config entry
(encrypted at rest like every other HA credential). It is never written to
logs by this integration.

## Development

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1   # Windows PowerShell
pip install -e ".[tests]"
ruff check custom_components/napoleon tests
mypy custom_components/napoleon
pytest
```

## License

MIT — see [LICENSE](LICENSE).
