# Review of v0.27

`rc/v0.27` at 3118908 against v0.26's source 0ae025b: twelve commits. Reviewed 2026-11-26, after v0.27 was
released (the build session fired the task for it the same day, after v0.28's). Advisory: every item below is a
proposal for the build session to judge. v0.28 changed none of the code the two B findings are in, so they hold
for the current tree too.

**How it was done.** By reading, plus what runs without the bench: no SHARC runner, no ColdFire emulator, no
assemblers. With the owner's stock images (his project's files) `dnfw mods apply` built both sources to the
released files byte for byte (v0.26 b83513d3..., v0.27 3b987e6c...), so sizes are measured, and the Python tests
the diff touched were run. Nothing here is a gate result, and no cycle figure is this review's.

## 1. Headline

Nothing found that could harm a unit or lose data. Two things a user could meet, both in the guard's new,
leaner expectations and both read, not measured: CONTOUR's feedback turned up from 0 during a high note (B1),
and any glide across CONTOUR's step thresholds (smaller, in B1). One gate check was loosened, with its reason
written beside it (C1).

## 2. Findings

**B1. CONTOUR: feedback arriving mid-note is no longer expected.** *Read.*
`src/dnfw/contour/program.py:491-498`. v0.26 expected `CTR_PEAK` on every block whose FDBK word was not 0. v0.27
looks at FDBK and the pitch only on the block that triggers the voice (`expect` runs `triggered` only when R10,
the slot's trigger bit, is set). A voice struck with FDBK at 0 above B4 costs about 25,400 a block (1 step);
when FDBK leaves 0 (the knob, a p-lock on a trigless step, an LFO on FDBK) the next block runs 4 steps, about
82,000 by the build session's figures, against an expectation of 25,400 x 1.25. That is some 50,000 cycles over,
per voice, on that block. One voice fits in the limit's P/8 (about 83,000); two CONTOUR tracks whose FDBK rises
on the same block (one LFO shape on both, a pattern-wide p-lock) do not. The result would be a frame overrun: a
crackle, never harm. The commit's note covers a bend across B3 or B4 ("under by one step's cost for one block");
FDBK from 0 is the larger case and is not mentioned.
A fix that keeps v0.27's gain: run the pitch test on any block where FDBK is not 0 and the slot's last cost is
under the step count's measured cost (so it bites on the transition only). To settle it first: rprof CONTOUR at
84.0 with FDBK 0 for ten blocks, then FDBK up.

**C1. The flexlevel check was loosened.** *Read.* `scripts/sharc_waverider_m5.py:3019, 3050` (06cee15):
`ratio_ok` at LEVEL 20 now asks for 40 frame pairs within 1 %, where it asked 200. The reason is given (RIFT's
take has 45 frames loud enough) and every pair must still pass, so it is a narrower sample, not a wider
tolerance. It is still the one place in this release where a check asks less than before. A hotter take (GAIN up
for this case) would keep 200.

**C2. The guard's v0.27 change has `fkeep`'s melody for FASCIA and nothing for the three machines it was made
for.** *Read.* ORGAN, CONTOUR and SPALL got `LIGHT_FLOOR = 36,000` (`src/dnfw/fascia/program.py:134`) from rprof,
a probe. No step fails if 36,000 becomes 0, or if a machine's heaviest block grows past it. A case to keep:
eight ORGAN voices at every rank struck on one block, the frame inside its limit; control, the floor at 12,000.

**C3. The imports' unchecked parts.** *Read.* `docs/inkey.md` says the [+]/[-] keys and the ARPEGGIATOR menu's
marks are not driven in the emulator and rest on upstream's hardware reports, which were made on upstream's
firmware and on DN2 mk2, not beside RIFT's machines. The run-time overlap check does cover their two chunks
(`src/dnfw/mods/platform.py:141`, and the build passes it), and nothing in `csrc/` touches the pattern's track
byte +1187 or the flag at 0x405CD8AF. Not checked: whether upstream's code keeps state outside its chunks.

**C4. A FLEX take's level comes from the last frame a voice played the track.** *Read.*
`csrc/sampler/rectrig.c:820` stores each track's LEVEL word as frames pass; `:738` sends its coarse byte with bit
15. A LEVEL p-locked to 0 on the step before a take, or a track faded out, gives a silent take, by design ("as
much quieter as the track sounds"). Worth a line in the manual: a take of a track turned down is turned down.
The DSP side reads right: the source is still masked to its low byte (`sampler/program.py:1986`), BUS carries no
level bits, and the RECORDER, IN and MAIN stay at x 1.

**Checked and found right (read, or run where said):**
- `sl_clear`'s one pass (`csrc/slides/slide.c:424-460`) does what the three `lock_set` calls did: track and step
  are clamped above it, each of our records on the track loses the step's lock, a record left empty is freed.
- The shared guard leaves (`perc/guard.py`, `_around_shared`): R13 carries the floor into the leaf, the call
  clobbers only R12 and I12, the emitter forgets its known constants at the call and after the raw shift.
- CONTOUR's pitch arithmetic: 102 x the record (64 + 32 + 4 + 2), the thresholds half a semitone under B3 and B4;
  the step count in `contour/live.py:123-126` depends on the X increment only, so RATIO does not enter.
- The reverb's hot words in L1 for the block: `test_mverb_program.py` passes (run mode, bit for bit `live.Verb`).
- `safety.preflight` passes on both builds. Run here on `rc/v0.27`: `test_mverb_program`, `test_waverider_dsp`,
  `test_waverider_mod`, `test_contour_program`: 71 passed, 22 skipped (bench files absent).
- The gate gained its `midiarp` and `inkey` steps in the commits that brought the features.

## 3. Time and memory

| | v0.26 | v0.27 | how |
|---|---|---|---|
| DSP upload to spare (of 1,048,575) | 345 | 1,951 | measured: `safety.preflight` on each build |
| MAIN OS, unpacked | 3,491,376 | 3,494,916 (+3,540) | measured, the same builds |
| Master reverb, model steps a block | 26,086 | 26,102 | measured: run mode, noise in, both exact to `live.Verb` |

v0.26 shipped with 345 bytes of the DSP's upload buffer free. The reverb's v0.27 change moves four state words
from DDR to L1 for the block: 16 model steps more, and its saving is in memory stalls, which the model does not
count and this review could not measure. No machine's cost on the unit's model was measured: the ledger's v0.27
row stays the build session's.

## 4. Optimizations

**Done: none** (no assembler or runner, so nothing could be proved on the unit's cost model).

**Proposed:** none new for this diff. The reverb proposals in v0.28's report and addendum (line addresses as
pointers; the short lines in L2) apply to this code as well.

## 5. For the build session

- B1: profile CONTOUR above B4 with FDBK rising from 0 mid-note; if it overruns, expect by pitch on that block.
- C1: flexlevel's LEVEL 20 case back to 200 pairs with a hotter take, or leave it and say so in `TAKEN-v0.27.md`.
- C2: a guard step for ORGAN, CONTOUR and SPALL on a trigger block.
- C3: one emulator or hardware pass of [KEYBOARD] + [FUNC] + [+]/[-] on a RIFT machine's track, when a tester
  has a unit free.
- C4: the manual's FLEX section: a take follows the source track's LEVEL.
- `src/dnfw/contour/program.py:457`: `CTR_MID = 64,000` against a measured 44,600 at 2 steps; 56,000 would still
  be x 1.25 over it and lets one more voice in on a chord's block.
- The ledger on this branch is `qa/v0.28`'s with v0.26's bytes row added; `main` has neither yet.

## 6. Not checked

- Everything on the SHARC runner and in the ColdFire emulator: the DSP against its models, every cycle figure,
  the pages, boot, the fuzz, the new `midiarp` and `inkey` steps themselves.
- `gen_waverider_code.py --check` (no m68k assembler): the committed ColdFire code was not shown to be what
  `csrc/` compiles to. That the build reproduces the released sha256 shows only that the release was built from
  this commit's committed code.
- Upstream's assembler sources in `scripts/upstream_inkey/` (2,260 lines) were not read; the specs' guards and
  stock bytes are checked by the build.
- The manual and quick guide's text; the 2 MiB image's spare bytes (no stated method).
- How any of it sounds or feels on the unit.
