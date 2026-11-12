# RIFT: the plan and its state

RIFT is the owner's second Digitone II firmware (named 2026-11-12): no MD or MNM machines,
"more complex versions of DT2 engines plus my new synthesis ideas with no compromises".
This repository is public; the bench (emulators, snapshots, goldens) is the private
De-Pattern/DN2-Rift-bench. Start from docs/HANDOFF-second-firmware.md for the background.

## Decisions (owner, 2026-11-12)

- **Reference sound: FASCIA pass 3**, the four-page, 32-control engine of the 2026-11-07
  tour (dn2mk2-firmware 9a6877e, goldens dn2mk2-bench f6972d6), not the 3-page v2.
- **Name RIFT**, its own Discord channel (RIFT ANNOUNCEMENTS); releases post there through
  the repository secret `DISCORD_WEBHOOK_URL` (set 2026-11-12).
- **Public repo, private bench.**
- **Order:** FASCIA first, released and tested; then the rest below.

## What is here (2026-11-12)

1. `52a5de4`: the infrastructure from dn2mk2-firmware e06993e (v0.51).
2. FASCIA: the engine (`src/dnfw/fascia/model.py`), its float32 DSP-order contract
   (`live.py`), the SHARC program bit-exact to it (`program.py`, from `fascia-saved`
   54e7843), pass 3's 30 audition patches (`scripts/fascia_audition.py`), and the goldens
   test (`test/test_fascia_golden.py`, within 2 LSB; the goldens come from the bench).

**Pass 3 and the DSP port are the same engine.** v2 only put a 24-control panel with macros
(`expand()`) in front of the approved 32-control engine. Fed pass 3's 32 controls directly
(`"_internal"`), the engine the DSP port was made from renders all 30 pass-3 goldens with
**0 LSB** of difference (checked 2026-11-12). So pass 3 needs no new DSP port, but:

- **The panel goes back to four pages of 8** (pass 3's SYN1 EXCITERS, SYN2 RESONATORS,
  SYN3 SPECTRAL, SYN4 ONSET/INTERACT). The ColdFire side (`fascia/machines.py`, 24 controls
  on WaveTone/FM Tone records) needs 32 places, and the DSP program's `expand` step goes.
- **FDBK and VARY must come back to life in the DSP program**: v2 fixed them
  (`VARY_INTERNAL = 40`, FDBK 0); pass-3 patches use them (16: VARY 110; 27: FDBK 40).
- **Open: 27_trade_bar_bell is 7 cents flat in live.py** against the model (pitch of the
  first partial; the check allows 5.1). `test_fascia_live` fails on it (1 of 182). It is
  the FDBK path v2 never exercised. Fix it, or measure it for the owner's ear; the check is
  not loosened.
- `test_fascia_program` needs the MD ROM: it reaches the DSP image builder, which imports
  every engine of the mod (next section).

## Next, in order

1. **Stand FASCIA on its own.** `waverider/dsp.py` (the DSP image), `waverider/pages.py`,
   `waverider/coldfire.py` and the ColdFire C (`csrc/waverider`) compose every engine of the
   mod. Make them compose stock + FASCIA only; then take the MD, MNM, sampler and older
   engines out, one gated commit each, each a clean removal.
2. **Measure** FASCIA alone on the SHARC runner (`fcost`): voices per frame, the guard's
   headroom unchanged. Report to the owner before any trimming.
3. **Integrate** (type 18, four pages, p-locks, LFO targets, slides, MACHINE SEL, presets,
   sound locks) and move the gate over: `ship_gate.py`'s steps for RIFT, the bench's
   `setup.sh` pinned to RIFT.
4. **The first release**: gated, its `releases/v0.1.md`, the flasher site, the announcement.
5. **The release machinery**: a new `releases/vX.Y.md` on main makes the GitHub release and
   posts it to RIFT ANNOUNCEMENTS (`.github/workflows/release.yml`); the browser flasher and
   sample import tool (from the DN2 mk2 patcher, site/) deploy to Pages with each release.

## After the first release (owner, 2026-11-12)

- **An FX slot for new effects**, studying the Overtone DN2 mod's way of adding effects
  (its source or docs needed), then **RESON**: the eight-band resonant filterbank /
  vocoder / ping engine from the Viscera (M-VAVE FM1) design, with its PARTICLES ideas
  (DUST first, then DROPLET, MIGRATE), ported to the SHARC as a DN2 effect.
- **A capicola stretch sample machine** (heavylight's algorithm; the owner has his
  permission), DT2-style but a single sample, with the Viscera "PUTTY" ideas (stretch,
  freeze, fragments, two buffers bounced) built into it.
- **A single FLEX machine.**
- **Stereo throughout** for both: stereo samples imported as one L/R sample, stereo
  resampling and recording, stereo all the way through the signal chain. This is the
  deepest change on the list (the DN2's voices are mono into the mixer); it is researched
  and costed before it is designed.
- **The same sample import tool** as the DN2 mk2 mod's.
