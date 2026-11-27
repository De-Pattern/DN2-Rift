# Review of v0.29

The frozen source `rc/v0.29` at `073a80f`, against the last released tag `v0.27` (`3118908`). v0.28's part
of that diff (to `66bffc8`) was reviewed yesterday (`qa/v0.28`), so this pass read what came after it:
v0.28's last three commits and v0.29's fourteen. Reviewed 2026-11-27 by a fresh session, started with no
message; `rc/v0.29` was the newest `rc/*` with no review.

**How it was done: mostly by reading.** This session had the stock OS 1.11, Digitakt II 1.17 and
Machinedrum images, so the Python side ran: the build, `safety.preflight`, three unit-test files, and the
DSL's run mode. It had no SHARC emulator, no ColdFire emulator and no assemblers: no gate step, no runner
step and no cycle count. Each item says *read*, *run* or *measured*. Nothing here is a gate result.

## 1. Headline

Nothing found that could harm a unit or lose data. One grade B: SMEAR's one-voice rule does not cover
notes that arrive together, so a chord on a SMEAR track still starts a voice a note. And the most useful
thing for the gate: since the rule went in, the runner's SMEAR cases with more than one voice (the stress
of sixteen among them) play one voice at a time and still pass.

## 2. Findings

**B1. SMEAR mono: notes on the same block all keep running.** *Run (the rule's own program); the unit
not tested.* `src/dnfw/smear/stage.py:347` (`_mono`): a voice fades only when another voice of its track
is triggered on a block where it is itself on and not triggered. `docs/qa/v0.29/mono_cases.py` runs that
program over hand-made mailboxes:

| case | voices of the track running after the block |
|---|---|
| a second note on another voice (the runner's case) | 1 |
| two notes on the same block | 2 |
| four notes on the same block | 4 |
| the same four struck again on the same voices | 4 |
| then a single note on a fifth voice | 1 |
| the old voice's glue left out by the guard on the new note's block | 2, and still 2 the block after |

So a chord trig on a SMEAR track with its voices unlocked is as polyphonic as v0.28, each note looping
until a lone note arrives: the frame-filling case the release is named for. Whether the unit gives a
chord's notes several voices of a SMEAR track on one block is the ColdFire's allocator's doing and could
not be told here; one chord trig on the unit settles it. The last row needs the frame nearly full (the
glue is expected at 6,000), so it is rare, but it is the moment mono matters most.
A rule on state instead of on the edge would close both: each block, of a track's voices that are on,
only the newest stays (among several triggered together, one of them); the others fade or, if they have
not sounded yet, end at once. Which note of a chord should sound is the owner's to say.

**C1. The runner's SMEAR cases with several voices now play one at a time.** *Read; the rule's effect run.*
`scripts/sharc_waverider_m5.py:5587` says it: the runner leaves the voice routing (`TRK_ROUTE`) at zero,
every voice on track 0. With mono in, each new note therefore fades every other SMEAR voice. `step_smear`'s
"PLAY and GRN", "three tracks, two lanes" and "v0.22 FRZ" (`:5564-5568`) trigger their voices on
successive blocks: the first voice is gone on block 2 or 3 of 60, so FRZ beside a playing track is one
block of FRZ. `step_mstress` (`:5613`, "sixteen SMEAR tracks, a note on the next track every block") holds
one voice and one fading. All still pass: they ask bit-exactness to the same program, and a peak.
Several SMEAR tracks at once is still what a unit can do (two tracks never touch each other), and the
gate no longer runs it. The routing set to voice v on track v in `smr_frame`'s runs (as the mono control
does for two voices, `:5589`) puts it back; `mstress`'s instructions a block before and after `12b6ec3`
would show the size of it.

**C2. The mono rule has no model and no unit test.** *Read; the test run.* `stage.Model` (`stage.py:541`,
"the contract") has no fade, and `test/test_smear_stage.py:18, 91` build the layout without `smp_pos`, so
the rule is not emitted there (the 17 cases pass here without it). What holds it is the runner's one case,
which checks the old voice is silent from the block after the fade; the fade block itself (block 20) is in
neither of its ranges (`:5599`, 10..20 and 21..34), so the ramp is compared only with itself.

**C3. `gstress` has no negative control.** *Read.* `scripts/sharc_waverider_m5.py:5886`.
`TAKEN-v0.28.md` records the floors' gate case as done; the step has four checks and no run in which one
fails. Two that would: `SMP_FLOOR` at 0 (our voices must then end past 0.8 of the frame), and 60,000 on
every block (fewer than six heard between the downbeats). It also runs ONESHOT only; REPITCH is the
dearest render by `rprof` (31,094).

**C4. DIGIDRUM's floor by type.** *Read; the ranges computed from `digidrum.machines`.*
- `src/dnfw/digidrum/program.py:774-779` takes records 40..99 as the heavy types. By `machines.option`
  the types' records are SD VINTAGE 41..59, CP 60..80, CY 81..100: record 100 is CY ALLOY and gets the
  light floor (36,000 for 39,711), record 40 is SD BASIC and gets the heavy one. The page writes 9, 30,
  50, 70, 91 and 111, so only an LFO or a lock between choices lands there. `GE 41` and `LT 101`.
- No case fails if `DGD_HEAVY` or the light floor is wrong. `step_dstress` (`:4743`) runs CY ALLOY only
  and calls it the heaviest type; this release's own `rprof` has SD VINTAGE at 48,798 against CY's 39,711.

**C5. SMEAR's STRT and SIZE show two decimals the engine does not read.** *Read.*
`csrc/sampler/fmt.c:850` gives SMEAR the fine records (0.00 to 120.00, the knob in 1/256), and
`src/dnfw/sampler/program.py:446` still reads them through `ctl()` (the word >> 8): 121 places, as before.
The cap at 127 is right and closes the read past the table. But a fine turn now moves the number and not
the sound until the next whole step. How that feels under the hand is the owner's to judge; `ctl_pos`
would make the decimals real for STRT.

**C6. Discord names in this public repository.** *Read.* `CLAUDE.md` (2026-11-26): names and messages stay
in the bench. v0.29 added a handle, twice with the message quoted, at `csrc/sampler/fmt.c:847`,
`src/dnfw/digidrum/program.py:755`, `src/dnfw/sampler/program.py:455`,
`scripts/sharc_waverider_m5.py:5320`, in `9a19abe`'s message, and in the manual's v0.29 entry
(`scripts/gen_rift_manual.py:757-758`, so the public page). v0.28's are at `csrc/sampler/smp_page.c:939, 948`,
`csrc/waverider/page.c:150`, `src/dnfw/smear/stage.py:198`, `src/dnfw/sampler/program.py:3307`. If a thanks
in the manual is meant as credit, the rule wants that exception written down; the comments can cite the
bench's report instead.

**C7. v0.30's probe is in v0.29's frozen tree.** *Read.* `scripts/sharc_dn2_fixups.py:394-405`: the PC
histogram's test sits in `run()`, on every instruction the runner steps, in a file every SHARC step
reads. It does nothing while `PCHIST` is None. Named because the tree was frozen with it.

Read and found sound, no finding: the reverb's lines in SMEAR's lane (`mverb/program.py:71-99, 183-189,
515-521`: 16 KB exactly, asserted; the lane is never addressed while VOC is off, `LANE` being -1; cleared
on the clearing's first block; `MVERB_SAVE_DM` sits below it); the fade's registers and the sample
voice's `on` cleared at the voice's own index (`stage.py:272-299`); `_route`'s halves, the same way round
as `PP.half` and the runner's pokes; SMEAR's own start still writes SIZE 120.00 (`smr_default`, printed
here: 30720), so a fresh track never held a word past the range; RUBBER's page code under `GLASS_ON` in
all four places and `glass_names` out of the layout; the `pvmix` room (656 + 88 = 744).

## 3. Time and memory

No cycle count (no SHARC emulator); the ledger's v0.29 row says so. *Measured* here, by building each
tree on the stock image (`dnfw mods apply`; v0.27's build is the released file, sha256 3b987e6c...):

| | v0.27 | v0.28 (`9b5e2c3`) | v0.29 (`073a80f`) |
|---|---|---|---|
| 2 MiB image, bytes to spare | 796 | 1,604 | 1,806 |
| DSP upload, bytes to spare (of 1,048,575) | 1,951 | 5,889 | 5,137 |
| our DSP code as assembled | 190,526 | 186,608 | 187,360 |
| the ColdFire's C chunk | 216,272 | 217,152 | 216,416 |

- v0.29's +752 of DSP code: smear +552 (mono), fascia +132 (DIGIDRUM's expectation), mverb +44, smp +24.
- The sample machines' L2 span (24,576) holds smp 23,746 and pvmix's 744: **86 bytes left**. The next
  change to `smp.asm` of any size needs room found first.
- The mono scan runs on every block, SMEAR track or not: 386 steps of its program with no mailbox on,
  1,114 with one note among sixteen, 6,634 with sixteen triggered together (the DSL's steps, which count
  constant loads: not the unit's instructions).
- This tree's file: sha256 7ce19eb6a5a8cd3ca2103bd22f5ca4e04d292a9375f9dda6404dc146778416bf, preflight
  21/21, not gated. If the build session's differs, one of the two trees is not `073a80f`.

## 4. Optimizations

**Done: none.** Each needs its cost on the unit's model before and after, and there was no runner.

**Proposed** (bit for bit, not started):

1. **The mono scan only on a block with a trigger.** `_mono` can do nothing unless some mailbox holds a
   trigger; one test of the frame's trigger word (as `_track` reads it, `stage.py:202`) skips it on every
   other block. About 386 steps a block back for every user. Half an hour, with B1's change if that is
   taken (a rule on state needs its own cheap test).
2. v0.28's remaining one stands: the reverb's line addresses as pointers.

## 5. For the build session

- `scripts/sharc_waverider_m5.py` `smr_frame`'s runs: the routing at voice v on track v (C1); then
  `mstress` and the three `step_smear` cases mean what they say again.
- `step_smear`'s mono case: a case with both notes on one block, whatever is decided for B1; block 20's
  ramp checked against 31/32 .. 0 of the block before's continuation, or the rule given to `stage.Model`.
- `step_gstress`: a control that fails (C3).
- `src/dnfw/digidrum/program.py:774-775`: 41 and 101 (C4). `step_dstress`: SD VINTAGE, or its docstring.
- `src/dnfw/smear/stage.py:330`: the docstring says the 0x7fff bits, the code masks 0xFFFF.
- The handles in comments and the manual (C6).
- `scripts/sharc_dn2_fixups.py:394-405`: the probe out of `run()`'s loop, or behind its own runner (C7).

## 6. Not checked

- **Everything the emulators say**: every cycle figure (the reverb's 26,575, DIGIDRUM's by type, SMEAR
  mono's cost), every runner and gate step, the screens. The generated `.asm` and `.json` were not
  regenerated from their sources (no assembler); the build used them as committed.
- **`TRK_ROUTE` on the unit.** This is the first DSP rule that reads it a voice at a time. If the ColdFire
  writes a stolen voice's new track a block after its trigger reaches the DSP, the note would fade its old
  track's SMEAR voice and miss its own. Two SMEAR tracks sharing the voice pool, on the unit, would show it.
- **An old project's SMEAR track with SIZE or STRT stored above 120.00**: the DSP caps it (read); what the
  page shows before the knob is touched was not drawn. `docs/ROADMAP.md:62` has an unreproduced report of
  the same kind of change (v0.48, STRETCH, an old project), and item 10 there, the old-projects gate step,
  is still open.
- The reverb's L2 lines against power-on garbage: read as cleared before use; whether the runner's
  `garbage` part fills that lane was not looked at.
- The unit tests beyond `test_smear_stage.py`, `test_mverb_program.py` and `test_rubber_pulled.py` (17
  passed).
