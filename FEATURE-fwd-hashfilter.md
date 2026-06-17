# Repeater forward filter for 1-byte path-hash traffic

**Status:** Stage 1 (stateless hash-size filter) + Stage 2 (pubkey policy table) implemented, build-verified. Hardware test pending.
**Branch:** `repeater-hash-filter` (off `dev`, clean mainline 1.16). **Target:** `RAK_4631_repeater` (nRF52840).
**Tracking:** local doc (no upstream issue yet — publish later).

## Problem

MeshCore path hashes are prefixes of a node's pub_key (`Identity.h`). 1-byte hashes give a 256-value
space; with 1000+ repeaters online they collide constantly, so a packet cannot be attributed to a
unique repeater, and **direct-route matching** (`Mesh.cpp` `isHashMatch`) can resolve to the wrong node.
The network is migrating to multibyte hashes, but many old repeaters/companions still emit 1-byte.

### Measured (CoreScope `logger-at.meshcore.observer`, 7-day window, 2026-06-16)
- 79.4% of all on-air packets still 1-byte (2B 16.7%, 3B 3.2%, 4B 0.7%).
- 2110 distinct advert pubkeys: 664 (31%) ever-multibyte (= confirmed modern); 1446 (69%) only-ever-1-byte,
  of which 1004 flagged as repeaters.
- Path hash size is set by the originator and preserved by modern relays, but old 1-byte-only repeaters
  re-emit modern adverts as 0-hop 1-byte copies (observed 40:1 for a known 3-byte node). So
  `getPathHashSize()==1` marks "1-byte-encoded flood", not "old originator" — but dropping 1-byte
  **adverts** is self-targeting: old nodes exist only as 1-byte (fully suppressed), modern nodes still
  propagate via their multibyte copy (only the redundant downgraded duplicate is trimmed).

### Why no region/scope awareness
Measured 2026-06-16 (7-day store): only **2.99%** of traffic is transport-scoped (TRANSPORT_FLOOD/DIRECT);
**97%** is unscoped FLOOD/DIRECT on the wildcard. So MeshCore's region system (`REGION_DENY_FLOOD`) can
only act on ~3% of packets, and a region-aware filter would miss the problem. This filter is deliberately
scope-independent — it acts in `allowPacketForward`/`filterRecvFloodPacket` on all floods. (script:
`reference/routetype.py` in the observer project)

Root cause is compliance, not the concept: regions require companions to send scoped, which they do NOT
by default, and users who don't engage with the topic never reconfigure. This is the same defaults
problem as 1-byte hashes — which is why repeater-side enforcement (acting on what arrives) is the
realistic lever, rather than relying on sender compliance.

## Design

Two complementary mechanisms, both default OFF, repeater builds only:

1. **Stateless hash-size filter** (Stage 1, this branch) — hook `allowPacketForward()`. Cheap, no state.
2. **Pubkey policy table** (Stage 2, planned) — hook `filterRecvFloodPacket()` (`Mesh.h`, called in
   `Mesh.cpp` before any `hasSeen()`, so dropping a copy doesn't mark it seen → a better-path copy can
   still win, beating the documented naive "first packet wins"). Enables flood path-steering by pruning
   branches through known-bad nodes. nRF52840 has only 256KB RAM → use short prefixes / few entries /
   flash-backed lookup, not a large RAM table.

## Stage 1 — implemented

CLI (admin):
- `set fwd.hashfilter off|advert|all` — off / adverts only / all flood+direct 1-byte traffic
- `set fwd.hashfilter.prob 0..100` — % chance to drop a matched 1-byte packet (100 = always; default 100)
- `get fwd.hashfilter` — echoes `mode prob=N`

Changes (all in `MeshCore-116`/this tree):
- `src/helpers/CommonCLI.h` — NodePrefs: `fwd_hashfilter_mode`, `fwd_hashfilter_prob`.
- `src/helpers/CommonCLI.cpp` — persist at /com_prefs offsets 293/294 (back-compat: defaults preserved
  if absent in older files), constrain, set + get handlers.
- `examples/simple_repeater/MyMesh.cpp` — `allowPacketForward()` block: drop 1-byte matches per mode+prob.

### Recommendation for deployment
Start with `set fwd.hashfilter advert` (+ optional `prob` < 100 to soften). Do NOT use `all` while ~75%
of the network is still 1-byte — it would drop most relayed traffic at an exposed linking node.
Measurement stays external (observer/CoreScope); no on-device counter in Stage 1.

## Stage 2 — implemented

Per-pubkey forward policy table (full 32-byte keys), max `FWD_BLOCK_MAX = 16` entries, persisted in
NodePrefs at /com_prefs offsets 295.. (count + 16×32 keys + 16 actions = 529 B; back-compat: empty if
absent). Two action flags:
- `FWD_BLOCK_PRUNE_PATH` (0x01) — hook `filterRecvFloodPacket`: drop any flood copy whose path contains
  this node. Called before `hasSeen()`, so the dropped copy is NOT marked seen → a copy via a different
  path can still win. This steers floods off bad branches (beats naive "first packet wins"). Path holds
  hash prefixes → reliable at multibyte sizes; 1-byte is covered by the Stage 1 hash-size filter.
- `FWD_BLOCK_DROP_ADVERT` (0x02) — hook `allowPacketForward`: don't forward adverts originated by this
  node (exact full-pubkey match against the advert payload), at any hash size.

CLI (admin):
- `set fwd.block.add <64-hex-pubkey> [prune|advert|both]` — default `prune`
- `set fwd.block.del <hex-or-prefix>` — removes all entries matching the prefix
- `set fwd.block.clear`
- `get fwd.block` — lists entries (6-byte prefix + flags P/A)

Changes: `CommonCLI.h` (FWD_BLOCK_* defines + table fields), `CommonCLI.cpp` (persist 295.., constrain,
3 set handlers + get), `simple_repeater/MyMesh.cpp` (prune in `filterRecvFloodPacket`, advert-drop in
`allowPacketForward`). Builds clean; RAM 13.8%, Flash 63.0%.

RAM note: 16-entry table = 529 B, trivial on the nRF52840's 256 KB. Raise `FWD_BLOCK_MAX` only modestly.

## Stage 3 — last-hop whitelist — implemented

An opt-in **last-hop whitelist** for an exposed bridge repeater: only relay a flood if its immediate
sender (the last path hop, appended by the relay that just handed it over) is on a curated allow-list
of trusted backbone neighbours. Default OFF, repeater builds only.

Locked design decisions:
- **Hook `filterRecvFloodPacket`** — runs before `hasSeen()`, so a whitelisted copy can still win even
  if a non-whitelisted copy arrived first. (`allowPacketForward` runs *after* `hasSeen()` → an earlier
  non-whitelisted copy marks the packet seen and would suppress relaying the whitelisted copy =
  first-packet-wins; wrong for a whitelist.)
- **Exemptions (prevent admin lockout):** adverts (`PAYLOAD_TYPE_ADVERT`, neighbour learning/discovery),
  `PAYLOAD_TYPE_ANON_REQ` (login/initial contact), and floods addressed to this node (dest_hash at
  `payload[0]` matches self) always pass.
- **0-hop floods** (empty path → originator not identifiable, not in path + encrypted): configurable
  `set fwd.whitelist.0hop allow|drop`, **default allow**.
- **Last-hop matched at the packet's hash size** (hash-size-independent). 1-byte is collision-prone
  (~W/256 leak); operator should also enable `fwd.hashfilter all` to drop 1-byte floods deterministically.

CLI (admin):
- `set fwd.whitelist on|off`
- `set fwd.whitelist.0hop allow|drop` (default allow)
- `set fwd.whitelist.add <64-hex-pubkey>`
- `set fwd.whitelist.del <hex-or-prefix>` — removes all entries matching the prefix
- `set fwd.whitelist.clear`
- `get fwd.whitelist` — echoes `mode 0hop=allow|drop N entries | <6-byte prefix>...`

Changes: `CommonCLI.h` (`FWD_WL_MAX=16` + table fields: mode, zerohop, count, 16×32 keys),
`CommonCLI.cpp` (persist /com_prefs offsets 824.. = mode+zerohop+count+16×32 keys ≈ 515 B; back-compat:
off/allow/empty if absent; constrain; set + get handlers), `simple_repeater/MyMesh.cpp`
(whitelist block in `filterRecvFloodPacket` with exemptions + 0-hop policy + last-hop match).

### Recommendation for deployment
Pair with `set fwd.hashfilter all` (drop collision-prone 1-byte floods) so only multibyte last-hops are
whitelist-matched. Build the allow-list from observed relay-adjacency / active TRACE link verification
(see `reference/kk_adjacency.py`, `trace_probe.py` in the observer project), NOT from `get neighbours`
(advert-only, RAM-only, incomplete). Strong verified backbone links go in; high-delay-but-strong bridges
(low relay frequency, high SNR) belong in too. 0-hop=allow for first deployment; switch to drop only once
the backbone path is confirmed working.

## Bench testing (devboard, no traffic volume needed)

Functional verification is about the forward/drop decision, not statistics — a handful of packets
suffices. Build the debug variant which enables serial packet logging + `MESH_DEBUG`, so each
drop/prune prints to the USB console:

    pio run -e RAK_4631_repeater_debug

This auto-generates `.pio/build/RAK_4631_repeater_debug/firmware.uf2` (post-build script
`variants/rak4631/gen_uf2.py`, family 0xADA52840). Flash by double-tapping reset on the RAK4631
(it mounts as a USB drive) and copying `firmware.uf2` onto it. Then over serial:
1. `set fwd.hashfilter advert` (or `all`) → watch for `fwd-filter: drop 1-byte advert ...` lines.
2. `set fwd.block.add <64-hex-pubkey> prune` then `get fwd.block` → on a matching multibyte flood,
   watch for `fwd-filter: prune flood via blocklisted node ...`.
3. `set fwd.block.add <64-hex-pubkey> advert` → watch for `fwd-filter: drop advert from blocklisted ...`.

Deterministic option (no ambient traffic): use a second node/companion to emit a known 1-byte vs
multibyte advert and confirm only the intended one is relayed. The drop logs are no-ops in the normal
`RAK_4631_repeater` build (compiled out unless `MESH_DEBUG`).

Impact measurement (how much network traffic changes) is separate and needs an exposed, high-throughput
node + CoreScope correlation — not reproducible on a low-traffic bench.

## Checklist
- [x] NodePrefs fields + persistence (Stage 1 offsets 293/294, Stage 2 295.., back-compat)
- [x] CLI set/get handlers (hashfilter + block table)
- [x] `allowPacketForward` filter (hash-size mode+prob, plus DROP_ADVERT)
- [x] `filterRecvFloodPacket` path-prune steering
- [x] Builds clean: `pio run -e RAK_4631_repeater` (+ `_debug` variant)
- [x] Debug build variant with drop/prune serial logging (`RAK_4631_repeater_debug`)
- [x] Bench smoke test on RAK4631 devboard: `all` mode dropped 2/2 received 1-byte packets (2026-06-16)
- [x] Deterministic 2-node test (Heltec companion_radio_usb sender + RAK4631 repeater, radio matched
      to EU-narrow 869.618/62.5/SF8/CR8): **4/4 PASS** (2026-06-16) — advert-mode drops 1-byte advert /
      forwards multibyte; Stage-2 `advert` blacklist drops the targeted pubkey / forwards after clear.
      Orchestrator: `reference/orchestrate_test.py`.
- [x] PRUNE_PATH (filterRecvFloodPacket steering) verified on HW (2026-06-16): blocked a known 3-byte
      bridge repeater with `prune`; ambient multibyte floods relayed through it were pruned — log
      `prune 2-byte flood via blocklisted hop XXXX (hop 9/10)` — and 0 prunes after clear. (Origin pubkey
      is never a path hop, so the controllable sender can't drive this; it's driven by ambient relayed
      traffic. RAK debug build now logs the matched hop bytes.)
- [x] Stage 3 last-hop whitelist: NodePrefs fields + persistence (offsets 824..), CLI set/get,
      `filterRecvFloodPacket` whitelist block with exemptions + 0-hop policy + last-hop match
- [x] Stage 3 build-verify (`pio run -e RAK_4631_repeater`, RAM 14.0% Flash 63.2%, + `_debug`)
- [x] Stage 3 2-node bench test: **10/10 PASS** (2026-06-17, `reference/stage3_test.py`). Verified on HW:
      CLI round-trip; persistence across reboot (offset 824); advert exemption (relays under whitelist
      on + 0hop=drop); 0-hop policy (`drop 0-hop flood` at 0hop=drop, none at allow — driven by a channel
      GRP_TXT flood, non-exempt 0-hop); last-hop match on ambient multi-hop floods (`drop N-byte flood,
      last-hop XX not whitelisted`, seen at both 1-byte `63` and 3-byte `63D13A`). Note: deterministic
      last-hop testing needs ambient relayed traffic (controllable sender's origin is never a path hop).
- [ ] Production deploy + CoreScope impact measurement
- [ ] Next build: add dedicated `get fwd.hashfilter.prob` for set/get symmetry (MeshCore CLI convention;
      the combined `get fwd.hashfilter` already reports prob, so this is convention-only, deferred from
      the fwdfilter1 release)
