# Rotary Dial → Home Assistant Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dialling a digit on a 1970s LM Ericsson H15662 rotary telephone fires a Home Assistant event, so that dialling `5` activates a lighting scene.

**Architecture:** Three dry contacts (dial impulse, dial shunt, hook switch) are read as GPIO inputs by a Seeed XIAO ESP32C3 running ESPHome. A state machine gated by the shunt contact counts impulse breaks into a digit, which is published as a Home Assistant event. The digit-to-action mapping lives entirely in Home Assistant.

**Tech Stack:** ESPHome (YAML + lambdas, ESP-IDF framework), `esphome` CLI, Home Assistant native API, Seeed XIAO ESP32C3.

**Spec:** `docs/superpowers/specs/2026-09-19-rotary-dial-ha-bridge-design.md`

## Global Constraints

- **Input only.** No audio, no microphone, no earpiece, no bell output, no PSTN or VoIP. The existing Python voice-assistant work in this repo is unrelated and must not be modified.
- **The line cord is removed and discarded before any electronics are connected.** The bell circuit is designed for 48–125 V AC. The phone must never be connected to both a live telephone line and the ESP32.
- **GPIO 2, 8 and 9 are ESP32-C3 strapping pins and must not be used.** Only GPIO 3, 4, 5 are used for inputs.
- **No custom PCB.** Six passive components only: 3× 10 kΩ pullup to 3.3 V, 3× 100 nF to GND.
- **No MQTT broker and no ESPHome add-on.** Firmware compiles with the `esphome` CLI; Home Assistant's built-in ESPHome integration discovers the device.
- **`api: reboot_timeout: 0s`** — the device must never reboot because Home Assistant is unreachable.
- **Calibration constants live only in `substitutions:`** in `esphome/rotary-phone.yaml`. No magic numbers in lambdas.
- Device name: `rotary-phone`. HA event name: `esphome.rotary_dial`.

---

## A note on testing this plan

This is firmware plus 50-year-old electromechanical hardware. There is no host test
runner, and pretending otherwise would produce a plan that cannot be followed.

Instead, **every task ends with a verification step that has an explicit pass
criterion** — a reading on a multimeter, a value in a log line, an entity state in
Home Assistant. Treat a failed pass criterion exactly as you would a red test: stop,
do not proceed to the next task.

Tasks 2, 4 and 6 are **bench protocols performed by a human with a multimeter and
the phone open**. Their deliverable is a committed measurement record. An agentic
worker cannot complete these alone and must hand them to the operator.

---

## File Structure

| File | Responsibility |
|---|---|
| `esphome/rotary-phone.yaml` | Device identity, WiFi, API, OTA, web server, calibration substitutions, package includes |
| `esphome/packages/dial_decode.yaml` | Contact inputs and the decode state machine. The only file that knows about pulse timing. |
| `esphome/packages/diagnostics.yaml` | RSSI, uptime, IP address. Instrumentation only. |
| `esphome/secrets.yaml.example` | Template for credentials |
| `esphome/secrets.yaml` | Real credentials — **gitignored** |
| `docs/bench/phase1-dial-contacts.md` | Measured dial contact identification |
| `docs/bench/phase2-pulse-calibration.md` | Measured pulses-per-digit and timing |
| `docs/bench/phase3-hook-switch.md` | Measured hook switch pole and sense |
| `docs/bench/phase4-rf-check.md` | RSSI with cover off vs on |
| `ha/automations/rotary_dial.yaml` | The ten Home Assistant automations |

---

### Task 1: Scaffolding and a board that talks to Home Assistant

No phone involved. Proves the toolchain before any vintage hardware is at risk.

**Files:**
- Create: `esphome/rotary-phone.yaml`
- Create: `esphome/packages/diagnostics.yaml`
- Create: `esphome/secrets.yaml.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: a device named `rotary-phone` reachable over the ESPHome native API and at `http://rotary-phone.local/`. Substitution names `pulse_offset`, `pulse_min`, `pulse_max` that Task 5 reads.

- [ ] **Step 1: Install the ESPHome CLI**

```bash
pip install esphome
```

Verify:

```bash
esphome version
```

Expected: `Version: 2025.x.x` or later. Anything older than 2024.6 will reject the `ota:` list syntax used below.

- [ ] **Step 2: Add ESPHome build artefacts and secrets to .gitignore**

Append to `.gitignore`:

```
# ESPHome
esphome/secrets.yaml
esphome/.esphome/
esphome/build/
```

- [ ] **Step 3: Create the secrets template**

Create `esphome/secrets.yaml.example`:

```yaml
wifi_ssid: "your-ssid"
wifi_password: "your-wifi-password"
fallback_password: "rotaryfallback"
api_encryption_key: "generate with: openssl rand -base64 32"
ota_password: "any-passphrase"
```

- [ ] **Step 4: Create your real secrets file (not committed)**

```bash
cp esphome/secrets.yaml.example esphome/secrets.yaml
openssl rand -base64 32
```

Edit `esphome/secrets.yaml`: put the generated string in `api_encryption_key`, and fill in your real WiFi SSID and password.

- [ ] **Step 5: Create the diagnostics package**

Create `esphome/packages/diagnostics.yaml`:

```yaml
sensor:
  - platform: wifi_signal
    name: "WiFi Signal"
    id: wifi_signal_db
    update_interval: 30s
    entity_category: diagnostic

  - platform: uptime
    name: "Uptime"
    update_interval: 60s
    entity_category: diagnostic

text_sensor:
  - platform: wifi_info
    ip_address:
      name: "IP Address"
      entity_category: diagnostic
```

- [ ] **Step 6: Create the main device config**

Create `esphome/rotary-phone.yaml`:

```yaml
substitutions:
  # Calibration constants. Defaults assume a Nordic dial (N+1 pulses per digit).
  # Task 4 confirms or corrects these by measurement.
  pulse_offset: "1"
  pulse_min: "2"
  pulse_max: "11"

esphome:
  name: rotary-phone
  friendly_name: Rotary Phone

esp32:
  board: seeed_xiao_esp32c3
  framework:
    type: esp-idf

logger:
  level: DEBUG

api:
  encryption:
    key: !secret api_encryption_key
  # Never reboot because Home Assistant is unreachable — this device is
  # sealed inside a telephone.
  reboot_timeout: 0s

ota:
  - platform: esphome
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: "Rotary Phone Fallback"
    password: !secret fallback_password

captive_portal:

web_server:
  port: 80
  version: 3

packages:
  diagnostics: !include packages/diagnostics.yaml
```

- [ ] **Step 7: Compile**

```bash
cd esphome && esphome compile rotary-phone.yaml
```

Expected: `INFO Successfully compiled program.`
If it fails on `board: seeed_xiao_esp32c3`, your ESPHome is too old — upgrade it.

- [ ] **Step 8: Flash over USB-C**

Connect the XIAO by USB-C, then:

```bash
cd esphome && esphome run rotary-phone.yaml
```

Choose the serial port when prompted. If the board is not detected, hold **BOOT**, tap **RESET**, release **BOOT**, and retry.

Expected: upload completes, then logs stream showing `WiFi Connected`.

- [ ] **Step 9: Verify — pass criterion**

Three checks, all must pass:

1. `ping rotary-phone.local` responds.
2. `http://rotary-phone.local/` loads and shows WiFi Signal, Uptime and IP Address.
3. In Home Assistant, **Settings → Devices & Services** shows a discovered ESPHome device `rotary-phone`. Accept it and paste the `api_encryption_key` when asked.

If HA does not discover it, confirm the board and HA are on the same subnet before debugging anything else.

- [ ] **Step 10: Commit**

```bash
git add .gitignore esphome/rotary-phone.yaml esphome/packages/diagnostics.yaml esphome/secrets.yaml.example
git commit -m "feat(esphome): add XIAO ESP32C3 base config with diagnostics

Device reaches Home Assistant over the native API and serves a local
debug page. No phone hardware connected yet."
```

---

### Task 2: Bench protocol — identify the dial contacts

**HUMAN TASK.** Multimeter required. Phone open, line cord already removed.

**Files:**
- Create: `docs/bench/phase1-dial-contacts.md`

**Interfaces:**
- Consumes: nothing
- Produces: the measured mapping of dial wire colour → `COMMON` / `SHUNT` / `IMPULSE`, and each contact's resting sense (`NO` or `NC`). Task 3 wires GPIO according to this.

- [ ] **Step 1: Confirm the phone is isolated**

The line cord and wall plug must be physically removed and set aside. Do not
proceed while the phone can reach a telephone socket.

- [ ] **Step 2: Identify the three dial wires**

The dial mechanism has a 3-wire tail. The blog reference for this model reports
white / red / blue on screw terminals 10 / 15 / 14, but **do not trust this** —
verify by measurement.

- [ ] **Step 3: Find the common wire**

Multimeter in continuity mode. With the dial **at rest**, probe all three wire
pairs and record continuity:

| Pair | Continuity at rest? |
|---|---|
| A–B | |
| A–C | |
| B–C | |

The impulse contact is normally **closed** and the shunt contact is normally
**open**. So exactly one pair should show continuity at rest. The wire common to
both contacts is the one appearing in that closed pair *and* shared with the third
wire when the shunt closes — confirm in Step 4.

- [ ] **Step 4: Confirm by rotating the dial**

Rotate the dial to `0` and **hold it at the finger stop** (do not release). In this
held position the shunt is closed and the impulse contact is not yet pulsing.

Re-probe all three pairs and record:

| Pair | Continuity, dial held at stop |
|---|---|
| A–B | |
| A–C | |
| B–C | |

The pair that changed from open to closed is COMMON–SHUNT. The pair closed in both
tests is COMMON–IMPULSE. The wire in both pairs is COMMON.

- [ ] **Step 5: Observe the impulse pulses**

Probe COMMON–IMPULSE. Rotate to `0` and release. The meter should chatter as the
contact breaks repeatedly. This confirms you have the impulse contact and not the
shunt.

- [ ] **Step 6: Record the result**

Create `docs/bench/phase1-dial-contacts.md`:

```markdown
# Phase 1 — Dial contact identification

**Date measured:**
**Phone:** LM Ericsson H15662 DLG/DLN 012 024

## Measured mapping

| Function | Wire colour | Screw terminal | Sense at rest |
|---|---|---|---|
| COMMON  | | | n/a |
| SHUNT   | | | open (N.O.) |
| IMPULSE | | | closed (N.C.) |

## Continuity readings

At rest:

| Pair | Continuity |
|---|---|
| A–B | |
| A–C | |
| B–C | |

Dial held at finger stop:

| Pair | Continuity |
|---|---|
| A–B | |
| A–C | |
| B–C | |

## Deviations from the reference

Record here if the wire colours or senses differ from the blog reference
(white/red/blue on terminals 10/15/14). If they match, say so explicitly.
```

Fill in every blank from your actual measurements.

- [ ] **Step 7: Verify — pass criterion**

You can state, without guessing, which physical wire is COMMON, which is SHUNT, and
which is IMPULSE. The impulse wire chatters on dial release; the shunt wire does not.

- [ ] **Step 8: Commit**

```bash
git add docs/bench/phase1-dial-contacts.md
git commit -m "docs(bench): record measured dial contact identification

Phase 1 of bring-up. Supersedes the wiring table in the design spec."
```

---

### Task 3: Wire the dial contacts and see them in Home Assistant

Raw contact visibility only — no counting, no decode. This isolates "is the wiring
right" from "is the logic right".

**Files:**
- Create: `esphome/packages/dial_decode.yaml`
- Modify: `esphome/rotary-phone.yaml` (add the package include)

**Interfaces:**
- Consumes: the contact mapping from `docs/bench/phase1-dial-contacts.md`
- Produces: `binary_sensor` ids `dial_impulse` and `dial_shunt`, both `true` when their contact is **closed**. Task 4 attaches counting to these.

- [ ] **Step 1: Wire the contacts**

For each of the two dial contacts, on a scrap of perfboard or directly on the board's pins:

```
3.3V ──[ 10kΩ ]──┬────────────── GPIO n
                 │
                ═╪═ 100nF
                 │
   contact ──────┴───── GND     (COMMON wire of the dial → GND rail)
```

- IMPULSE wire → GPIO3 (pin D1)
- SHUNT wire → GPIO4 (pin D2)
- COMMON wire → GND

Do not use GPIO 2, 8 or 9.

- [ ] **Step 2: Create the decode package with raw sensors only**

Create `esphome/packages/dial_decode.yaml`:

```yaml
binary_sensor:
  # Normally CLOSED. Breaks once per dial pulse.
  # pullup + inverted => reported true when the contact is CLOSED.
  - platform: gpio
    id: dial_impulse
    name: "Dial Impulse"
    pin:
      number: GPIO3
      mode:
        input: true
        pullup: true
      inverted: true
    filters:
      - delayed_on: 4ms
      - delayed_off: 4ms

  # Normally OPEN. Closed while the dial is away from its rest position.
  - platform: gpio
    id: dial_shunt
    name: "Dial In Progress"
    pin:
      number: GPIO4
      mode:
        input: true
        pullup: true
      inverted: true
    filters:
      - delayed_on: 10ms
      - delayed_off: 10ms
```

If Phase 1 found the senses reversed from the spec's expectation, flip the
`inverted:` value on that sensor and note it in a comment.

- [ ] **Step 3: Include the package**

In `esphome/rotary-phone.yaml`, change the `packages:` block to:

```yaml
packages:
  dial: !include packages/dial_decode.yaml
  diagnostics: !include packages/diagnostics.yaml
```

- [ ] **Step 4: Flash over the air**

```bash
cd esphome && esphome run rotary-phone.yaml
```

Choose the OTA/network target rather than serial.

- [ ] **Step 5: Verify — pass criterion**

Open `http://rotary-phone.local/` and watch the two binary sensors while operating the dial:

| Action | `Dial Impulse` | `Dial In Progress` |
|---|---|---|
| Dial at rest, untouched | ON (closed) | OFF |
| Dial held at finger stop | ON | **ON** |
| Dial released, returning | flickers OFF/ON | ON, then OFF at rest |

All three rows must match. If `Dial Impulse` reads OFF at rest, your `inverted:` is
wrong or the wire is on the shunt contact — go back to Task 2.

- [ ] **Step 6: Commit**

```bash
git add esphome/packages/dial_decode.yaml esphome/rotary-phone.yaml
git commit -m "feat(esphome): add raw dial contact binary sensors

Impulse and shunt contacts visible in HA and on the device debug page.
No decode logic yet."
```

---

### Task 4: Bench protocol — calibrate pulses per digit

**HUMAN TASK.** Requires Task 3 flashed and working.

This resolves `PULSE_OFFSET`, the one constant that makes every trigger off-by-one
if it is wrong.

**Files:**
- Create: `docs/bench/phase2-pulse-calibration.md`
- Modify: `esphome/packages/dial_decode.yaml` (temporary raw counter)
- Modify: `esphome/rotary-phone.yaml` (final calibration substitutions)

**Interfaces:**
- Consumes: `dial_impulse`, `dial_shunt` from Task 3
- Produces: confirmed values for substitutions `pulse_offset`, `pulse_min`, `pulse_max`; a template sensor id `raw_pulses_sensor` and globals `pulse_count`, `dialing` that Task 5 extends.

- [ ] **Step 1: Add a raw pulse counter**

Add to the top of `esphome/packages/dial_decode.yaml`:

```yaml
globals:
  - id: pulse_count
    type: int
    restore_value: no
    initial_value: '0'
  - id: dialing
    type: bool
    restore_value: no
    initial_value: 'false'

sensor:
  - platform: template
    id: raw_pulses_sensor
    name: "Raw Pulses"
    accuracy_decimals: 0
    update_interval: never
```

Then add automations to the two existing binary sensors. Under `dial_impulse`, add:

```yaml
    on_release:
      - lambda: |-
          if (id(dialing)) {
            id(pulse_count) += 1;
          }
```

Under `dial_shunt`, add:

```yaml
    on_press:
      - lambda: |-
          id(pulse_count) = 0;
          id(dialing) = true;
    on_release:
      - delay: 150ms
      - lambda: |-
          if (!id(dialing)) return;
          id(dialing) = false;
          ESP_LOGI("dial", "RAW PULSES: %d", id(pulse_count));
          id(raw_pulses_sensor).publish_state(id(pulse_count));
```

The impulse contact is normally closed, so a pulse is a **break**, which is
`on_release`.

- [ ] **Step 2: Flash and open the log stream**

```bash
cd esphome && esphome logs rotary-phone.yaml
```

- [ ] **Step 3: Run the calibration protocol**

Dial each digit **ten times**, watching the `RAW PULSES` log line. Record every
reading, not just the common one — inconsistency is the finding that matters.

- [ ] **Step 4: Record the result**

Create `docs/bench/phase2-pulse-calibration.md`:

```markdown
# Phase 2 — Pulse calibration

**Date measured:**

## Raw pulse counts, 10 repetitions per digit

| Digit dialled | Readings (10) | Consistent? |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 0 | | |

## Derived constants

- `pulse_offset` = (raw count for digit 1) − 1 =
- `pulse_min` = lowest observed raw count =
- `pulse_max` = highest observed raw count =

## Verdict

Nordic (N+1) or standard (N) dial?

## Debounce notes

Any digit where readings varied across the ten repetitions, and what was changed
(`delayed_on` / `delayed_off` on `dial_impulse`) to stabilise it.
```

- [ ] **Step 5: Tune debounce if readings are inconsistent**

If any digit gives varying counts, the impulse filter is too permissive or too
aggressive:

- Counts **too high** → contact bounce is being counted. Raise `delayed_on` and `delayed_off` on `dial_impulse` from `4ms` toward `10ms`.
- Counts **too low** → real pulses are being filtered out. Lower toward `2ms`.

Re-run Step 3 after each change. Record the final values in the bench doc.

- [ ] **Step 6: Write the confirmed constants into substitutions**

Update the `substitutions:` block in `esphome/rotary-phone.yaml` with your measured
values, and replace the comment:

```yaml
substitutions:
  # Measured in Phase 2 — see docs/bench/phase2-pulse-calibration.md
  pulse_offset: "1"
  pulse_min: "2"
  pulse_max: "11"
```

- [ ] **Step 7: Verify — pass criterion**

All ten digits produce a **consistent** raw count across ten repetitions each, and
the counts form a contiguous run of ten values (e.g. 2–11 for a Nordic dial, 1–10
for a standard one). A gap or an overlap means the dial needs cleaning or the
debounce needs more work — do not proceed.

- [ ] **Step 8: Commit**

```bash
git add docs/bench/phase2-pulse-calibration.md esphome/packages/dial_decode.yaml esphome/rotary-phone.yaml
git commit -m "feat(esphome): add raw pulse counting and record calibration

Phase 2 of bring-up. Confirms pulses-per-digit offset by measurement."
```

---

### Task 5: The decode state machine and the Home Assistant event

**Files:**
- Modify: `esphome/packages/dial_decode.yaml`

**Interfaces:**
- Consumes: globals `pulse_count`, `dialing`; sensor `raw_pulses_sensor`; substitutions `pulse_offset`, `pulse_min`, `pulse_max`
- Produces: HA event `esphome.rotary_dial` with string fields `digit` and `raw_pulses`; template sensor id `last_digit_sensor`; script id `dial_guard`

- [ ] **Step 1: Add the globals and sensor for the emitted digit**

In `esphome/packages/dial_decode.yaml`, extend the `globals:` block with:

```yaml
  - id: last_raw
    type: int
    restore_value: no
    initial_value: '0'
  - id: last_digit
    type: int
    restore_value: no
    initial_value: '0'
```

And extend the `sensor:` block with:

```yaml
  - platform: template
    id: last_digit_sensor
    name: "Last Digit"
    accuracy_decimals: 0
    update_interval: never
```

- [ ] **Step 2: Add the 3-second guard script**

Add a top-level `script:` block to `esphome/packages/dial_decode.yaml`:

```yaml
script:
  # Abort a dial that never returns home (finger slipped, dial jammed).
  - id: dial_guard
    mode: restart
    then:
      - delay: 3s
      - lambda: |-
          ESP_LOGW("dial", "Dial did not return home within 3s; discarding");
          id(dialing) = false;
          id(pulse_count) = 0;
```

- [ ] **Step 3: Replace the shunt automations with the full state machine**

Replace the `on_press:` and `on_release:` blocks under `dial_shunt` (added in Task 4)
with:

```yaml
    on_press:
      - lambda: |-
          id(pulse_count) = 0;
          id(dialing) = true;
      - script.execute: dial_guard
    on_release:
      - script.stop: dial_guard
      - delay: 150ms
      - if:
          condition:
            lambda: 'return id(dialing);'
          then:
            - lambda: |-
                id(dialing) = false;
                id(last_raw) = id(pulse_count);
                int n = id(last_raw) - ${pulse_offset};
                id(last_digit) = (n == 10) ? 0 : n;
            - sensor.template.publish:
                id: raw_pulses_sensor
                state: !lambda 'return id(last_raw);'
            - if:
                condition:
                  lambda: 'return id(last_raw) >= ${pulse_min} && id(last_raw) <= ${pulse_max};'
                then:
                  - sensor.template.publish:
                      id: last_digit_sensor
                      state: !lambda 'return id(last_digit);'
                  - homeassistant.event:
                      event: esphome.rotary_dial
                      data:
                        digit: !lambda 'return str_sprintf("%d", id(last_digit));'
                        raw_pulses: !lambda 'return str_sprintf("%d", id(last_raw));'
                  - logger.log:
                      format: "Dialled %d (raw %d)"
                      args: ['id(last_digit)', 'id(last_raw)']
                      level: INFO
                else:
                  - logger.log:
                      format: "Implausible pulse count %d; discarding"
                      args: ['id(last_raw)']
                      level: WARN
```

Note `raw_pulses_sensor` is published **before** the plausibility check, so a
discarded dial is still visible for debugging. That is deliberate.

**If compilation fails with an error about `${pulse_offset}`:** substitutions
defined in `rotary-phone.yaml` are normally applied to included packages, but if
your ESPHome version does not resolve them inside this package, pass them
explicitly by changing the include in `rotary-phone.yaml` to:

```yaml
packages:
  dial: !include
    file: packages/dial_decode.yaml
    vars:
      pulse_offset: ${pulse_offset}
      pulse_min: ${pulse_min}
      pulse_max: ${pulse_max}
  diagnostics: !include packages/diagnostics.yaml
```

- [ ] **Step 4: Flash**

```bash
cd esphome && esphome run rotary-phone.yaml
```

- [ ] **Step 5: Verify decode — pass criterion**

With `esphome logs rotary-phone.yaml` streaming, dial each digit 0–9 once:

Expected: ten lines reading `Dialled 1 (raw 2)` … `Dialled 9 (raw 10)` … `Dialled 0 (raw 11)` — with your own measured raw values. **The dialled digit must equal the digit on the dial, for all ten.** An off-by-one here means `pulse_offset` is wrong; go back to Task 4 Step 6.

- [ ] **Step 6: Verify the guard — pass criterion**

Rotate the dial to `5`, hold it at the finger stop for **more than 3 seconds**, then release.

Expected: `Dial did not return home within 3s; discarding`, and **no** `Dialled` line, and no HA event.

- [ ] **Step 7: Verify the event reaches Home Assistant — pass criterion**

In HA, open **Developer Tools → Events**, subscribe to `esphome.rotary_dial`, and dial `5`.

Expected: an event with `data: {digit: "5", raw_pulses: "6"}` (or your measured raw value). Note the fields are **strings** — automations must match `"5"`, not `5`.

- [ ] **Step 8: Verify repeats — pass criterion**

Dial `5` three times in a row. Three separate events must appear. This is the whole
reason the digit is an event rather than a sensor state; if only one arrives,
something has been modelled as state.

- [ ] **Step 9: Commit**

```bash
git add esphome/packages/dial_decode.yaml
git commit -m "feat(esphome): add dial decode state machine and HA event

Shunt contact gates digit boundaries, impulse breaks are counted, and a
plausible digit fires esphome.rotary_dial. Implausible counts and dials
that never return home are discarded."
```

---

### Task 6: Bench protocol — wire the hook switch

**HUMAN TASK.** Multimeter required.

The hook is not needed to trigger digits. It is wired now so that hook automations
are possible later without reopening the phone, and so HA's recorder starts
accumulating history immediately.

**Files:**
- Create: `docs/bench/phase3-hook-switch.md`
- Modify: `esphome/packages/dial_decode.yaml`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `binary_sensor` id `hook_switch`, named `Handset Lifted`, `true` when the handset is **off** the cradle

- [ ] **Step 1: Find a usable pole of S1**

The hook switch S1 is a multi-pole switch on the original PCB with terminals
1, 2, 4, 5, 6, 7, 8, 9. With the phone isolated and the original PCB gutted, probe
terminal pairs in continuity mode while lifting and replacing the handset.

Record which pair changes state cleanly and repeatably:

| Pair tried | On cradle | Off cradle | Clean? |
|---|---|---|---|
| | | | |

- [ ] **Step 2: Note the sense**

Record whether your chosen pair is **closed on cradle** or **closed off cradle**.
This determines the `inverted:` value in Step 4.

- [ ] **Step 3: Wire it**

Same RC network as Task 3:

```
3.3V ──[ 10kΩ ]──┬────────────── GPIO5  (pin D3)
                 │
                ═╪═ 100nF
                 │
   S1 pole ──────┴───── GND
```

- [ ] **Step 4: Add the binary sensor**

Add to the `binary_sensor:` block in `esphome/packages/dial_decode.yaml`:

```yaml
  # Hook switch. Not used for triggering — reported so that HA's recorder
  # accumulates history for future hook-based automations.
  # `inverted` set from the sense measured in Phase 3.
  - platform: gpio
    id: hook_switch
    name: "Handset Lifted"
    pin:
      number: GPIO5
      mode:
        input: true
        pullup: true
      inverted: true
    filters:
      - delayed_on: 20ms
      - delayed_off: 20ms
```

If your pole is **closed on cradle**, `inverted: true` gives `Handset Lifted = OFF`
when on the cradle, which is correct. If it is **closed off cradle**, change to
`inverted: false`.

- [ ] **Step 5: Flash**

```bash
cd esphome && esphome run rotary-phone.yaml
```

- [ ] **Step 6: Record the result**

Create `docs/bench/phase3-hook-switch.md`:

```markdown
# Phase 3 — Hook switch

**Date measured:**

## Pole selection

| Pair tried | On cradle | Off cradle | Clean? | Chosen? |
|---|---|---|---|---|
| | | | | |

## Sense

Chosen pole is closed when the handset is: (on cradle / off cradle)

`inverted:` value used in `dial_decode.yaml`:

## Notes

Any bounce observed, and whether the 20ms filter was sufficient.
```

- [ ] **Step 7: Verify — pass criterion**

In Home Assistant, the `Handset Lifted` entity reads **off** with the handset on the
cradle and **on** with it lifted. Lift and replace five times — every transition must
register, with no doubles.

- [ ] **Step 8: Commit**

```bash
git add docs/bench/phase3-hook-switch.md esphome/packages/dial_decode.yaml
git commit -m "feat(esphome): add hook switch binary sensor

Phase 3 of bring-up. Hook state reported to HA for future automations;
not used for digit triggering."
```

---

### Task 7: Integrate into the phone and verify RF

This is where the steel base plate risk gets measured rather than assumed.

**Files:**
- Create: `docs/bench/phase4-rf-check.md`
- Modify: `esphome/packages/dial_decode.yaml` (silence the impulse sensor)

**Interfaces:**
- Consumes: everything from Tasks 3–6
- Produces: an assembled phone; `dial_impulse` no longer exposed to Home Assistant

- [ ] **Step 1: Stop the impulse sensor flooding the recorder**

Every dial pulse is a state change. Left exposed, this writes tens of rows to HA's
database per dialled digit for no benefit. It stays visible on the device's own web
page for debugging.

Add to the `dial_impulse` binary sensor in `esphome/packages/dial_decode.yaml`:

```yaml
    internal: true
```

and remove its `name: "Dial Impulse"` line (internal components must not have a name).

- [ ] **Step 2: Strip the phone**

Remove and discard: transformer T1, varistors V1–V3, capacitors C1 and C2,
resistors R1–R5, and the line cord and plug.

Keep in place: the dial mechanism, the hook switch, the bell assembly (unused — it
is most of the phone's weight and character), and the handset (unwired).

Gut the original PCB but **retain its screw terminals** as the wiring block.

- [ ] **Step 3: Mount the board and antenna**

Mount the XIAO in the base cavity. Route the u.FL external antenna **up into the
plastic cover, as far from the steel base plate as the lead allows**. Route the
USB-C cable out through the hole the original line cord used.

- [ ] **Step 4: Measure RSSI with the cover off**

With the phone assembled but the cover off, read the `WiFi Signal` sensor in HA.
Record the value.

- [ ] **Step 5: Measure RSSI with the cover on**

Fit the cover, wait 60 s for the sensor to update, and record again.

- [ ] **Step 6: Record the result**

Create `docs/bench/phase4-rf-check.md`:

```markdown
# Phase 4 — RF check

**Date measured:**
**Antenna position:**

| Condition | RSSI (dBm) |
|---|---|
| Cover off | |
| Cover on | |

**Pass criterion: better than −70 dBm with the cover on.**

Result: PASS / FAIL

## If FAIL

Antenna positions tried and their readings:

| Position | RSSI (dBm) |
|---|---|
| | |
```

- [ ] **Step 7: Verify — pass criterion**

RSSI with the cover on is **better than −70 dBm**. If not, reposition the antenna
and re-measure before closing the phone. Do not proceed with a marginal reading —
this is the fault that will otherwise present later as random missed digits.

- [ ] **Step 8: Re-verify decode after assembly**

Dial all ten digits once with the phone fully assembled. All ten must decode
correctly, as in Task 5 Step 5. Wiring disturbed during assembly is common.

- [ ] **Step 9: Commit**

```bash
git add docs/bench/phase4-rf-check.md esphome/packages/dial_decode.yaml
git commit -m "feat: integrate board into phone shell and verify RF

Phase 4 of bring-up. Impulse sensor made internal to stop recorder churn."
```

---

### Task 8: Home Assistant automations

**Files:**
- Create: `ha/automations/rotary_dial.yaml`
- Modify: `README.md`

**Interfaces:**
- Consumes: HA event `esphome.rotary_dial` with string field `digit`
- Produces: ten automations, one per digit

- [ ] **Step 1: Test an automation before writing ten**

In HA, **Developer Tools → Events → Fire event**:

```yaml
event_type: esphome.rotary_dial
event_data:
  digit: "5"
  raw_pulses: "6"
```

This lets you develop and debug automations without touching the phone.

- [ ] **Step 2: Write the automations**

Create `ha/automations/rotary_dial.yaml`. This file is a reference copy kept in this
repo; paste its contents into your HA `automations.yaml` or create the automations
through the UI.

```yaml
# Rotary phone dial → actions.
# The device fires esphome.rotary_dial with digit as a STRING.
# Replace each action with whatever that digit should do.

- id: rotary_dial_1
  alias: "Rotary dial 1"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "1"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_1

- id: rotary_dial_2
  alias: "Rotary dial 2"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "2"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_2

- id: rotary_dial_3
  alias: "Rotary dial 3"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "3"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_3

- id: rotary_dial_4
  alias: "Rotary dial 4"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "4"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_4

- id: rotary_dial_5
  alias: "Rotary dial 5"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "5"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.movie_night

- id: rotary_dial_6
  alias: "Rotary dial 6"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "6"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_6

- id: rotary_dial_7
  alias: "Rotary dial 7"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "7"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_7

- id: rotary_dial_8
  alias: "Rotary dial 8"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "8"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_8

- id: rotary_dial_9
  alias: "Rotary dial 9"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "9"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_9

- id: rotary_dial_0
  alias: "Rotary dial 0"
  trigger:
    - platform: event
      event_type: esphome.rotary_dial
      event_data:
        digit: "0"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.CHANGE_ME_0
```

- [ ] **Step 3: Verify — pass criterion**

Set up digit `5` against a real scene. Dial `5` on the phone. The scene activates.

Then dial `5` twice more — it must activate all three times.

- [ ] **Step 4: Update the README**

In `README.md`, under the `- **Use the dial for shortcuts**` feature, add:

```markdown
  Implemented as an ESPHome bridge — see
  [the design spec](docs/superpowers/specs/2026-09-19-rotary-dial-ha-bridge-design.md)
  and [`esphome/`](esphome/). Dialling a digit fires the Home Assistant event
  `esphome.rotary_dial`; the digit-to-action mapping lives in Home Assistant.
```

- [ ] **Step 5: Commit**

```bash
git add ha/automations/rotary_dial.yaml README.md
git commit -m "feat(ha): add rotary dial automations and document the bridge

Ten automations, one per digit. Dialling 5 activates a scene."
```

---

## Deferred (explicitly not in this plan)

Named so they are not mistaken for oversights:

- **Battery operation.** The XIAO's BAT pads keep it viable; no work here.
- **Ringing the bell.** No output path is built. Would need a driver and is out of scope.
- **Multi-digit codes.** The state machine emits per-digit, so sequences could be composed in HA later with no firmware change.
- **Promoting decode to an ESPHome `external_component`.** The named escape hatch if the Task 4 protocol proves the lambda insufficient. The Task 4 protocol becomes its test fixture.
