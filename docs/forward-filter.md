# Repeater forward filter — operator manual

*🇩🇪 [Deutsche Fassung](./forward-filter.de.md) (primary) · 📻 [Flashing guide](./flashing-repeater.md)*

This manual documents **every** forward-filter feature of the ACETyr repeater firmware
(`repeater-v1.17.1.fwdfilterN`) in one place. It supersedes the per-release descriptions — from now on
the release notes only record *what changed*, this document describes *what the firmware does*.

---

## Read this first

**Every filter ships disabled.** A freshly flashed node behaves exactly like a stock MeshCore 1.17.0
repeater. Nothing happens until you switch something on yourself.

All filters act **locally on this one node** — there is no protocol change and no coordination with
other nodes. Mixed-firmware networks are fine, and so is a single filtered node in an otherwise
untouched network.

Everything is driven from the **admin CLI**: locally over USB, or remotely over the air (remote
management in the MeshCore app, admin login required). See
[CLI access](./flashing-repeater.md#cli-access).

---

## Command reference

| Command | Values | Default | Effect |
|---|---|---|---|
| `set fwd.hashfilter` | `off` · `advert` · `all` | `off` | Stop forwarding packets with a 1-byte path hash |
| `set fwd.hashfilter.prob` | `0`–`100` | `100` | Probability that a match is actually dropped |
| `set fwd.block.add` | `<64-hex> [prune\|advert\|both]` | action `prune` | Add a node to the policy table (max. 16) |
| `set fwd.block.del` | `<hex prefix>` | — | Remove all entries matching the prefix |
| `set fwd.block.clear` | — | — | Empty the policy table |
| `set fwd.whitelist` | `on` · `off` | `off` | Enforce the last-hop whitelist |
| `set fwd.whitelist.0hop` | `allow` · `drop` | `allow` | How to treat floods that have not taken a hop yet |
| `set fwd.whitelist.add` | `<64-hex>` | — | Add a node to the whitelist (max. 16) |
| `set fwd.whitelist.del` | `<hex prefix>` | — | Remove all entries matching the prefix |
| `set fwd.whitelist.clear` | — | — | Empty the whitelist |
| `set fwd.scoped.reserve` | `0`–`100` | `0` | Percent of the airtime allowance (60 s window) kept free for scoped traffic |
| `set fwd.chan.block` | `#name` · `Public` · `<32\|64-hex>` `[label]` | — | Add a channel to the blocklist (max. 16) |
| `set fwd.chan.unblock` | `#name` · `Public` · `<32\|64-hex>` · `<index>` | — | Remove one entry |
| `set fwd.chan.clear` | — | — | Empty the blocklist |
| `set flood.max.request` | `0`–`64` | `64` | Hop cap for flooded REQUEST packets |
| `set flood.max.anon.request` | `0`–`64` | `64` | Hop cap for flooded ANON_REQUEST packets |
| `set flood.max.response` | `0`–`64` | `64` | Hop cap for flooded RESPONSE packets |

Every `set` has a matching `get`:

| Command | Example output |
|---|---|
| `get fwd.hashfilter` | `> advert prob=75` |
| `get fwd.hashfilter.prob` | `> 75` |
| `get fwd.block` | `> 2 entries \| a1b2c3d4e5f6 P \| 9988776655ff PA` |
| `get fwd.whitelist` | `> on 0hop=allow 3 entries \| a1b2c3d4e5f6 \| …` |
| `get fwd.scoped.reserve` | `> 40` |
| `get fwd.scoped.stats` | `> reserve=40% fwd_scoped=812 fwd_unscoped=95 drop_unscoped=1043 saved_air=214500ms air=1180/6000ms/60s` |
| `get fwd.chan` | `> 3 entries \| 2F B2 9C` |
| `get fwd.chan <index>` | `> 1: #slovakia (B2)` |
| `get fwd.chan.stats` | `> blocked=1832 saved_air=856000ms` |
| `get flood.max.request` | `> 64` |

List output shows only the **6-byte prefix** of each pubkey; in `get fwd.block`, `P` = *prune* and
`A` = *advert*. Long lists are truncated in the display at roughly 140 characters — the entries
themselves stay active, only the output is cut short.

---

## Why this exists

Two problems that show up in large, long-running networks:

**1-byte path hashes.** The path hash is a prefix of the node pubkey. One byte leaves 256 possible
values — in a network with more than a few dozen nodes those collide by necessity. Such a hop can no
longer be attributed to a specific node, and direct-route matching can resolve ambiguously. The result
is relay traffic nobody can trace and paths that take a wrong turn.

**Unscoped floods.** An unconfigured node always transmits without a region code — that is the default
and legacy behaviour, and it is intentional for compatibility. In practice this traffic becomes the
majority in grown networks and crowds delivery between correctly configured repeaters out of the
airtime budget.

These filters give an operator tools against both — without a protocol change everyone would have to
adopt.

---

## Stage 1 — hash-size filter

Drops packets whose path hash is only one byte wide.

```
set fwd.hashfilter off      # off (default)
set fwd.hashfilter advert   # stop forwarding adverts with a 1-byte hash
set fwd.hashfilter all      # stop forwarding all 1-byte flood and direct traffic
```

`advert` is the gentle first step: adverts are the traffic that fills routing tables across the
network with ambiguous entries. `all` covers payload traffic as well.

The probability lets you dose the effect instead of switching hard:

```
set fwd.hashfilter.prob 100   # every match is dropped (default)
set fwd.hashfilter.prob 75    # three out of four matches are dropped
set fwd.hashfilter.prob 0     # nothing is dropped (filter effectively inert)
```

The probability applies to **all** matches of the selected mode, including adverts in `advert` mode. A
value below 100 is useful when you want to increase pressure on affected neighbours without cutting
them off entirely — their packets still get through, just less reliably.

---

## Stage 2 — per-pubkey policy table

A table of up to 16 nodes, each with one of three actions.

```
set fwd.block.add <64-hex-pubkey> prune    # path prune (default if no action given)
set fwd.block.add <64-hex-pubkey> advert   # do not forward this node's adverts
set fwd.block.add <64-hex-pubkey> both     # both of the above
```

**`prune`** drops flood copies whose path traversed the named node. The test runs **before**
duplicate suppression — a copy of the same packet arriving via a different path can still win. This
steers paths rather than destroying packets: "don't go via X, take the other route". It is only
reliable at multibyte hash sizes, because the path hop is otherwise ambiguous.

**`advert`** stops forwarding adverts originated by that node. This compares the full pubkey exactly,
so it works at any hash size.

Removing and inspecting:

```
set fwd.block.del a1b2c3d4      # prefix is enough, removes all matches -> "OK (1 removed)"
set fwd.block.clear             # empty the table
get fwd.block                   # show contents
```

Adding a pubkey that is already present replaces its action; no duplicate entry is created.

---

## Stage 3 — last-hop whitelist

The strictest filter: a flood is only forwarded if its **immediate sender** — the last hop in the path
— is on the allow list. Everything else is dropped.

```
set fwd.whitelist.add <64-hex-pubkey>   # add backbone neighbours (max. 16)
set fwd.whitelist.del a1b2c3d4          # prefix is enough
set fwd.whitelist.clear
get fwd.whitelist
set fwd.whitelist on|off                # enforcement (default: off)
set fwd.whitelist.0hop allow|drop       # default: allow
```

`0hop` covers floods that have not taken a hop yet, i.e. heard directly from the originator. There is
no "last hop" to check, so they need their own rule. The default `allow` keeps directly heard nodes
flowing.

**So you cannot lock yourself out**, three packet classes are always exempt from the whitelist:
adverts, `ANON_REQ`, and floods addressed to this node itself. Remote admin login therefore still
works even with a wrong whitelist.

The last hop is matched at the packet's hash size. With a 1-byte hash that means 256 possible values,
and any foreign node sharing the prefix passes the whitelist too. **This is why you enable
`fwd.hashfilter all` first** — the whitelist then matches at multibyte width and the comparison is
meaningful.

---

## Stage 4 — airtime reserve for scoped traffic

```
set fwd.scoped.reserve 0     # off (default)
set fwd.scoped.reserve 40    # keep 40 % of the airtime allowance free for scoped traffic
```

Keeps that percentage of **this node's transmit airtime** free for **scoped** (region-coded) flood
traffic. If the remaining allowance is no longer enough for another unscoped packet without eating
into the reserve, that packet is dropped; scoped floods and all direct traffic always pass regardless.

**The reference is a 60-second window, not the hourly budget.** The allowance per window follows
directly from the configured duty cycle:

```
allowance per window = 60 s × duty cycle
```

At `set dutycycle 10` that is 6000 ms per window, roughly twelve packets at the SF8 preset. A 40 %
reserve keeps 2400 ms of it free: unscoped floods are dropped once this node has transmitted enough
within the current window that the remainder no longer covers another unscoped packet.

> **Why not the duty-cycle budget itself?** Because nothing can be measured with it. The Dispatcher's
> token bucket runs over a full hour and carries roughly 360,000 ms of slack at a legal 10 %. A flood
> storm of twenty relays costs ~10,000 ms and disappears into it without trace. Measured on the bench:
> bucket at 359,325/360,000 ms (99.8 % full) while the node was relaying a busy mesh at 0.995 % actual
> duty against a 10 % limit. A percentage threshold on a permanently full bucket can only trip at
> 100 %. Up to and including `fwdfilter7` the setting was therefore effectively a switch: 0 = off,
> 100 = drop every unscoped flood, everything in between inert. The short window is the actual fix —
> not a different threshold.

Only this node's **transmit budget** is reserved, not the RF channel.

> **Since mainline 1.17.1 fewer replies go out un-scoped.** When a server cannot resolve the scope of
> a request — a DIRECT request carrying no transport code, for instance — 1.17.1 sends the reply on
> the server's own default scope instead of un-scoped. Before that it went out un-scoped, which made
> it a candidate for dropping on every repeater with a reserve set. The reserve therefore hits login
> and admin replies less often. Do not rely on it: it only applies when the *replying* node already
> runs 1.17.1 and has a default region configured — older nodes, and nodes without one, still reply
> un-scoped.

### Measured behaviour

Two runs under identical load (93 flood adverts each, `dutycycle 10`, so a 6000 ms allowance per
window):

| Reserve | forwarded | dropped | peak airtime in the window |
|---|---|---|---|
| `0` | 93 | 0 | **7733** / 6000 ms — 129 % |
| `50` | 24 | 69 | 2579 / 6000 ms — 43 % |

Without a reserve this load overruns the window allowance by 29 %. At a 50 % reserve the node
forwards the first packets and then holds airtime flat at 2577–2579 ms, across all seven sample
points.

So the reserve **does not switch off, it settles.** At the holding point 3423 ms were still available
against a threshold of 2400 ms reserve plus roughly 500 ms for the next packet — the node leaves
about 57 % of the allowance free against a 50 % reserve rather than tipping over at a fixed line. How
much actually gets through therefore depends on the load, not on the configured value alone.

> **Set this carefully at very low duty cycles.** The allowance shrinks with the duty cycle, but a
> single packet is still ~500 ms. At `set dutycycle 1` only 600 ms per window is available — one
> packet nearly fills the whole allowance, and any reserve above 0 will then drop practically every
> unscoped flood regardless of load. Arithmetically correct, but rarely what you want.

Checking the effect:

```
get fwd.scoped.stats
> reserve=40% fwd_scoped=812 fwd_unscoped=95 drop_unscoped=1043 saved_air=214500ms air=1180/6000ms/60s
```

- `fwd_scoped` / `fwd_unscoped` — forwarded floods, split by scope
- `drop_unscoped` — floods dropped by the reserve
- `saved_air` — airtime saved as a result, in milliseconds
- `air` — transmit airtime used in the current window / allowance / window length. This is the gate's
  input: if the first value sits well below the second, the reserve does not engage, whatever it is
  set to

The counters count the **forwarding decision**, not confirmed transmission. They live in RAM and
**reset to 0 on every reboot** — deliberately, since a per-packet counter in flash would wear out the
nRF52. For long-term statistics, poll the value externally and keep summing; a reboot simply looks
like a counter reset.

---

## Stage 5 — channel blocklist

```
set fwd.chan.block #austria       # block a channel by its name
set fwd.chan.block Public         # the built-in default channel
set fwd.chan.block <32|64-hex>    # block a channel by its key
set fwd.chan.unblock #austria     # undo -- also by index or by key
set fwd.chan.clear                # empty the blocklist
```

Drops flooded **group messages** (`GRP_TXT`, `GRP_DATA`) belonging to a channel you listed. Nothing
else is touched: direct messages, adverts, requests, and group messages on every channel you did not
list all pass as before.

In the figures below, **21 % of flood airtime** is group messages — the second largest item after
adverts.

> **Where the numbers come from, and what they are not.** Every measured figure in this section comes
> from one 24-hour capture (2026-08-17) by the logger-at observer network, whose nodes sit mostly in
> Austria and pick up traffic from across central Europe. That is a
> **snapshot of a slice**, not a property of the network: another week, another region or another
> site will give different values. The numbers show the order of magnitude and explain why this stage
> exists — what is actually going on at **your** site is something `get fwd.chan.stats` tells you
> once you have listed something.

### Why not just match the hash byte

A group packet identifies its channel by **one single byte**, a truncated hash of the channel key. In
the captured traffic **244 of the 256 values were in use**. Filtering on that byte necessarily catches
unrelated channels, and the protocol offers nothing longer.

How badly depends on the byte, and you cannot tell in advance. From the same capture:

| byte | share that really is the channel you meant |
|---|---|
| `0xD9` (`#test`) | 96 % |
| `0xDD` (`#vienna`) | 77 % |
| `0xB3` (`#hamradio`) | 43 % |
| `0x98` (`#yo`) | 1 % |

On `#yo`, a hash-byte filter would drop **99 % other people's traffic** and 1 % of what you aimed at.
Without the key the two cases cannot be told apart — which is why this stage works differently.

### The node recognises the channel without being able to read it

Instead of comparing the hash byte, you store the **channel key**. Every group packet carries a
2-byte message authentication code (MAC) computed under exactly that key over the encrypted text. If
it verifies, the packet belongs to that channel — not probably, but demonstrably.

The filter verifies that code **and stops there**. It decrypts nothing. In the firmware's receive
path the same check is followed by a `decrypt()`; on the filter path that call does not exist, and
that is checkable in the source (`src/helpers/ChannelFilter.h`). A repeater can therefore name the
channel it drops while remaining unable to read a single message.

Worked through on the captured traffic: byte `0xD9` carried 2130 packets, 2048 of them `#test` and 82
belonging to other channels. The `#test` key recognised all 2048 and let all 82 through. A hash-byte
filter would have dropped all 2130.

Cross-checked over the air on the bench with two purpose-built channels sharing one hash byte: the
listed one was dropped, the other forwarded in the same second.

### Adding channels

**By name** — for the public hashtag channels the apps offer:

```
set fwd.chan.block #austria
> OK (hash FB)
```

The node derives the key from the name exactly as the clients do. The name is taken **literally**:
`#ping` matches, while `ping`, `#Ping` and `#PING` match nothing. The `#` is part of it.

**The default channel** is simply called `Public`. It has no `#…` name, it has a fixed key, and the
built-in name is there so that nobody has to type that key out:

```
set fwd.chan.block Public
> OK (hash 11)
```

**By key** — for everything else, 32 or 64 hex characters, with an optional label:

```
set fwd.chan.block 4f2b… MyChannel
> OK (hash 7A)
```

**Viewing.** The list shows hash bytes only, so that a full table still fits in one reply over the
air; details come one entry at a time:

```
get fwd.chan
> 3 entries | 2F B2 9C

get fwd.chan 1
> 1: #slovakia (B2)
```

**Removing** works by name, by key or by index:

```
set fwd.chan.unblock 1
> OK (1 removed)
```

### What is behind a hash byte?

The node cannot answer that — a hash does not run backwards, and the node knows only the channels you
entered yourself. It only has to be answered once, before you decide what to block.

At your own site you usually know which channels are in use: enter the names, read `get fwd.chan`,
done. Where that is not enough, do it on a computer: collect candidate names, derive the key from
each, and MAC-verify it against real packets. That is certainty rather than a guess among 256
possibilities — the same mechanism the filter itself uses. A ready-made tool is in the project at
`reference/corescope_channel_profile.py --identify`.

### The most obvious case: channels with no connection to the region

The capture contains **ten channels** whose names point somewhere else — `#hungary`, `#slovakia`,
`#kosice`, `#switzerland`, `#polska`, `#turiec`, `#poland`, `#yo`, `#australia` and `#slovenia`,
together **4.8 % of group airtime**. Their packets were on the air and were being passed along.

Whether anyone at **your** site reads one of them is something only you know. That is exactly the
point: for these channels the question usually has a clear answer, and for a busy local channel it
does not — blocking one is an operator's decision that affects other users of the same repeater. The
firmware does not make it for you and makes none on its own.

### Checking the effect

```
get fwd.chan.stats
> blocked=1832 saved_air=856000ms
```

- `blocked` — group packets dropped
- `saved_air` — airtime saved by those drops, in milliseconds

Like the other counters, both live in RAM and **go back to 0 on every restart**.

### Cost

The check costs CPU time, but only for packets whose hash byte matches an entry at all — everything
else is done after one byte comparison. Measured, on a match:

| | per check |
|---|---|
| RAK4631 (nRF52840, crypto hardware) | **210 µs** |
| Heltec V3 (ESP32-S3, software) | **482 µs** |

Against the ~470 ms the same packet occupies on air, that is **0.1 %**. With an empty blocklist the
check does not run at all.

### What the node stores

**A repeater holds no channel keys — other than the ones you enter yourself.** A stock repeater has
joined no channel and holds none. Only `set fwd.chan.block` puts a key into `/fwd_prefs`.

And it is the **whole** key, including when you enter a `#name` and the node derives it for itself.
There is no half key to store: the same key that verifies the MAC also decrypts
(`Utils::MACThenDecrypt` hands it to both steps). Anyone who can verify can in principle read — the
fact that *this* firmware does not is a property of the code, not of the key.

So the question is never *whether* a whole key sits on the device, but **whether that key is a
secret.**

In the two ordinary cases that has no consequence:

- **`#name` channels** — the key is the hash of the name. Anyone who knows the name can derive it, so
  the node carries nothing an attacker did not already have.
- **The `Public` channel** — its PSK is published in the firmware source and in
  [the FAQ](./faq.md), and every companion in the mesh ships with it. Also no secret.

Only if you enter the PSK of a **genuinely private** channel does a real secret end up on the device
— and a device on a mast can be taken down and read out. That key is the same one the channel can be
read with; the fact that *this* firmware does not decrypt protects nothing against someone holding
the hardware.

That case is rare and mostly unwanted anyway: you can only block a private channel if you are a
member of it, and then you would usually rather relay its traffic than drop it. **Recommendation: use
this stage for public channels**, and enter a private key only after a deliberate judgement about one
specific device in one specific place.

---

## Per-payload flood hop caps

```
set flood.max.request 64        # REQUEST      (default 64)
set flood.max.anon.request 64   # ANON_REQUEST (default 64)
set flood.max.response 64       # RESPONSE     (default 64)
```

Caps how far flooded packets of these types may travel. The default of 64 is the maximum and therefore
a no-op. These are meant against misconfigured automation traffic that crosses the entire network when
it should stay local.

> ⚠️ **Leave these at 64 on backbone high sites.** RF admin login rides on
> `ANON_REQUEST`/`RESPONSE`. Setting these too low on a remote node cuts exactly the traffic you would
> need to reach it again.

(These three settings come from mainline PR #2797 and are not part of the forward filter proper, but
they are stored in the same `/fwd_prefs` file and driven from the same CLI.)

---

## Common configurations

**"I just want to observe for now."**
Do nothing. The shipped state does not filter. Polling `get fwd.scoped.stats` gives you the
scoped/unscoped split at your site even with every filter off.

**"Make the 1-byte adverts stop."**
```
set fwd.hashfilter advert
```
The usual first step. Adverts only; payload traffic is untouched.

**"One specific node is flooding me."**
```
set fwd.block.add <pubkey> both
get fwd.block
```

**"The path via node X is bad, I want the other one."**
```
set fwd.block.add <pubkey-of-X> prune
```
No data loss — copies via other paths still win.

**"My backbone node should only relay for the backbone."**
See [Safe deployment](#safe-deployment) — this is the case where the order matters.

**"Unscoped traffic is eating my airtime."**
```
set fwd.scoped.reserve 40
```
Check `get fwd.scoped.stats` after a few hours and adjust, watching `air=` to see whether the node
ever gets near its allowance at all. 100 drops unscoped floods as soon as there
is any budget pressure at all.

**"I am relaying channels nobody here listens to."**
```
set fwd.chan.block #hungary
set fwd.chan.block #polska
get fwd.chan
```
The uncontroversial case. Write down first which channels are actually read at your site — the rest
is your candidate list. Check `get fwd.chan.stats` after a day: if `blocked` is still 0, that channel
was not passing through here anyway and the entry can go.

---

## Safe deployment

For the whitelist (stage 3) — the only filter that can functionally remove a node from the network.
**Nothing is enforced until step 4**; steps 1–3 only populate and verify and are safe to run on a live
node.

1. **Identify the real backbone neighbours** — from active relay adjacency or TRACE, **not** from the
   device's neighbour table. That lists nodes you *hear*, not the ones that actually relay your
   traffic. This is the most common mistake here.

2. **With the whitelist still off**, add each confirmed pubkey:
   ```
   set fwd.whitelist.add <64hex>
   ```
   This only fills the table; forwarding is unchanged.

3. **Verify the table** — `get fwd.whitelist`. Is it exactly what you expect?

4. **Only now enable enforcement**, in this order:
   ```
   set fwd.hashfilter all
   set fwd.whitelist on
   ```
   Hash filter first, so the whitelist matches at multibyte width instead of collision-prone 1-byte.
   Leave `0hop allow` (the default) until you have confirmed the backbone still relays through this
   node.

**Rollback — at any time:**
```
set fwd.whitelist off
set fwd.hashfilter off
```

> ⚠️ **Careful with remote and masthead nodes.** With the whitelist active the node stops relaying for
> any non-whitelisted last hop. Admin *login* still works (adverts and `ANON_REQ` are always exempt),
> but multi-hop paths **through** this node to nodes beyond it break if the whitelist is incomplete.
> Before step 4 on a site with no backhaul, make sure you have a way back: local USB/BLE access, or a
> node you can still reach.

---

## Where the settings live

All `fwd.*` and `flood.max.*` settings are stored in a dedicated file **`/fwd_prefs`** on the node's
filesystem, in a self-describing TLV format. The mainline settings live entirely separately in their
own file — since 1.17 that is `/prefs.json`, before it was the `/com_prefs` blob.

That is not cosmetic. If the filter fields were written into the mainline file, a mainline merge that
inserts a field there could shift offsets — and then radio or region settings get silently reinterpreted
as filter values. Keeping them separate makes that impossible by construction. The change of the
mainline format from `/com_prefs` to `/prefs.json` in 1.17 is exactly that case: `/fwd_prefs` was
unaffected.

Practical consequences:

- **Switching between fork and mainline firmware** only loses the filter configuration. Radio, region
  and identity settings survive.
- **Older firmware reading a newer `/fwd_prefs`** ignores unknown fields. A missing field means its
  default — i.e. "off".
- **Upgrading from fwdfilter3 to fwdfilter4 or newer** resets the filter configuration once (the move
  from `/com_prefs` to `/fwd_prefs`). Re-add whitelist and blacklist entries afterwards. Radio and
  region settings are preserved. From fwdfilter4 onward the configuration survives every upgrade.
- **Upgrading to fwdfilter8** migrates the *mainline* settings once, from `/com_prefs` to
  `/prefs.json`. The filter configuration is unaffected, but going back to older firmware has
  consequences — see
  [Downgrading from fwdfilter8](./flashing-repeater.md#downgrading-from-fwdfilter8).

---

## Version history

| Version | Date | What it added |
|---|---|---|
| `fwdfilter1` | 2026-06-16 | Stage 1 (hash-size filter) + stage 2 (policy table) |
| `fwdfilter2` | 2026-06-17 | Stage 3 (last-hop whitelist) — **superseded, do not use** |
| `fwdfilter3` | 2026-06-17 | Fix: reply-buffer overflow in `get fwd.whitelist`/`fwd.block` over RF |
| `fwdfilter4` | 2026-06-20 | Dedicated `/fwd_prefs` file · replanted on mainline · `flood.max.*` · `get fwd.hashfilter.prob` |
| `fwdfilter5` | 2026-06-21 | New build target SenseCAP Solar Node P1 (no functional change) |
| `fwdfilter6` | 2026-07-10 | Stage 4 (`fwd.scoped.reserve`) + `get fwd.scoped.stats` |
| `fwdfilter7` | 2026-07-13 | Fix: airtime estimate guarded against error codes · version string gained a leading `v` |
| `fwdfilter8` | 2026-08-10 | Rebased onto MeshCore 1.17.0 · Fix: stage 4 measures over a 60 s window instead of the hour bucket (1–99 was previously inert) · Fix: noise-floor estimator could latch at −120 · Fix: the guarded airtime estimate aborted in-flight transmits |
| `fwdfilter9` | 2026-08-16 | Rebased onto MeshCore 1.17.1 · carried noise-floor fix brought up to date (no change to any `fwd.*` command) |
| `fwdfilter10` | 2026-08-17 | Stage 5 (`fwd.chan.block`) + `get fwd.chan` / `get fwd.chan.stats` · build target Seeed XIAO nRF52840 + Wio-SX1262 added on 2026-10-10 (same firmware, no new version) |

**Recommendation: always run the newest release.** Every older one carries at least one of the bugs
fixed above.

---

## Limits and known caveats

- **16 entries each** for the whitelist, the policy table and the channel blocklist. Enough for backbone adjacencies, not for
  network-wide lists.
- **List output is truncated.** `get fwd.whitelist`/`get fwd.block` will not show every entry on a full
  table. The entries are still active.
- **Statistics counters are volatile** (see stage 4) and count the forwarding decision, not confirmed
  transmission.
- **The airtime window is a fixed 60 seconds**, not a setting. The length is a trade-off: short
  enough that a flood storm becomes visible, long enough that single packets do not dominate the
  result. It is not a measured optimum.
- **The window is tumbling, not sliding.** A burst arriving just after a window rolls over gets the
  full allowance — the reserve damps sustained load, not every individual peak.
- **The load measurement above used flood adverts.** Under mixed real traffic — larger payloads,
  different airtime per packet — the behaviour is inferred, not measured.
- **Path prune is unreliable at 1-byte hashes**, because the path hop is ambiguous. Reliable at
  multibyte hash sizes.
- **The channel blocklist only acts on flooded group packets.** Group traffic sent as a direct packet
  passes. In the measurement that was 3 packets out of 13 820, so the exception costs practically
  nothing and keeps the intervention narrow.
- **A channel whose key you do not have cannot be blocked selectively.** That is the point rather than
  an oversight: without the key there is only the hash byte, and that catches unrelated channels.
- **A false match is arithmetically possible**, at roughly 1 in 65 536 per configured channel per
  packet — the code is 2 bytes long. With a handful of entries this has no practical meaning, and it
  is orders of magnitude better than filtering on a single hash byte.

Please report bugs and feedback as an [issue](https://github.com/ACETyr/MeshCore/issues).
