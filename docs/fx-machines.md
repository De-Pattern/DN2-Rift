# FX machines: design (RIFT, after v0.16)

**Owner, 2026-11-21:** "lets speed this up ... so we can get to my nebulae granular engine and start
doing fx machines"; the first effect is "based on the PLATEAU reverb for vcv rack" (Valley's Plateau,
4ms' Mesa, the Versio port, all built on Dattorro's 1997 plate).

An FX machine is a **track type** (as FLEX is a sample machine): the tracks you choose feed it, it
plays the effect, and its output is the track's voice, so the track's own filter, amp, pan, sends,
LFOs, mutes and p-locks all work on the effect as they do on any machine.

## 1. The first effect: PLATEAU

`src/dnfw/fx/plateau.py` (the reference model), `scripts/plateau_audition.py` (the auditions).

- **The network:** Dattorro, "Effect Design, Part 1", Fig. 1 and Tables 1-2: predelay, input
  bandwidth, four input allpasses (142, 107, 379, 277 at 29,761 Hz), the figure-eight tank (two
  modulated allpasses 672 and 908, delays 4453/3720 and 4217/3163, damping, decay allpasses 1800 and
  2656) and Table 2's fourteen output taps. Scaled to 48 kHz and by SIZE.
- **On top, after Plateau's panel:** SIZE, DIFFUSION (0: the echoes heard), input LOW/HIGH CUT, tank
  LOW/HIGH CUT (damping), modulation SPEED/DEPTH, HOLD (freeze: the input closed, the decay 1), CLEAR,
  TUNED (the tank's loop at the note's period: the reverb played as a resonator, the FX track's notes
  setting the pitch).
- **Plateau's code is not used** (ValleyRackFree's licence): ours is written from the paper, as
  fm1-piano and digi_macro were read for ideas only.
- **Its pages (proposed):**
  - FX1: PRED SIZE DCAY DIFF / DAMP BAND MIX LEV
  - FX2: LOCT TLOW MSPD MDEP / HOLD TUNE CLR SRC

## 2. How tracks feed it

**Decided (owner, 2026-11-21): route A; a source keeps its own dry output** (a send: its level down
for 100 % wet). Stereo (route B) can follow.

**The bus matrix (owner, 2026-11-21: "route multiple tracks into this track via a bus matrix, which
we did mockup for the initial flex track but never used").** FLEX's 2026-11-09 design
(dn2mk2-firmware e6f441a, `docs/flex-mockups/flex-screens-b.png`, "T08 FLEX: REC BUS"), now the FX
track's **BUS** page:

- Two rows of eight numbered cells, the sixteen tracks. **[TRIG n] toggles track n**: a selected
  cell is drawn filled (as a p-lock is highlighted) and its key's LED lit.
- **The FX track itself, every other FX track and every FLEX track are out by default**, drawn
  struck (the mockup's FLEX cell), so no effect feeds itself or another; pressed in deliberately.
- **What is summed: each track's own block**, the one the recorder's TRK1..16 and Overbridge read
  (`SM.TRK_BUF + 0x100 t`, L at +0, R at +0x80: the track's audio after its own filter, amp and pan,
  the block before). Each track's LEVEL is applied in the bus by the ColdFire's word, so the balance is
  as heard. This replaces section 6's open question: the DSP already keeps one block per **track**,
  so no voice-to-track mapping is needed.
- Stored per FX track and pattern (with its other settings); the mask rides the sample link as the
  recorder's words do.
- The cost: one multiply-add a sample a selected track, at most sixteen.
- Later, the same matrix as FLEX's SRC **BUS** (record the sum), as first designed.


What is known (docs/fx-platform.md §1): RIFT's chain runs inside the engine's block after every
voice's machine has rendered and before the stock per-voice chain (filter, amp, pan, sends, mix).
There, every voice's buffer is complete and none has been filtered. The FX machine's voice can be
filled there from the other voices' buffers.

| route | what you hear | cost to build | limits |
|---|---|---|---|
| **A. pre-filter bus (proposed first)** | the chosen tracks' raw machine output, summed, into the FX track; its output through the FX track's own filter/amp/pan | small: our tail already holds every buffer | mono into stock's pan (the reverb's two outputs summed, or L only); the sources' own filters are not in the send |
| B. stereo pair | as A, the FX on two tracks (L and R), panned hard | A plus a pairing rule | costs two tracks |
| C. a main-mix insert | the whole mix (or the sends' bus) through the effect | needs a hook after stock's mix (not yet found; the recorder's MAIN tap reads there) | not a track: no p-locks or LFOs |

The sources: a track mask on the FX track's page 2 (SRC: the sixteen trig keys, as FLEX's source),
and each source's level into the bus is its own track level (so a source can be "send only" with its
own output muted).

The FX track sounds while it has a note: TRIG it (a held note, a long trig or KEYBOARD HOLD) and the
effect runs; the note's pitch is TUNED mode's pitch.

**Mono (owner, 2026-11-21: "lets keep it mono").** The FX track's output is its own voice's mono
block, through its own filter, amp, pan, sends and LEVEL like any machine. A stereo output (the
effect's L and R added into the main mix where MON adds the input, the track's chain bypassed) was
weighed and set aside.

## 3. What it costs

- **Memory:** the tank and input lines at SIZE 1.0 are about 36,000 samples (145 KB in float32,
  72 KB in 16-bit). They go in DDR, as SMEAR's lanes and THOLET's ring do. One PLATEAU instance (one
  FX track) at first.
- **DSP code:** v0.16 leaves about 4.9 KB of the 1 MiB upload. PLATEAU's block loop is estimated at
  1.5 to 2 KB; the FX machine's glue (the bus, the mask) under 1 KB. **Room is freed first:** more of
  the power-on tables onto the sample link (as v0.16 did for ORGAN, THOLET and SMEAR), or FASCIA's
  code trimmed.
- **CPU:** per sample about 30 delay reads and writes and 10 one-pole filters: well under one FASCIA
  voice. It runs inside the guard's frame like every machine.
- **ColdFire image:** 998 bytes left after v0.16's logos. The FX machine (a MACHINE SEL row, its
  pages, the BUS page's cells and [TRIG] keys) needs more, so room is freed first: the page
  renderer's chunk (`csrc/waverider/page.c` and what it links, 203 KB) still carries code for
  machines RIFT no longer offers (Waverider's wave spans, PERC's and the Monomachine's leftovers);
  each is measured (the linked map's symbol sizes) and stubbed under `WR_RIFT` as `md_page.c` was.

## 4. The gate (as every engine)

- Reference model -> the owner's ear (auditions) -> a float32 `live` model -> the SHARC program,
  bit-exact to it (`test_plateau_program`), runner parts `plateau` (bit-exact, a negative control: a
  wrong tap fails), `pstress` (with sixteen FASCIA voices under the guard: the frame holds), `pgarbage`
  (random state: bounded, no NaN reaches the filter).
- ColdFire: `fxmachine` (MACHINE SEL lists it; its pages; SRC; p-locks; SAVE/LOAD keeps it).
- Types 0-4 bit-identical to stock whenever no FX track sounds.

## 5. Next effects

WARP (the Tonverk's Frequency Warper) and CHRONO (Chrono Pitch), whose reference models exist
(`src/dnfw/fx/warp.py`, `chrono.py`), then the rest of docs/fx-platform.md's list.

## 6. Open, to research before the DSP work

- ~~Which voice is whose track~~: settled by the per-track blocks (`SM.TRK_BUF`, section 2).
- **The FX track's own voice.** It must hold a voice while the effect rings (a note that does not
  end, or the track kept "sounding" while its tail is above silence), and that voice must not be
  stolen by the dynamic allocator.
