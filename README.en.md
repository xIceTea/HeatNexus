![HeatNexus](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/banner_small.png)

[![Validate](https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml/badge.svg)](https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml) [![Tests](https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml/badge.svg)](https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml) ![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5) ![Home Assistant 2025.6+](https://img.shields.io/badge/Home%20Assistant-2025.6%2B-03a9f4) [![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue)](LICENSE)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&repository=HeatNexus&category=integration) [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=heatnexus)

[Deutsch](README.md) · **English**

# HeatNexus

Heating systems in Home Assistant — local, complete, no cloud.

The system is read and controlled directly over its HTTP API on your network.
Boilers, heating circuits, buffer tanks, domestic hot water and circulation are
covered, including the info, operator and service levels.

**A note on language.** The integration speaks German, because the heating
systems it talks to do: entity names, help texts and the bundled dashboard use
the same wording as the InfoWIN Touch control panel, so what you read in Home
Assistant matches what you read on the boiler. This page exists so you can
decide whether the integration fits before you install it.

![Animated plant diagram: boiler starts, buffer charges, heating circuit and hot water warm up](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation.gif)

*The plant diagram is assembled from the parts that were discovered —
  two buffer tanks give you two. And it moves: pumps spin, the bands on flow and
  return show the direction, the buffer reports “charging” and “discharging”,
  tanks and radiators take the colour of their sensors. Example values.*

[![Tour of the panel: overview, fault, controls, maintenance, time programmes](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif)](docs/OBERFLAECHE.md)

*The integration's own page in the sidebar: overview, an active fault,
  controls with a hot-water charge running, maintenance, time programmes. In
  detail in [docs/OBERFLAECHE.md](docs/OBERFLAECHE.md) (German) –
  example values, recorded from the shipped interface.*

## Supported hardware

| Part | Status |
|---|---|
| PuroWIN — wood chips | verified against real hardware |
| UML / UMLZ heating circuit module | verified against real hardware |
| B-PLMi buffer charging module | verified against real hardware |
| ZSP pump and relay module | verified against real hardware |
| BioWIN, BioWIN 2 — pellets | supported, unverified |
| Heat pump, electric heater | supported, unverified |
| Gas and oil boilers | supported, unverified |
| Solar, cascade, changeover | supported, unverified |
| Infinity PLUS heating circuit and DHW | supported, unverified |

*Supported, unverified* means the function is described in the bundled device
database and is recognised with its names, units and enumerations — there simply
was no such system available to measure against. Which function type is what and
which datapoints it carries is documented in full in
[`docs/DATAPOINTS.md`](docs/DATAPOINTS.md).

Everything else is picked up by the generic discovery: whatever the controller
reports shows up in Home Assistant. Reports about hardware not listed here are
welcome — the integration's diagnostics export is all it takes.

## What it does

- **Automatic discovery** of every unlocked function. Datapoints the system does
  not have are dropped; write-protected ones are created read-only.
- **Ranges from the device**: minimum, maximum, step, unit and the permitted
  enumeration values come from the controller's own metadata.
- **A thermostat per heating circuit** with operating mode, comfort correction
  and a timed comfort setpoint.
- **Time programs** for heating, hot water and circulation, readable and
  writable — shown as a weekly grid in the panel, with an editor for weekdays
  and switch points.
- **Faults in plain text** with code, class and what to do about it.
- **Service level** available in full, disabled by default, switchable per
  entity.
- **A dedicated panel** in the sidebar: plant diagram, key values, system
  status, heating circuits, hot water, faults, history and quick controls on one
  page, plus tabs for controls, maintenance, history and time programs.
- **Plant diagram** drawn from the discovered parts, with running pumps and live
  values on top. The kind of heat generator — wood chips, pellets, logs, heat
  pump, gas/oil — is detected and can be overridden per system.
- **Dashboard and automation blueprints** ship with it and build themselves from
  whatever the system provides.
- Multiple systems in parallel.

## Installation

### Through HACS

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&repository=HeatNexus&category=integration)

The button adds the repository to HACS and opens the download page. Restart Home
Assistant afterwards.

By hand it works the same way: HACS → Integrations → ⋮ → **Custom repositories**
→ enter the repository URL, category *Integration* → install "HeatNexus" →
restart Home Assistant.

### Without HACS

Copy the folder `custom_components/heatnexus` to
`<config>/custom_components/heatnexus` and restart Home Assistant.

### Setup

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=heatnexus)

Or by hand: Settings → Devices & Services → Add integration → **HeatNexus**. You
need the IP address of the system, the account and its password.

#### Account and password

The interface is the same one the system's own web front end uses. Out of the
factory the controller knows two accounts:

| Account | Factory password | Scope |
|---|---|---|
| `USER` | `123` | info and operator level |
| `Service` | `123` | plus the OEM parameters |

You can check the credentials without Home Assistant: open `http://<IP of the
system>` in a browser. If the InfoWIN Touch web interface appears, the
combination is right.

To read or write OEM parameters, pick `Service` during setup. A different user
name can be typed into the same field.

**Changing the password** is possible in two places, both writing the same
parameter: on the InfoWIN Touch itself, or in its web interface under
*Passwort*. A password set there applies to the API immediately — after that it
has to be updated in Home Assistant via *Reconfigure*.

**Password unknown or suddenly wrong?** If the system is registered with
Windhager Connect, the current web server password can be read there. Sign in,
select the system — the address then ends in `/management`. Replace that word
with `settings`:

```text
https://connect.windhager.com/systems/<system id>/management
https://connect.windhager.com/systems/<system id>/settings
```

The settings page shows the password in clear text and lets you change it.

> **Windhager app:** if the system is connected to myComfort / myConnect,
> Windhager assigns its own password and the factory values above no longer
> apply. This is not a permanent lockout — the password can be read or reset as
> described above, after which both the app and HeatNexus work again.

> **HTTP only:** the controller answers on port 80 without encryption; there is
> no local HTTPS (verified on a PuroWIN with InfoWIN Touch). Thanks to digest
> authentication the password itself does not travel in clear text, but the
> readings do. HeatNexus belongs on your own network, not on the internet.

The second step selects the **scope**:

| Level | Contents | Default |
|---|---|---|
| Info | readings and states | always on |
| Operator | operating mode, setpoints, programs, hot water | always on |
| Service | heating curve, limits, screed program | created, disabled |
| OEM | combustion control, ignition, drives | not created |

Plus two switches:

- **Enable service/OEM level immediately** — without it the entities are created
  but stay disabled and cause no polling.
- **Make service/OEM level writable** — without it these parameters are display
  only. Only with it can they be written.

Both can be changed at any time under *Configure* on the integration, as can the
polling interval. After a change the integration re-reads the system.

The same place holds the **heat generator** per system. It only affects the
drawing in the plant diagram and changes neither entities nor values. Out of the
box it is set to *detect automatically*: HeatNexus takes the fuel the system
reports, otherwise the function type, otherwise the name of the function. If the
result does not fit, it can be pinned here.

#### The first minute

After setup the integration is there immediately, but not yet **complete**:
first the core set of entities appears, then HeatNexus reads the whole system in
the background. Depending on the system this takes 30 to 120 seconds, and during
that time more entities keep arriving — a handful becomes several hundred,
depending on the scope.

A notification accompanies the process and reports the final count. So there is
no reason to worry if only a few values are visible right after setup.

The result is stored and survives restarts; on the next start everything is
there at once. A fresh read happens only after a change of scope, after a new
version, or through the `heatnexus.rediscover` service.

## Services

| Service | Effect |
|---|---|
| `heatnexus.set_time_program` | set a time program (`switch_points` with `weekdays`, or `blocks` for separate weekly plans) |
| `heatnexus.set_vorgabe` | timed room temperature override for a heating circuit ("Eco / Comfort") |
| `heatnexus.set_current_temp_compensation` | comfort correction of a heating circuit |
| `heatnexus.rediscover` | re-read the system, e.g. after modifications |

```yaml
service: heatnexus.set_time_program
target:
  entity_id: sensor.heizkreis_programm_1
data:
  weekdays: ["Mo", "Di", "Mi", "Do", "Fr"]
  switch_points:
    - {time: "06:00", value: 21}
    - {time: "22:00", value: 18}
```

## The panel

Besides the dashboard, HeatNexus adds its own page to the sidebar. It shows the
system as a whole instead of as a pile of tiles:

- **Plant diagram** with flow and return, live values, and pumps that spin while
  they run.
- **Key values** per part — one leading value per function, like the control
  panel of the system itself.
- **System status**: operating state, outside temperature, boiler output, fuel,
  hopper, remaining runtimes.
- **Heating circuits and hot water** with operating mode and setpoint, operable
  directly.
- **Faults in plain text**, **history** and **quick controls** for the frequent
  interventions, each with a confirmation where a wrong tap causes work.
- **Time programs** as a weekly grid: seven rows per program, switch points as
  bars. Editing works in blocks — tick weekdays, set switch points — and saving
  writes the whole program at once, the way the system stores it.

A "?" next to cards and controls explains what a value means and what an action
does. Both the panel and the explanations can be switched off under *Configure →
General*.

The layout is computed in Home Assistant, not in the browser: what the system
delivers appears, what is missing is left out.

## Dashboard

A dashboard named **Heizung** appears in the sidebar on its own after setup. It
is built from the devices actually found — no entity IDs to type, no YAML to
copy:

- **Overview** — the most important values per part, in a sensible order (boiler,
  buffer, heating circuit, hot water, circulation), plus the fault messages. With
  several systems the system name is in the heading, so two identically named
  parts stay distinguishable.
- **Plant** — one diagram per system: boiler, buffer, heating circuits, hot water
  and circulation, connected by flow and return, with the live values on top.
  What was found is drawn — two buffer tanks give you two.
- **Maintenance** — remaining runtimes until ash removal, main cleaning and
  service as gauges, plus fuel, hopper and meter readings.
- **Analysis** — meter increase *today* and *this month* (burner starts,
  operating hours) and temperature histories of the last 48 hours per part.
- **One view per part**, split into controls, readings, settings and diagnostics.

If a part is missing, its block is left out. If the scope is changed later, the
dashboard adapts the next time it is opened. It can be switched off under
*Configure → General*.

If you would rather build your own: templates for an overview, control cards and
a plant diagram are in [`dashboards/`](dashboards/).

## Automation blueprints

Six blueprints ship with the integration and are ready under *Settings →
Automations & Scenes → Blueprints* after setup — no import from the internet:

| Blueprint | Purpose |
|---|---|
| Report fault | notify on a fault, remind at a fixed interval, notify on recovery |
| Maintenance warning with reminder | advance warning, warning and reminder for a remaining runtime (ash, cleaning, service) |
| Fuel supply low | notify when the hopper reports empty, with reminder |
| Record running time | measure how long a part runs uninterrupted |
| Lower heating circuit while away | lower on absence, restore on return |
| Emulate legionella protection | raises the cylinder on a fixed schedule via the one-off charge — for controllers without a built-in legionella function |

What happens on an event is up to the individual automation — notification,
announcement, phone call, any action. The fault blueprint evaluates the
`stoerung_aktiv` attribute, not the displayed text, so it does not depend on any
particular wording.

## Documentation

| File | Contents |
|---|---|
| [`docs/API.md`](docs/API.md) | device API and OID structure |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | how the integration is built |
| [`docs/DATAPOINTS.md`](docs/DATAPOINTS.md) | every datapoint per function type, with its level |
| [`docs/ENUMS.md`](docs/ENUMS.md) | every enumeration value and its meaning |
| [`CHANGELOG.md`](CHANGELOG.md) | version history |

`DATAPOINTS.md` and `ENUMS.md` are generated from the bundled device database
(`python tools/build_datenpunkte_doku.py`) and checked against it by a test — so
they cannot go stale.

## Development

```bash
pip install -r requirements_test.txt
pytest
ruff check custom_components tests tools
```

Read out a system — on Windows a double click on `tools/probe.cmd` is enough,
otherwise:

```bash
python tools/heatnexus_probe.py                       # guided mode
python tools/heatnexus_probe.py all 192.0.2.10 192.0.2.11
```

Details in [`tools/README.md`](tools/README.md).

## Disclaimer

This integration writes to a heating system. Controllable operator-level
datapoints are verified; service parameters are deliberately disabled. Use at
your own risk.

## Support

HeatNexus is built in my spare time against a real heating system. If you would
like to support the work:

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="48">](https://buymeacoffee.com/xicetea)

Just as helpful and free: a bug report with the diagnostics export, especially
from hardware listed here as *supported, unverified*.

## License

HeatNexus is licensed under the [GNU General Public License v3.0](LICENSE).
If you modify and distribute it, you distribute it under the same licence —
with source. Name and logo are excluded, see [`NOTICE`](NOTICE).

Up to and including 1.5.0 the project was licensed under Apache License 2.0;
earlier releases remain under the terms they were published with.
