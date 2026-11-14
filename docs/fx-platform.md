# The FX insert platform: design

**Status (2026-11-13): design and reference models; no firmware yet.** RIFT's roadmap item 1
(`docs/rift-roadmap.md`). An insert effect per track, with its own controls, chosen per sound
and p-lockable, on every machine (stock and ours). Not a filter type (owner, 2026-11-13: "this
would be an actual filter and we are not implementing fx that way this time"): the filter stays
what it is, and the insert sits beside it.

Every piece below is built to come out with one constant (`fx.platform.ON`) and is gated like
everything else. The sound of each effect goes to the owner's ear as a reference model and
audition WAVs first (`src/dnfw/fx/`, `scripts/fx_audition.py`); a bit-exact DSP port follows
the verdict, as FASCIA and PING were made.

## 1. Where the insert runs on the DSP

The engine task renders one block per frame (about 666,667 cycles on the unit; stock idles
63-65 % of it, `docs/dsp-time.md`). Inside the block:

    machine dispatch (sw 0x1c8ef1): every voice's machine renders into its voice buffer
      -> sw 0x1c9448: JUMP into our chain   (PERC head -> sample machines -> FASCIA -> tail)
      -> our tail (PING_SW 0x170280): register restore, two stock instructions, JUMP 0x1c944c
      -> the stock per-voice chain: filter (record +0x1dc's type), amp, pan, sends, mix

**The insert stage goes in our tail, before the JUMP back.** At that point every voice's
buffer is complete (stock machines and ours) and none has reached the filter: the PRE FLTR
position of Overtone's design. This is exactly where PING, SHFT and GRAN ran in the DN2 mk2
mod (v0.10-v0.44, on the instrument), so the position is proven on hardware; only their
selector (the filter type) changes, to the insert's own control.

- **Per voice, mono.** The DSP's blocks are per voice (`docs/lfo4-build-plan.md`, "the
  engine's index is a VOICE"): a track playing a chord runs one insert instance per sounding
  voice, each with its own state, as PING did. A voice's insert state is cleared when its
  voice starts a new note on another track (the same rule as the machines' state, keyed by
  `mnm_ages`' voice order).
- **POST FLTR** (after the stock filter and amp) needs a second hook inside the stock
  per-voice chain, not yet found. It is researched after the first effect ships; PRE FLTR
  alone covers RESON, the resonator, the shifter and the pitch effect.
- **Stereo** inserts (Overtone takes two voices per note) wait for RIFT's stereo work
  (roadmap §5): the voice chain is mono into the stock pan.

## 2. The guard and the cost

The insert runs inside the guard's frame (`perc/guard.py`): each instance's cost is measured
like a machine voice's and the guard skips an insert (passes the voice dry, never silent)
when it would overrun. Sample voices still get their time first. Budgets measured on the
SHARC runner's memory clock, before shipping, per effect; targets, per voice per block:

| effect | work per sample | target |
|---|---|---|
| RESON | 8 bands x 2 biquads, envelopes every 4th sample | under FASCIA's median (about 70,000 cycles) |
| RESONATOR (P-6) | up to 6 Karplus-Strong lines, one-pole damping | under 25,000 |
| WARP (shifter) | 2 x 6-pole allpass Hilbert pairs, one quadrature oscillator | under 15,000 |
| CHRONO (pitch) | 2 grains from a 100 ms delay line, 2 one-poles | under 10,000 |

## 3. The controls

### What the panel shows

Overtone's layout, which the owner pointed to:

- **FX page 1** gains two places: **M.SEL** (the insert: OFF, RESON, RSNTR, WARP, CHRONO) and
  **MIX** (dry/wet). Both p-lockable, so one trig can switch the effect.
- **An INSERT page** (FX pressed again): the chosen insert's own eight controls, named for it
  (as FASCIA's pages are named per machine by `wr_names`).

### Where the values live

A sound's value array has no room: its 101 mirror slots are all used by some machine except
65 and 100 (`docs/lfo4-feasibility.md`). Two routes exist in this code base, both proven:

1. **LFO4's side table** (`csrc/lfo4/ext.c`, `carry.c`, `store.c`): eight u16 values per live
   sound, keyed by the sound's address, carried through every copy, saved in the stored
   sound's spare bytes (ids 4..32, which stock save never writes), on the instrument since
   2026-09 ("unsaved LFO4 edits survive a power-cycle"). Parameter ids above 100 reach it
   through the setter's divert (`slots.h`). This is the store for the insert's ten values
   (M.SEL, MIX, eight controls): `EXT_PARAMS` grows from 8 to 10, the ids 101..110.
   **Integration cost:** lfo4 and waverider both write `slot_to_id` (2 bytes at
   `0x400dce86`, `docs/mods-compatibility.md`), and lfo4 relocates the parameter table; the
   two are merged in RIFT's waverider rather than applied as two mods.
2. **P-locks** of ids 101..110 ride the pattern's stock lock pool as extended records, the
   route the arp p-locks and the slides proved (stored ids 200+, `docs/lock-id-table.md`;
   stock firmware drops them on load, nothing else changes).

A sound saved with an insert and opened on stock firmware (or the DN2 mk2 mod) plays dry.

### How the values reach the DSP

The DSP reads machine values from the frame (2,688 bytes a block, 146 bytes a track); the
insert's ten values are not in it. They ride the ColdFire-DSP sample link (`link.c`, TDM
slots 8..15, about 1.1 MB/s, `docs/link-research.md`), which already carries the recorder's
per-frame commands: 16 tracks x 10 values x 2 bytes = 320 bytes, sent only when one changed.
The DSP keeps them per track and reads them at the insert stage. LFO modulation of an
insert control is applied on the ColdFire before the send (LFO4's evaluator does the same).

## 4. The gate

- SHARC runner: `insert` (off: every voice's buffer and the stock types 0-4 bit-identical to a
  build without it; on: each effect bit-exact to its float32 live model on fixed inputs),
  `istress` (the stress scenarios with an insert on every track: the guard holds the frame,
  sample voices first, no voice silent), `igarbage` (random state and values: bounded output,
  no NaN reaches the filter).
- ColdFire: `insert` (M.SEL and MIX on FX page 1, the INSERT page's names per effect,
  p-locks, a save/load round trip, a sound copy carrying its values, a stock-saved sound
  playing dry).
- Negative controls: a build with a broken send (values never arrive) and one with a
  deliberately wrong coefficient must fail.

## 5. Order of work

1. Reference models and auditions (this commit): RESON (ported from Viscera's
   `vsc_engine.c`), RESONATOR (P-6), WARP (Tonverk Frequency Warper), CHRONO (Tonverk Chrono
   Pitch). The owner listens.
2. The DSP stage with a pass-through and a gain test effect, gated (sound-neutral when off).
3. The ColdFire store and pages (the LFO4 merge), the link's insert words.
4. Each approved effect's float32 live model and its bit-exact SHARC port, one at a time.
