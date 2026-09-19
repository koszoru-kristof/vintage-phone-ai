# Rotary Dial → Home Assistant Bridge

**Date:** 2026-09-19
**Status:** Design approved, not yet implemented
**Scope:** Input only. The phone becomes a dial-and-hook input device for Home Assistant. Audio, voice assistant, and telephony are explicitly out of scope.

## Goal

Dialling a digit on a 1970s LM Ericsson rotary telephone triggers an action in a
local Home Assistant instance. Dialling `5` turns on a lighting scene.

The hook switch is not required to trigger a digit, but every hook transition is
reported to Home Assistant and recorded, so that hook-based automations can be
built later without reopening the phone.

## Target hardware

**Phone:** LM Ericsson H15662, DLG/DLN 012 024. Finnish market, 1970s–80s.

Relevant original parts:

| Part | Role | Fate in this project |
|---|---|---|
| Dial mechanism S2 | Shunt springs + impulse springs | **Kept** — the primary input |
| Hook switch S1 | Multi-pole, cradle-operated | **Kept** — one pole used |
| Bell + coil | 1.8 kΩ, driven at 20–25 Hz / 48–125 V AC | Kept in place, unused (weight and character) |
| Transformer T1 | Anti-sidetone / impedance match | Removed |
| Varistors V1–V3, C1, C2, R1–R5 | Line protection and audio network | Removed |
| Original PCB `TVA 30130-A` | Carries the screw terminals | Gutted, terminals reused as a wiring block |
| Line cord and plug | PSTN connection | **Removed and discarded** |
| Handset (mic + earpiece) | Audio | Left in place, unwired |

The phone is modified freely — originality is not a constraint — but no custom PCB
is designed and no circuit is built beyond six passive components.

### Safety

The line cord is removed and discarded. The bell circuit is designed to sit across
48–125 V AC ringing voltage. There is no configuration in which the phone is
connected to both a live telephone line and the ESP32.

## Controller

**Board:** Seeed XIAO ESP32C3.

Chosen for three reasons specific to this build:

1. **u.FL external antenna connector.** The phone is built on a rigid stamped steel
   base plate. A PCB trace antenna lying on that sits on a ground plane and will be
   detuned and attenuated. The external antenna can be mounted up in the plastic
   cover, away from the steel.
2. **BAT+/BAT− pads with onboard charging.** Battery operation is out of scope now,
   but this keeps the option open without a board change.
3. USB-C, 21×17 mm, ESPHome-supported.

**Power:** 5 V USB-C from any phone charger into the board's own USB port; the
onboard regulator supplies 3.3 V. Peak draw on WiFi is roughly 100 mA. The USB
cable exits through the hole the original line cord used.

Physical size is not a constraint — the base cavity is large once the transformer
and line components are removed.

## Architecture

Three units with distinct responsibilities:

```
┌─ CONTACT LAYER (hardware) ───────────────────────────────┐
│  dial shunt   ──┐                                        │
│  dial impulse ──┼─ 10k pullup + 100nF ─→ GPIO 4 / 3 / 5  │
│  hook switch  ──┘         (common → GND)                 │
└──────────────────────────────────────────────────────────┘
                              ↓  debounced edges
┌─ DECODE UNIT (firmware) ─────────────────────────────────┐
│  edges in  →  state machine  →  (raw_pulses, digit) out  │
│  knows nothing about WiFi, HA, or what a scene is        │
└──────────────────────────────────────────────────────────┘
                              ↓  digit event
┌─ TRANSPORT (ESPHome native API) ─────────────────────────┐
│  fires HA event  ·  publishes debug sensors              │
│  knows nothing about how a digit was derived             │
└──────────────────────────────────────────────────────────┘
```

The decode unit is the only place that knows about pulse timing and the only place
the pulses-per-digit offset lives. If that constant is wrong, exactly one line
changes and nothing downstream is affected.

### Firmware platform: ESPHome (YAML)

ESPHome provides WiFi management and reconnection, the native API (no MQTT broker
required, device auto-discovers in HA), OTA reflashing once the phone is closed up,
declarative debounce filters, and a built-in device-local web debug page.

**Known limitation:** decode logic embedded in a YAML lambda cannot be unit-tested
on the host. See *Testing* below for the mitigation and the escape hatch.

## Wiring

| Signal | XIAO pin | GPIO | Contact type | Expected idle |
|---|---|---|---|---|
| Dial impulse | D1 | 3 | N.C. — breaks once per pulse | closed (LOW) |
| Dial shunt | D2 | 4 | N.O. — closed while dial off rest | open (HIGH) |
| Hook switch | D3 | 5 | one pole of S1 | determined in Phase 3 |

Each contact: common side to a shared GND rail, other side to its GPIO.

Per input: 10 kΩ pullup to 3.3 V and 100 nF to GND. The ESP32 internal pullup is a
weak ~45 kΩ and is not trusted for wiring runs inside a steel enclosure. The RC
gives roughly 1 ms of hardware debounce; ESPHome `delayed_on` / `delayed_off`
filters handle the rest.

Six passives total, soldered to the board's pins or a scrap of perfboard.

**GPIO 2, 8 and 9 are ESP32-C3 strapping pins and must not be used** — driving them
at boot causes failures that present as random bricking. GPIO 3/4/5 are clean.

The idle states above are *expected*, not established. Actual wire colours and
contact senses are determined by measurement in Phase 1, which supersedes this table.

## Decode state machine

```
        ┌──────┐
        │ IDLE │◀───────────────────────────────┐
        └───┬──┘                                │
            │ shunt CLOSES (dial leaves rest)   │
            │ → pulses = 0, start 3s guard      │
            ▼                                   │
      ┌──────────┐                              │
      │ COUNTING │──── impulse RELEASES ──┐     │
      └───┬──┬───┘      → pulses++        │     │
          │  ▲────────────────────────────┘     │
          │                                     │
          │ shunt OPENS (dial back at rest)     │
          ▼                                     │
      ┌────────┐  150ms quiet                   │
      │ SETTLE │───────────────→ EMIT ──────────┤
      └────────┘                                │
                                                │
      3s guard expires ──→ DISCARD ─────────────┤
      pulses out of range ──→ DISCARD ──────────┘
```

### Design decisions

**The shunt contact defines digit boundaries.** It is a hardware statement that a
digit is in progress, so boundaries are never inferred from timing. This is the main
structural difference from rotary projects that watch only the impulse line and
guess at inter-digit gaps.

**Emit on shunt-open, not on a timeout.** The dial mechanically reports that it has
returned home. The 150 ms settle exists only to let the springs stop ringing.

**Both `raw_pulses` and `digit` are always published.** This replaces a separate
calibration mode. Dial a known digit, read `raw_pulses`, and the offset is
immediately visible — there is no mode to enter or forget to leave, and mechanical
drift as the dial ages remains observable.

```
n = raw_pulses - PULSE_OFFSET
digit = (n == 10) ? 0 : n
```

`PULSE_OFFSET` is determined empirically in Phase 2. Nordic dials send N+1 pulses
per digit; most other markets send N. This phone is Finnish-market, so `1` is
expected but not assumed.

Worked example, assuming `PULSE_OFFSET = 1`: dialling `1` produces 2 raw pulses
→ `n = 1` → digit `1`. Dialling `0` produces 11 raw pulses → `n = 10` → digit `0`.
With `PULSE_OFFSET = 0` the same mapping holds for a non-Nordic dial: `0` produces
10 raw pulses → `n = 10` → digit `0`.

**Guard rails discard rather than guess.** Pulse counts outside the plausible range,
and dials that fail to return home within 3 s, produce no output at all. For a
device that switches lights, a missed trigger is cheaper than a wrong one.

Debounce values and the plausible-count range are set from measurements in Phase 2.

## Home Assistant interface

### The digit is an event, not a state

Modelling the last-dialled digit as a sensor would break on repeats: dialling `5`
twice in a row does not change the sensor's state, so a state-based automation
fires only once. The digit is a momentary occurrence and is modelled as one.

Device side:

```yaml
- homeassistant.event:
    event: esphome.rotary_dial
    data:
      digit: !lambda 'return to_string(digit);'
      raw_pulses: !lambda 'return to_string(pulses);'
```

Home Assistant side, one automation per digit:

```yaml
trigger:
  - platform: event
    event_type: esphome.rotary_dial
    event_data:
      digit: "5"
action:
  - service: scene.turn_on
    target: { entity_id: scene.movie_night }
```

The digit-to-action mapping lives entirely in Home Assistant. The phone has no
knowledge of scenes, and re-mapping requires no reflash.

### Entities (instrumentation, not control surface)

| Entity | Type | Purpose |
|---|---|---|
| Handset lifted | `binary_sensor` | Hook state, both edges |
| Dial in progress | `binary_sensor` | Shunt contact, live — debug |
| Last digit | `sensor` | Eyeball confirmation |
| Raw pulses | `sensor` | Calibration readout |
| WiFi signal | `sensor` (RSSI) | Quantifies the steel-plate antenna risk |

The hook `binary_sensor` satisfies the requirement to record hook activity for
future automations: Home Assistant's recorder logs every transition to history and
logbook with no additional work, accumulating real data before any hook automation
is written.

`web_server:` is enabled for a device-local debug page showing live contact states
without Home Assistant in the loop — needed to distinguish phone faults from
network faults.

### Home Assistant prerequisites

**None.** The ESPHome *integration* in Home Assistant is built-in core and
auto-discovers the device over the native API; it does not need installing. The
ESPHome *add-on* is only a compiler and web dashboard, and is not required —
firmware is compiled with the `esphome` CLI so that the device configuration lives
in this repository under version control rather than inside add-on storage.

No MQTT broker is needed.

## Failure modes

**Digits dialled while WiFi or the API is down are dropped, by design.** ESPHome
reconnects automatically, but replaying a queued digit tens of seconds later would
change the lights unexpectedly. Silence is preferred to a late surprise.

**`api: reboot_timeout` must be set long or disabled.** The ESPHome default reboots
the device after 15 minutes without a Home Assistant connection, which turns any HA
maintenance window into a reboot loop inside a sealed phone.

**Implausible input produces no output.** Out-of-range counts and non-returning
dials are discarded silently rather than clamped to a best guess.

## Bring-up plan

Each phase resolves one unknown and has a concrete deliverable.

**Phase 0 — Bench, no phone.** Flash the XIAO over USB-C with minimal ESPHome YAML;
confirm it appears in Home Assistant.
*Deliverable:* working toolchain, before any 50-year-old hardware is involved.

**Phase 1 — Ring out the dial.** Multimeter continuity across the three dial wires,
at rest and mid-rotation.
*Deliverable:* a measured common/shunt/impulse table with actual wire colours,
superseding the table in *Wiring*.

**Phase 2 — Calibrate the decode.** Dial mechanism on the bench, out of the phone,
wired to the board. Dial each of 0–9 ten times; observe `raw_pulses`.
*Deliverable:* `PULSE_OFFSET`, measured pulse widths, debounce values, and the
plausible-count range.

**Phase 3 — Hook switch.** Identify a pole of S1 that switches cleanly with the
cradle; wire and verify.
*Deliverable:* working `binary_sensor`, and the hook's idle sense.

**Phase 4 — Integrate.** Remove the transformer, varistors, caps and cord; gut the
original PCB retaining its screw terminals as the wiring block; mount the board;
place the u.FL antenna in the plastic cover. Measure RSSI with the cover off and on.
*Deliverable:* an assembled phone and an RSSI figure. **Pass criterion: better than
−70 dBm with the cover on.** Below that, reposition the antenna before closing up.

**Phase 5 — Automations.** Ten Home Assistant automations, one per digit.
*Deliverable:* dialling `5` activates a lighting scene.

## Testing

**Decode correctness** is verified by the Phase 2 protocol: dial each digit ten
times, require a consistent `raw_pulses` value per digit across all repetitions.
This is a manual but repeatable test with a clear pass criterion, and it is the
honest substitute for host-side unit tests given the YAML-lambda limitation.

**Automations** are tested independently of the hardware by firing
`esphome.rotary_dial` by hand from Developer Tools → Events, which decouples
automation debugging from the phone entirely.

**Device state** is observed through ESPHome logs and the device-local `web_server:`
page.

## Escape hatch

If the decode proves fussier than the Phase 2 measurements suggest, promote the
decode unit from a YAML lambda to an ESPHome `external_component` — a C++ component
compiled in, with host-testable logic. All ESPHome infrastructure (WiFi, API, OTA,
web server) is retained; only the middle unit changes, and the Phase 2 protocol
becomes its test fixture.

This is a named fallback, not part of the plan. Starting there would be speculative
complexity for roughly twenty lines of counting logic.

## Rejected alternatives

**Bare PlatformIO firmware with MQTT.** Maximum timing control and fully testable,
but requires hand-rolling WiFi management, MQTT discovery, OTA and a debug
interface — all provided free by ESPHome — to arrive at the same three GPIO reads.

**VoIP ATA (e.g. Grandstream HT801), as used by the `rotary-gpt` project.** Requires
implementing SIP and pulse-to-DTMF conversion to obtain a digit that is directly
readable from two wires. Appropriate when real telephony is wanted; unnecessary
overhead for an input-only device.

**Single digit with hook gating.** Requiring the handset to be lifted before dialling
would prevent accidental triggering, but adds a gesture the user does not want for
light control. Rejected in favour of hook-independent dialling, with hook state
still reported.

**Multi-digit codes.** More available triggers, but requires inter-digit timeout
tuning and introduces partial-code ambiguity. Ten triggers are sufficient. The
decode state machine emits per-digit, so multi-digit sequences could be composed in
Home Assistant later if wanted.

## Out of scope

- Audio, microphone, earpiece, voice assistant (the existing Python work in this
  repo is unrelated and untouched)
- Ringing the bell — no output path is built
- Battery operation — deferred, but the board choice keeps it viable
- Any PSTN or VoIP connection
