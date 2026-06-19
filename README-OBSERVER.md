# MeshCore MQTT Observer — room-server build (1.16)

A Room Server that also bridges heard mesh packets to an MQTT broker. Based on
**`agessaman/MeshCore@mqtt-bridge-implementation`** (mainline **v1.16.0**), plus:

- the SNR/RSSI and zone-aware-UTC-timestamp fixes (upstream PRs #13 / #14, cherry-picked), and
- per-broker TLS on the main-broker connect path (scheme-aware `mqtts://`, CA verification).

A room server almost never transmits, which suits the observer role (a node is blind to the
mesh during its own TX).

**No credentials are baked into any build.** Broker host/user/password and WiFi are configured
at runtime over the serial CLI. (A pinned broker *CA certificate* is public verification
material, not a credential — see TLS below.)

## Target hardware

- **Heltec LoRa32 V3** (ESP32-S3, SX1262), 8 MB flash.
- LoRa region: set to your region via CLI (`set radio …`, comma-separated freq,bw,sf,cr).

## Build envs

| Env | TLS trust | Use |
|-----|-----------|-----|
| `Heltec_v3_room_server_observer_mqtt` | public mbedTLS CA bundle | distributable — any broker with a publicly-trusted cert (or plaintext) |
| `Heltec_v3_room_server_observer_mqtt_meshcore` | above **+ pinned MeshCore broker CA** | publishing to the `logger-at.meshcore.observer` broker (self-signed cert) |

Build (reuses the Evo-Port poetry/PlatformIO env via `-d`, or run `pio` directly in this tree):

```bash
cd ../MeshCore-Evo-Port
poetry run pio run -d ../MeshCore-116 -e Heltec_v3_room_server_observer_mqtt[ -t upload --upload-port COM3]
```

Use app-only `-t upload` (never `uploadfs`/`erase`) to preserve the node identity in SPIFFS.

## First-time configuration (serial CLI, 115200 baud)

The image ships with **no** WiFi or broker settings.

```
set wifi.ssid     <your-wifi-ssid>
set wifi.pwd      <your-wifi-password>
set mqtt.server   <broker-host>          ; MUST prefix mqtts:// for TLS — a bare host = plaintext mqtt:// (see TLS below)
set mqtt.port     <broker-port>          ; e.g. 8883/9010 (TLS) or 1883 (plaintext)
set mqtt.username <broker-user>
set mqtt.password <broker-password>
set mqtt.iata     <3-letter-code>        ; REQUIRED — an empty/"XXX" IATA blocks ALL publishing
set bridge.enabled on
set mqtt.status on
set mqtt.packets on
reboot                                    ; required: the running bridge re-reads server/IATA only on boot
```

Check state: `get mqtt.status`, `get wifi.status`, `ver`.

## ⚠️ NTP reachability is required

Timestamps and JWT tokens depend on a correct clock. After WiFi connects, the firmware syncs
time over **NTP** (`pool.ntp.org`, UTC, re-synced hourly; ESP32 SNTP fallback). This needs
**outbound internet from the node**: DNS resolution + UDP **port 123** to `pool.ntp.org`.

If the node is on an isolated LAN/VPN with no internet break-out, NTP fails and the node falls
back to a free-running RTC — timestamps drift, and until the first successful sync the clock may
sit below the 2024-01-01 sanity floor, delaying status/JWT publication. **Ensure the node can
reach an NTP server**, or provide a reachable one on the network.

## ⚠️ Do not set `mqtt.timezone` on a CoreScope-fed node

The packet `timestamp` is emitted as zone-aware UTC (RFC 3339 "Zulu", e.g. `…T21:09:45.937656Z`).
A CoreScope aggregator trusts zone-aware UTC. If you set a local `mqtt.timezone`, the firmware
emits **naive local** time instead, which CoreScope clamps to ingest time and flags
(`clock_naive`/`clock_skew`). Leave `mqtt.timezone` unset for CoreScope feeds. (A local human-
facing broker is unaffected.)

## ⚠️ Memory: one or two TLS connections max on the Heltec V3

The Heltec V3 has **no PSRAM** — WiFi, TLS and MQTT all share the ESP32-S3's ~512 KB internal
RAM. Each TLS/MQTT connection needs a sizeable contiguous mbedTLS buffer, so the board can
realistically sustain **one, at most two** concurrent TLS connections.

The two **LetsMesh analyzer** feeds (`mqtt.analyzer.us` / `mqtt.analyzer.eu`) default to **on**.
Together with your own `mqtts://` broker that is **three** TLS connections — enough to fragment the
heap below the publish threshold. The tell in the serial log:

```
MQTT: Skipping publish due to memory pressure (Max alloc: 16116, skipped: N)
```

`Max alloc` is the largest free block; the bridge **drops** every publish while it is < 60 KB, and
the pressure can also trigger `rst:0xc (RTC_SW_CPU_RST)` reboots.

If you only publish to your own broker, turn the analyzers off:

```
set mqtt.analyzer.us off
set mqtt.analyzer.eu off
reboot
```

Three TLS clients → one clears the pressure. Disabling just one analyzer (→ two) may suffice if you
want to keep some LetsMesh coverage, but one is the safe target on this board.

## TLS

TLS is selected per broker by the **URI scheme**: set `mqtt.server mqtts://<host>` (or `wss://`)
to use TLS; a bare host stays plaintext `mqtt://`.

> **Forgot the `mqtts://`?** A bare host against a TLS-only broker port connects at TCP and is
> then reset by the broker mid-handshake. The serial log shows the host with **no** scheme plus a
> clean reset — `errno = Connection reset by peer` / `socket errno: 0x68` (= 104, ECONNRESET) /
> `MQTT connect failed`. (An untrusted-cert problem looks different — mbedTLS handshake errors,
> not a peer reset.) Fix: `set mqtt.server mqtts://<host>`, `reboot`, confirm with
> `get mqtt.server` that the value echoes back **with** the prefix.

- **Default (`…_observer_mqtt` env):** TLS verifies against the public mbedTLS CA bundle — works
  for any broker presenting a publicly-trusted certificate.
- **`…_meshcore` env:** additionally pins the MeshCore observer-broker CA and skips the server-CN
  check (that broker presents a placeholder CN). Required for the `logger-at.meshcore.observer`
  broker, whose cert is self-signed with a CN we don't control.

Note: "encrypt without verifying" is **not** available — the prebuilt Arduino-ESP32 framework
compiles `CONFIG_ESP_TLS_SKIP_SERVER_CERT_VERIFY` out, so a CA is always required for `mqtts://`.

### Security note

Default **admin password is `password`** — change it after first boot. The pinned CA is public
material; no broker/WiFi credentials are baked into the firmware.
