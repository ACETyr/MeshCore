# Flashing the repeater firmware

*🇩🇪 [Deutsche Fassung](./flashing-repeater.de.md) (primary) · ⚙️ [Forward-filter manual](./forward-filter.md)*

This guide covers how to get the ACETyr repeater firmware (`repeater-v1.17.0.fwdfilterN`) onto a
device — with the web flasher, with esptool, and over the air.

The **[MeshCore web flasher](https://flasher.meshcore.io)** is the recommended route, same as for the
official firmware. It does not list this firmware — this fork is not *distributed* through the flasher
— but it can flash it: the **"Custom Firmware"** entry at the bottom of the device list loads a file
from your own computer, straight out of this fork's
[releases](https://github.com/ACETyr/MeshCore/releases).

---

## Step 1 — download the right file

Always take the **newest** release ([releases](https://github.com/ACETyr/MeshCore/releases)); older
ones contain bugs that have since been fixed. Which of the files you need depends on the board — and
on whether you want to **update** or **start fresh**:

| Board | Update (config preserved) | Fresh install / wipe | OTA |
|---|---|---|---|
| **RAK4631** (nRF52840) | `…​.zip` | `…​.zip` | `…​.zip` |
| **Heltec V3** (ESP32-S3) | `…​.bin` (**no** `merged`) | `…​-merged.bin` | `…​.bin` (**no** `merged`) |
| **SenseCAP Solar Node P1** (nRF52840) | `…​.zip` | `…​.zip` | `…​.zip` |
| **Seeed XIAO nRF52840 + Wio-SX1262** | `…​.zip` | `…​.zip` | `…​.zip` |

On the nRF52 boards it is always the same `.zip` — a DFU package that replaces only the application and
leaves configuration and identity alone. The `.uf2` that also ships is an alternative for the
drag-and-drop route without a flasher (see [route C](#route-c--rak4631--sensecap-p1-via-uf2-drag-and-drop));
the web flasher does **not** accept it.

On the Heltec V3 everything hinges on one distinction:

> ⚠️ **`-merged.bin` erases the entire flash — including the device identity.**
> It contains bootloader, partition table and application, is written to address `0x0`, and the web
> flasher performs a full chip erase along with it (it warns you about this itself). Afterwards the
> node has a **new pubkey** and has to be re-registered everywhere.
>
> **To update a running node, take the plain `.bin` without `merged` in the name.** It replaces only
> the application; name, password, radio and region settings and the identity are preserved. The same
> file is used for OTA.

> ℹ️ **SenseCAP Solar Node P1** is **build-validated only, not hardware-tested** — no device was
> available. The filter code is board-agnostic and compiles cleanly, but treat these binaries as
> unverified. Feedback from P1 operators is very welcome.

> ℹ️ The **XIAO firmware** is tested on the kit of XIAO nRF52840 with a **Wio-SX1262** stacked on
> top (Seeed part 102010710) and assumes exactly that pinout. A XIAO with a different LoRa module —
> an E22, say, or the Wio-SX1262 variant with the 30-pin board-to-board connector — will not work
> with this image.

---

## Step 2 — flash it

### Route A — web flasher (recommended)

Browser: **Chrome or Edge**. Firefox and Safari cannot do WebSerial and will not work.

1. Open <https://flasher.meshcore.io>.
   *(The Austrian community flasher at <https://flasher.meshcore-austria.at> is a fork of it and
   behaves identically — either works.)*
2. Do **not** pick your board from the device list. Instead click **"Custom Firmware"** at the very
   bottom and select the file you downloaded in step 1. The flasher works out the target from the file
   type: `.zip` → nRF52, `.bin` → ESP32.
3. Connect the device over USB.
4. **nRF52 boards only (RAK4631, SenseCAP P1, XIAO):** put the device into DFU mode — either with
   the **"Enter DFU mode"** button in the flasher, or manually by **pressing the reset button twice
   in quick succession**. In DFU mode the XIAO shows up on a **different serial port** than in
   normal operation, so pick the newly appeared port in the next step.
5. Start flashing, pick the serial port, wait.

If you select a `-merged.bin`, the flasher shows a warning that the flash will be erased — that is
correct and intended, see above. When updating, you do *not* want to see that warning.

### Route B — Heltec V3 with esptool (command line)

For scripting and bulk flashing. `pip install esptool`, then:

```bash
# update a running node — configuration preserved
esptool.py --chip esp32s3 --port COM5 --baud 921600 write_flash 0x10000 Heltec_v3_repeater-v1.17.0.fwdfilter8-<sha>.bin

# fresh install — erases the identity
esptool.py --chip esp32s3 --port COM5 --baud 921600 write_flash 0x0 Heltec_v3_repeater-v1.17.0.fwdfilter8-<sha>-merged.bin
```

`<sha>` is the short commit hash in the name of the file you downloaded — just use the actual
filename from the release.

On Linux/macOS use the appropriate port instead of `COM5` (`/dev/ttyUSB0`, `/dev/cu.usbserial-…`). If
the connection is unstable, drop the baud rate to `115200`.

### Route C — RAK4631 / SenseCAP P1 via UF2 (drag and drop)

No tooling at all, just a file manager. Cannot brick the node.

1. Connect the device over USB.
2. **Press the reset button twice in quick succession.** A USB drive appears (named `RAK4631` on the
   RAK4631; on the XIAO `XIAO-SENSE` or `XIAO-BOOT`, depending on the bootloader).
3. Copy the `.uf2` file onto that drive.
4. The drive disappears on its own and the device reboots. Done.

The `.uf2` replaces only the application; configuration and identity are preserved.

If the double reset does not work: try slower (two separate clicks, not a double-click), and try
another USB cable — many cables can only charge, not carry data.

### Route D — over the air, nRF52 boards (RAK4631, SenseCAP P1, XIAO)

For nodes you can no longer reach physically. You need BLE range to the device and admin access over
the air.

1. Get the release **`.zip`** onto your phone — the same file the web flasher uses.
2. Install the **nRF Device Firmware Update** app (iOS App Store / Google Play, search `nrf dfu`).
3. In the MeshCore app, log in to the repeater as admin via remote management and enter `start ota` in
   the command line tab. A reply of `OK` means the device is in OTA mode.
4. In the DFU app's `Settings`, enable **Packet receipt notifications** and set **Number of Packets**
   to `10` (RAK4631; `8` also works, and is the right value for the T114). Without this, uploads
   frequently abort.
5. Select the ZIP file, pick the device from the list and start `Upload`. It takes a few minutes.

If the device does not appear in the list: enable `Force Scanning` in the DFU app and issue
`start ota` again — OTA mode times out after a while.

> 💡 **Strongly recommended for anything on a mast:** install the
> [OTAFIX bootloader](https://github.com/oltaco/Adafruit_nRF52_Bootloader_OTAFIX) first. It detects an
> invalid application firmware and falls back to OTA DFU mode by itself, instead of leaving the node
> dead on the mast. An aborted OTA flash then stops being a climbing job. Background:
> <https://blog.meshcore.io/2026/04/06/otafix-bootloader>
>
> For the **XIAO** there are two OTAFIX variants, `xiao_nrf52840_ble` and `xiao_nrf52840_ble_sense`.
> Which one fits is in `INFO_UF2.TXT` on the USB drive (double reset): if the `Board-ID` line
> contains `Sense`, take the `_sense` variant, otherwise the other one. Over-the-air updates have
> not been tried on the XIAO yet, only the USB routes.

### Route E — over the air, Heltec V3

1. Have the **non**-`merged` `.bin` of the release ready.
2. Log in as admin via remote management and issue `start ota`.
3. On ESP32 devices this opens a Wi-Fi hotspot named **`MeshCore OTA`**. Connect with a phone or
   laptop.
4. Open <http://192.168.4.1/update> in a browser and upload the `.bin`.

This requires Wi-Fi range to the node — for a masthead node, usually not something that works from the
ground.

---

## Step 3 — verify it worked

At the CLI:

```
ver
> v1.17.0.fwdfilter8-<sha> (Build: …)
```

If the version matches the release, the device has the right firmware. Cross-check that the fork
features are actually present:

```
get fwd.hashfilter
> off prob=100
```

If the node answers with an error instead of a status, it is running mainline firmware without the
forward filter.

---

## Check the duty cycle

Before the node transmits for any length of time: **check the duty cycle and set it to whatever is
permitted at your location.**

```
get dutycycle
set dutycycle <value>     # 1-100, in percent
```

> ⚠️ **The shipped value is not a permitted value.** The firmware starts with an airtime factor of
> 1.0, which is a **50 %** duty cycle. In most of the bands MeshCore is operated in that is far above
> the permitted share. The default is a technical setting inherited from mainline firmware, not a
> statement about what you are allowed to transmit.

Which value is correct depends on the band, the channel and the legal situation where your node
stands. Knowing and observing that is **solely the responsibility of the node's operator** — this
firmware is distributed internationally and cannot name a number for you. If in doubt, ask your
national regulator or amateur radio society.

The value does more than keep you legal: the airtime reserve in
[stage 4](./forward-filter.md#stage-4--airtime-reserve-for-scoped-traffic) derives its window
allowance directly from the duty cycle, so a wrong duty cycle also skews the filter behaviour.

> ℹ️ **`set af` is the old route** and works on the reciprocal (`af = 100 / duty cycle − 1`). MeshCore
> 1.15 added `set dutycycle`, which takes plain percent. Use `dutycycle`; `af` only remains for
> compatibility. Older nodes that answer `get dutycycle` with `??` are running pre-1.15 firmware and
> have to be set through `af`.

---

## CLI access

Three routes, all equivalent — the forward-filter commands work on any of them:

**Over USB, in the browser.** Open <https://config.meshcore.io> in Chrome or Edge, connect the device
over USB, select the serial port. The most convenient route for initial setup. (The web flasher has the
same thing built in under "Serial console".)

**Over the air, from the MeshCore app.** Add the repeater as an admin (remote management), then use
the command line tab. This is the route for field nodes — and the reason the whitelist always lets
adverts and `ANON_REQ` through: so this access survives a broken filter configuration.

**From the command line.** [`meshcore-cli`](https://github.com/fdlamotte/meshcore-cli) — for scripts,
bulk configuration, and anything that needs to be reproducible.

After flashing, continue with the [forward-filter manual](./forward-filter.md).

---

## What survives a flash

An **update** — `.zip`, `.uf2` or the non-`merged` `.bin`, by any route — leaves the filesystem and
therefore the configuration alone: node name, admin password, radio and region settings, and the device
identity (the pubkey) are preserved. After the reboot it is the same node.

Two exceptions:

- **A `-merged.bin` flash or a flash erase wipes everything**, including the identity. The node then
  has a new pubkey and has to be re-registered everywhere — in other operators' whitelists as much as
  in your own documentation. Only do this if that is exactly what you want.
- **Upgrading from `fwdfilter3` to `fwdfilter4` or newer** resets the filter configuration once (the
  move to the dedicated `/fwd_prefs` file). Re-add whitelist and blacklist entries afterwards — best
  to run `get fwd.whitelist` and `get fwd.block` beforehand and keep the output. Everything else is
  preserved.

---

## Downgrading from fwdfilter8

`fwdfilter8` is based on MeshCore 1.17, and 1.17 changed the format of the settings file: instead of
the old `/com_prefs` blob it now writes `/prefs.json`.

On the first boot after the upgrade the firmware reads the existing `/com_prefs` one last time and
writes only `/prefs.json` from then on. Nothing changes for you: all settings migrate automatically,
there is nothing to do.

> ⚠️ **The old `/com_prefs` is left in place and is never updated again.** It freezes at the state
> the node was in immediately before the upgrade.
>
> If you later flash a version older than `fwdfilter8`, that firmware does not know `/prefs.json` and
> reads the frozen `/com_prefs`. **Every change you made since upgrading to fwdfilter8 is then
> silently gone** — no error, the node simply carries on with the old configuration. Radio, region
> and node settings are affected.

The filter configuration in `/fwd_prefs` is **not** affected: it lives in its own file and survives
the move in both directions.

If you are planning a downgrade, write down the current state first — `get radio`, `get name`,
`get dutycycle` and whatever else you changed — and set it again afterwards.

---

## Going back to mainline

Select the official repeater firmware in the web flasher — this time through the device list as usual
— and flash it. The same distinction applies: the update variant keeps the identity, the wipe variant
does not.

The filter configuration in `/fwd_prefs` stays behind as an orphaned file and is ignored by mainline
firmware, so the filters are inert. Flash a fwdfilter build again later and the old configuration is
back.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Browser does not see the device | WebSerial exists only in Chrome and Edge, not Firefox or Safari |
| Web flasher rejects the file | The file picker only accepts `.zip` and `.bin`. For nRF52 use the `.zip`, not the `.uf2` |
| RAK4631: flasher reports a DFU error | The device was not in DFU mode. Use "Enter DFU mode" in the flasher, or press reset twice |
| No USB drive after double reset | Two separate clicks, not a double-click; try another USB cable (many are charge-only) |
| esptool cannot find the port | Missing USB driver (CP210x/CH340); on Linux a permissions issue — add your user to `dialout` |
| Heltec will not boot after flashing | Probably the non-`merged` `.bin` written to address `0x0`. Re-flash the `-merged.bin` at `0x0` |
| Node has a new pubkey after flashing | It was a `-merged.bin` flash. Use the non-`merged` `.bin` to update |
| OTA aborts partway through | Enable `Packet receipt notifications`, set `Number of Packets` to 10; toggle Bluetooth on the phone; forget the device in Bluetooth settings and re-pair |
| Device not listed in the DFU app | Issue `start ota` again (the mode times out), enable `Force Scanning` |
| Node dead after a failed OTA | Without the OTAFIX bootloader, only on-site USB helps. Which is exactly why you install OTAFIX **first** |

If it persists: [open an issue](https://github.com/ACETyr/MeshCore/issues) — with board, release,
flashing route, and the exact error message.
