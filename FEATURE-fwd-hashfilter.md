# Repeater forward filter for 1-byte path-hash traffic

**Status:** Stage 1 implemented (stateless hash-size filter). Stage 2 (pubkey policy table) planned.
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

## Checklist
- [x] NodePrefs fields + persistence (offsets 293/294, back-compat)
- [x] CLI set/get handlers
- [x] `allowPacketForward` filter (mode + probability)
- [x] Builds clean: `pio run -e RAK_4631_repeater`
- [ ] On-hardware smoke test (set advert mode, confirm via `get`, observe drop in CoreScope)
- [ ] Stage 2: pubkey policy table + `filterRecvFloodPacket` steering
