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

## Checklist
- [x] NodePrefs fields + persistence (Stage 1 offsets 293/294, Stage 2 295.., back-compat)
- [x] CLI set/get handlers (hashfilter + block table)
- [x] `allowPacketForward` filter (hash-size mode+prob, plus DROP_ADVERT)
- [x] `filterRecvFloodPacket` path-prune steering
- [x] Builds clean: `pio run -e RAK_4631_repeater`
- [ ] On-hardware smoke test (set modes, confirm via `get`, observe effect in CoreScope)
