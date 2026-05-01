# hass-napoleon

Home Assistant custom integration for **Napoleon Astound**-series fireplaces.

This integration is a thin wrapper around [`pynapoleon`](https://github.com/sslivins/pynapoleon),
which talks to Napoleon's cloud (an Ayla Networks IoT tenant) on your behalf.

> **Status: alpha.** Bootstrap release exposes the main fireplace power switch
> only. Light, fan, flame intensity, setpoint, current temperature, and
> favourite-scene entities will land in subsequent PRs.

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

- Polls each fireplace on your Napoleon account once per minute.
- Provides one `switch.<fireplace_name>` per fireplace (main power).

## What it does *not* do (yet)

- Light / RGB control (planned)
- Fan / blower control (planned)
- Flame intensity number entities (planned)
- Setpoint / current temperature (planned)
- Heater / climate control (planned, requires more verification)
- Favourite scenes (planned)

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
