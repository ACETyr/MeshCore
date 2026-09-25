# Carried upstream patches

Changes in this fork that originate **upstream** and are carried ahead of mainline merging them.
Listed so that provenance is visible without diffing, and so each one has a written removal
condition instead of silently becoming permanent fork divergence.

Fork-original work (the forward filter, `/fwd_prefs`, the airtime guard) is not listed here — see
`FEATURE-*.md` and `docs/forward-filter.md` for those.

---

## Active

### meshcore-dev/MeshCore#2933 — median noise-floor estimator

| | |
|---|---|
| Upstream author | usrflo |
| Upstream PR | https://github.com/meshcore-dev/MeshCore/pull/2933 (OPEN) |
| Applied as | `a028adcb` (median only), **refreshed to PR head `fa6557f8` in the 1.17.1 replant** |
| Files | `src/helpers/radiolib/RadioLibWrappers.{h,cpp}` |
| Carried scope | the noise-floor estimator only. The PR's later RX-desync watchdog (`5017924c` and after) is **not** carried — open decision, see below |
| Fork issue | ACETyr/MeshCore#3 |

**The patch is usrflo's work, applied essentially verbatim** — the `sortInt16()` helper, the
explanatory comments and the `_floor_block_ready` flag are all his. This fork contributed only an
independent bench reproduction, posted to the PR on 2026-08-09.

**What it fixes.** `RadioLibWrapper::loop()` admitted a noise-floor sample only if
`rssi < _noise_floor + SAMPLING_THRESHOLD`, a one-way ratchet: each 64-sample block mean came from a
lower-truncated set, walked down to the -120 clamp and stuck there, leaving the RSSI-margin LBT
permanently over-sensitive. The patch accepts every idle sample and reduces the block to its median,
which recovers in both directions.

**Why carried rather than waited out.** Reproduced on our own hardware and verified fixed: 250
zero-hop adverts at 0.4 s wedges a stock node at -120 in 18.9 s; the patched build under identical
stimulus holds -104 with 56 blocks in 199 s, 15 up / 14 down. Mainline 1.17, 1.17.1 and current `dev`
all still ship the ratchet.

**Refreshed to `fa6557f8` in the 1.17.1 replant (2026-08-16).** The PR gained three things after
`a028adcb` was taken, and all three matter enough that carrying the older revision was the worse
option: 50 ms sample spacing (a block spans a real ~3.2 s window instead of a few ms), a one-sided
15 dB hold, and a bound on that hold. Measured on the bench the same day, control `34ad059a` vs
`fa6557f8`, matched stimulus:

- what we carried before published the *busy-channel* level under load (-56 on 2026-08-10) — with the
  spacing and hold it stays at the idle floor instead;
- 43 published values in a full run, every one -105, no -120 anywhere, while the control hit the
  clamp 8 s into the load;
- the bound releases a genuinely persistent rise: `held 1/3` → `2/3` → `noise_floor = -37 (accepted
  after 3 held blocks)`, then falls back to -105 by itself once the channel clears.

Applied surgically, not by taking the PR's files wholesale — those would have reverted this fork's
own airtime-fallback work (`_airtime_full_ms`, `AIRTIME_ANCHOR_MIN_BYTES`) which lives in the same
two files. `loop()` is now byte-identical to `fa6557f8` apart from one added comment. Posted to the
PR as `pull/2933#issuecomment-5309823975`.

⚠️ **This is an unmerged PR that moved twice in six days.** Re-diff against the PR head at every
replant rather than assuming the carried copy is current — that is exactly how it went stale here.

⚠️ **Refreshing to the head no longer means taking the whole head — and that split needs re-deciding,
not re-reading.** On **2026-09-03** the PR outgrew its title: `5017924c` adds an **RX-desync
watchdog** (`verifyRxChipMode()`, 10 s poll, `resetAGC()` self-heal, `ERR_EVENT_RX_DESYNC`), which
has nothing to do with the ratchet. We are pinned at `fa6557f8` (2026-08-12) and therefore do not
carry it. That is a decision with a date on it, and here is what it rested on:

- **As written in `5017924c` the watchdog misfires on a healthy radio**, through a RadioLib bug:
  `SX126x::getStatus()` calls `SPIreadStream(..., numBytes = 0)` and never copies the status byte
  out, so it returns 0 unconditionally and `((getStatus() >> 4) & 0x07) == 0x05` is always false.
  agessaman measured it on a RAK4631 (`pull/2933#issuecomment-5672571602`): 14 receiver resets in
  130 s on an *idle, healthy* node, 337/h under traffic, `ERR_EVENT_RX_DESYNC` set and the node
  reporting "reboot suggested". On SX126x each of those is a warm sleep, standby and full
  recalibration — not a cheap status retry.
- **usrflo confirmed and fixed it the same day**, `3e55f997` (2026-09-15): a raw `[GetStatus, NOP]`
  transaction over the module HAL, taking byte 1. Upstream RadioLib issue jgromes/RadioLib#1872 filed
  for the root cause. The fix is HW-validated **on his rig** (Wio Tracker L1 / nRF52840) — not on a
  RAK4631, not on a Heltec V3, i.e. not on anything this branch publishes.

**Re-evaluate at the next replant, and write the answer down.** Do not treat "we skipped the
watchdog" as standing policy — work these four points:

1. Is jgromes/RadioLib#1872 fixed, and has MeshCore moved its pinned RadioLib (was `6d893483`)? If
   both, `3e55f997`'s raw-SPI workaround may itself be obsolete or in conflict.
2. Has the watchdog been measured on a **RAK4631 or Heltec V3** by anyone, us or upstream? If not and
   we want it, that is a bench run, not a diff review — the failure mode presents as a *healthy* node,
   so reading the code is exactly what will not catch it. Signature to look for: `resetAGC()` cadence,
   `stats-radio` `rx_desync`, `stats-core` `errors: 8` on an idle node.
3. Do we want the self-heal at all, or only its instrument? `sx126xGetStatus()` on its own answers
   "is the SX1262 actually in RX right now", which we currently cannot ask — potentially useful for
   the open receiver-deafness question on the field nodes, and separable from the 10 s reset loop.
4. Record the outcome and the date here either way. "Still out of scope, re-checked YYYY-MM-DD,
   because X" is a result. Silence reads as staleness and is how `a028adcb` went stale.

**Re-checked 2026-09-25 — still out of scope. Point 1 is half-answered, points 2 and 3 are
untouched.** A maintainer fix for #1872 is now in flight, but nothing has merged and the pin has not
moved, so the split stands unchanged.

- **jgromes/RadioLib#1872 is still open, but no longer unowned.** jgromes assigned and labelled it
  and commented on 2026-09-22: the diagnosis is right, but `3e55f997`'s approach is not the whole
  fix. SX126x and SX128x differ — on SX126x the first byte is RFU, on SX128x it is already status —
  and with a plain extra NOP the value `getStatus()` *returns* on SX128x differs from the one the
  library processes internally (0x43 against 0x40). His fix sets the SPI status width properly and
  drops it to 0 for the `GetStatus` transaction only. Filed as **jgromes/RadioLib#1876**
  ("[SX126x][SX128x] Fix GetStatus", head `6900cd25`, base `master`, `Closes #1872`) — **open, not
  merged**. usrflo verified the SX126x half on his own rig on 2026-09-23: 120/120 polls of the fixed
  `getStatus()` byte-identical to the raw-SPI reference, `getDeviceErrors()` clean, no regression in
  any exercised read path. SX128x unverified — no hardware on his side.
- **MeshCore has not moved its pin.** `platformio.ini:23` is
  `6d8934836678d8894e3d556550475b37dce3e2b6` on upstream `dev` *and* `main`, identical to this
  branch. RadioLib's 8.0.0 release PR **#1867 is also still open**; #1876 targets `master`, so the
  fix can land independently of 8.0.0.
- ⇒ **`3e55f997`'s raw-SPI workaround is not obsolete yet and conflicts with nothing here** — this
  branch carries neither it nor the watchdog. What would make it obsolete is now concrete and
  watchable: #1876 merged **and** MeshCore repinned away from `6d89348`. Once both hold, the only
  argument left against the watchdog is point 2, and point 2 is unmoved: still nobody, us or
  upstream, has measured it on a RAK4631 or a Heltec V3.
- **#2933 itself gained nothing functional.** Head moved `3e55f997` → **`9f2e4b5d`** (2026-09-23),
  a comment-only commit (`src/helpers/radiolib/SX126xReset.h`, +5/−0) linking #1872 and #1876 from
  the workaround. Still open, still no maintainer review, no PR comment since 2026-09-16.
- **Removal condition not triggered.** Neither ratchet PR merged; #2842 unmoved since 2026-08-10
  (`bafa673a`). `fa6557f8` remains the correct pin.

Note for anyone debugging in the meantime: mainline's own `MESH_DEBUG_PRINTLN("SX1262 status=0x%02X …")`
in `CustomSX1262.h` hits the same RadioLib bug, so a boot log showing `status=0x00` carries no
information — it is that constant, not a chip fault.

**Removal condition.** Drop this patch when mainline merges a fix for the ratchet, then re-verify on
the bench rig before release. Two competing PRs are open and neither has a maintainer review:

- **#2933** (usrflo) — what we carry. +42/-22 across 2 files.
- **#2842** (yg-ht) — same root cause, much broader: absolute clamps, `noise.sample.ms` /
  `noise.window.secs` / `noise.clamp.low` / `noise.clamp.high`, a `stats-noise` CLI, unit tests and
  VNA cross-validation. +1235/-61 across 22 files.

If **#2842** wins, this is not a clean revert — it rewrites the estimator our patch touches. Expect
to drop `a028adcb`'s hunks wholesale and take upstream's version, then re-run the bench stimulus,
because #2842's absolute clamps (`noise.clamp.low` default -125) interact with the -120 behaviour we
tested against.

**Attribution is owed and unpaid.** `a028adcb` is authored by this fork with no `Co-authored-by:`
trailer, and it is already pushed, so amending would rewrite published history. Decision
(2026-08-09): settle it in the **release notes** instead. Any release carrying this patch — starting
with the first 1.17-based one — must credit usrflo and link #2933 by name in the notes, in both the
German and English text. This is not optional garnish; it is the only place the credit now appears
for anyone flashing the firmware.

Do **not** re-submit this patch upstream under fork authorship. It is already filed as #2933.

---

## Resolved

### meshcore-dev/MeshCore#3137 — `fem_rxgain` bound to the wrong field

Upstream author agessaman. The fork carried the one-line `CommonCLI.h` fix because
`[env:heltec_v4_repeater]` builds from this branch and `HeltecV4Board::canControlLoRaFemLna()`
returns true on a V4.3, so the bug was reachable from our source even though we publish no V4
binaries.

**Merged upstream 2026-08-12**, released in **1.17.1** as `23066573` (part of #3137), which also adds
`fem_txgain`. The 1.17.1 replant deduplicated our line to identical text exactly as the removal
condition foresaw — the only conflict was upstream's *additional* `fem_txgain` line, taken as-is.
Upstream separately disabled the equivalent load/save in `examples/companion_radio/NodePrefs.h`
(`890a2e2c`, `#if 0` "these cannot be set (yet)") and disabled its own round-trip test with it; that
is companion-side and does not affect this branch. Related issue #3145 is closed.

**The test stays.** `test/test_node_prefs_fem/` is fork-original and now guards mainline's own fix:
it passed against 1.17.1 in the replant run (42/42 native). Do not remove it — it is what would tell
us if a future mainline change re-aliased the binding.

---

### meshcore-dev/MeshCore#2797 — per-payload flood hop caps

Folded into the fork at `628b7689` (fwdfilter4) with its `atoi` off-by-one fixed. **Landed in
mainline 1.17** as `flood_max` / `flood_max_unscoped` / `flood_max_advert` with the same 64/64/8
defaults, so the 1.17 replant deduplicated it automatically — the fork copy and mainline's merged as
identical text. No longer carried.

The fork's own additional caps (`fwd.flood.max.request`, `.anon_request`, `.response`) live in
`/fwd_prefs` and are unrelated to #2797.
