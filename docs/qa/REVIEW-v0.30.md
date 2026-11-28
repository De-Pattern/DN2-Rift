# Review of v0.30

The frozen source `rc/v0.30` at `0dc29eb`, against the last released tag `v0.28` (`9b5e2c3`). v0.29's part of
that diff (to `073a80f`) was reviewed yesterday (`qa/v0.29`, taken up in `TAKEN-v0.29.md`), so this pass read
what came after it: v0.30's nineteen commits (the FLEX buffer waveform, the FLEX step lag, LEAN's leaner
ISR hooks and polls, keys first, TEMPO + YES, and the items taken from the v0.29 review). Reviewed 2026-11-28
by a fresh session, started with no message; `rc/v0.30` was the newest `rc/*` with no review.

**How it was done: mostly by reading.** This session had the stock OS 1.11, Digitakt II 1.17 and
Machinedrum images, so the Python side ran: the build, `safety.preflight`, 32 unit tests, the DSL's run
mode, and a line-for-line Python port of one C loop. It had no SHARC emulator, no ColdFire emulator and no
compilers: no gate step, no runner step, no cycle count, no screen. Each item says *read*, *run* or
*measured*. Nothing here is a gate result.

## 1. Headline

Nothing found that could harm a unit or lose data. Two grade B, both small: a FLEX buffer's new waveform
draws silence at the level of the sound that follows it, and SMEAR's one-voice rule can keep the old note
and end the new one after a skipped fade. The thing to watch is memory and time, not a bug: the 2 MiB image
has 1,200 bytes left (1,806 at v0.29), and the mono rule now compares every pair of voices on every block.

## 2. Findings

**B1. A FLEX buffer's waveform shows silence as sound.** *Run (a port of the loop); the unit not tested.*
`csrc/sampler/rec.c:758-780`. Each report paints the columns "since the last report" with its peak, and finds
the last report by walking back over columns that are 0. A column is also 0 when the report's peak was 0
(the DSP sends the block's peak, `sampler/program.py:2417`; a silent internal track is exactly 0), so the
first sound after a silence is painted back over the whole silence. `docs/qa/v0.30/overview_fill.py`, a
two-second take:

| take | columns drawn |
|---|---|
| silence for a second, then a sound | all of 0..98 at the sound's level |
| a hit, silence, a quieter hit at 1.5 s | the hit, then the whole gap at the second hit's level |
| a steady sound (the control) | level throughout |

So a kick on beat 3 of an otherwise empty bar reads as a bar of sound. The last column or two can also stay
empty (no report falls in them before `rt_cur_end`); with keys first a held knob spaces the reports further.
Nothing but the picture is affected. A fix that keeps the rest: remember the last column written (a word
beside `rt_cur_ix`, set to 0 by `rt_trig`) and paint from there, zero or not.
The gate's check of it (`scripts/emu_coupled_flex.py:315`, at least 80 of 100 columns lit) passes with the
back-fill and would pass more easily because of it; a take whose first half is silent, its first columns
asked to be 0, is the case that tells the two apart.

**B2. SMEAR mono: after a fade that could not run, the higher voice stays, not the newer note.** *Run (the
rule's own program).* `src/dnfw/smear/stage.py:347-420`. The rule on state closes v0.29's B1: a chord on one
block leaves one voice (run: four notes, voice 3 stays), and two voices left on by a skipped fade become one
on the next block. But which one is decided by the mailbox's number, and the docstring's "the newer index"
is not so: the allocator's newer voice can be the lower one. `docs/qa/v0.30/mono_cases.py`:

| case | still running |
|---|---|
| old note on voice 5, new (triggered) on voice 2 | 2 (right) |
| ... its fade skipped by the guard; the block after, both on, neither triggered | **5**: the new note is ended, the old one loops on |
| old on voice 2, new on voice 5, the block after a skipped fade | 5 (right) |

It needs the guard to leave the old voice out on the very block the new note arrives, so it is rare; when
it happens the track plays the wrong note until the next one. The runner's new cases (`sharc_waverider_m5.py`,
"two notes on one block") cover the chord and its control, not this.
One change would settle this and C1 together: do not clear FADE every block (`stage.py:493`); a voice's bit
is cleared when its fade has run (`faded()`, `:272`). A fade the guard skipped then waits for the voice's next
block, whatever its number, and the scan is needed only on a block with a trigger. Proposed, not written here
(it changes `smear.asm`, and this session cannot assemble or run it).

**C1. The mono scan now does its pair work on every block.** *Measured, in the DSL's steps (they count
constant loads; they are not the unit's instructions or cycles).* v0.29 looked at the other voices only on
a block with a trigger. The rule on state looks at them for every voice that is on, on every block:

| a block with no note | v0.29 | v0.30 |
|---|---|---|
| no SMEAR voice | 386 | 306 |
| one SMEAR track sounding | 387 | 605 |
| four SMEAR tracks sounding | 390 | 1,666 |
| sixteen SMEAR tracks sounding | 402 | 8,338 |

A project with several SMEAR tracks pays it 1,500 times a second, on the blocks where time is shortest.
What it is in cycles on the unit needs the runner (`mstress` before and after `f6735fd` would show it).
`TAKEN-v0.29.md` deferred "the scan only on blocks with a trigger" because the rule on state must see the
block after a skipped fade; B2's change removes that need.

**C2. The new gate steps and their controls.** *Read.*
- `keystream` (`scripts/emu_keystream.py`, `ship_gate.py:4212-4230`) has no run in which it fails. A build
  with the cap of 8 passes taken out is its control.
- `flexlag`'s control is named in its docstring (the build before the change fails link 4, a tick late) and
  in the gate's comment, but the gate does not run it.
- `flexlag` runs `--step 1` only. `--step 0`, PLAY's own first step, where the take starts at once
  (`rectrig.c:570`, `was == 0xFF`), is in the script and not in the gate; nor is STOP with a trig still
  waiting for its tick (`rt_dl_on = 0`, `:545`).
- `tempoyes` has its control in the run (a plain YES opens the menu before and after). Good.
- The flexpool step's new shot is compared only for being different from page 1 (`ship_gate.py:2121`): any
  drawing passes.

**C3. Tester handles.** *Read.* The comments since v0.28 are cleaned (C6 of v0.29: grep finds none of them in
the tree). Two of this release's commit messages still name a tester (`d06a396`, `e967fab`); history is not
rewritten, so it is one for the next messages. `docs/slides.md` has one older handle the cleaning missed.

Read and found sound, no finding: the step lag (`rectrig.c:520-582`: one waiting trig a track, dropped on
STOP, the one-shot spent only when its take started, the BUSY rule's "its own, ending now" still met since
both takes start the same tick late); `ms_frame`'s early return (`:875`: the gains start at 256, `ms_low`
keeps the loop running until every fade back has ended, `rt_lvl` is read only by FLEX's own takes and
meter, which need a FLEX track); `ms_mask_now`'s inlined test against `rt_is_bounce` (the same byte);
`voice_kinds` and the three loops it feeds (`link.c:3083-3170`: the same voices visited as before, by the
same test); `smp_status`'s reuse within a period (`:250`: a read torn by the ISR is stamped with the period
before it, so it is read again); `smp_skipped_any` on the newest stamp; `smp_overview` for a buffer
(`:633`: the sixteen halves fit before the slice columns, asserted; `smp_slices` still refuses a slot past
the pool, so no slice marks from another slot's table); TEMPO held (`rec.c:1974`, bit 9 as the key's
code, the same 15,000 as a [TRIG]'s); DIGIDRUM's 41 and 101 in `program.py:774` and in `fascia.asm`; the
ship gate's diff (three steps added, one check tightened from 5 shots to 6, nothing loosened).

## 3. Time and memory

No cycle count (no SHARC emulator); the ledger's v0.30 row says so. *Measured* here by building each tree
on the stock image (`dnfw mods apply`), v0.29's figures from yesterday's review:

| | v0.28 (`9b5e2c3`) | v0.29 (`073a80f`) | v0.30 (`0dc29eb`) |
|---|---|---|---|
| 2 MiB image, bytes to spare | 1,604 | 1,806 | **1,200** |
| DSP upload, bytes to spare (of 1,048,575) | 5,889 | 5,137 | 5,013 |
| our DSP code as assembled | 186,608 | 187,360 | 187,484 |
| the ColdFire's C chunk | 217,152 | 216,416 | 217,532 |

- The image: 606 bytes went in one release, for 1,116 bytes of C. Two more releases of this size do not
  fit. The receiver has no bound of its own (`safety.preflight` is the only thing that stops an image over
  2 MiB), so the gate holds it; the room has to be found before the next feature, not after.
- The DSP: +124, all in smear (6,724 to 6,848, the rule on state). The sample machines' L2 span is as it
  was: 86 bytes left.
- This tree's file: sha256 c786acf488d255062779e0b572c1d3d8c12b847eb75b5b35b620ac7e3584c607, preflight
  21/21, not gated. If the build session's differs, one of the two trees is not `0dc29eb`.
- The build session's own figures for LEAN (the CPU marker's poll 589 to 11 instructions a period, the
  ISR's hooks with no FLEX track) were not measured again: no ColdFire emulator.

## 4. Optimizations

**Done: none.** Each needs its cost on the unit's model before and after, and there was no runner.

**Proposed** (the same sound, bit for bit; not started):

1. **SMEAR mono: fades kept until they run, the scan on trigger blocks only** (B2 and C1 together). FADE is
   not cleared each block; a voice's bit is cleared where its fade runs; `_mono` is skipped unless the
   frame's trigger word is set (as `_track` reads it, `stage.py:199`). Back to about v0.29's cost on a block
   with no note, and the skipped fade lands on the right voice. One to two hours with its runner cases (the
   skipped fade with the old voice the higher one; `mstress` before and after).
2. Still standing from v0.28: the reverb's line addresses as pointers.

## 5. For the build session

- `csrc/sampler/rec.c:770-778`: the overview's last column kept in a word, not found by walking back over
  zeros (B1); the take's last columns filled at its end. `emu_coupled_flex.py:315`: a take with a silent
  first half.
- `src/dnfw/smear/stage.py:351`: "the newer index" is the higher index (B2), whatever is decided.
- `scripts/sharc_waverider_m5.py` `step_smear`: the block after a skipped fade, the old voice the higher.
- `ship_gate.py`: `keystream`'s and `flexlag`'s controls run, or named as run by hand; `flexlag --step 0` (C2).
- `csrc/sampler/link.c:633-637`: 128 and 129 are `BUF_SLOT0` and `BUF_SLOT0 + 1` (`sampler/machines.py:373`);
  the name, or an assert beside the one at `:123`.
- `src/dnfw/sampler/program.py:3139`: the docstring says frames / 32; the code shifts by 6 and `rec.c:746`
  reads 64 a unit.
- `docs/slides.md`: one handle left (C3).

## 6. Not checked

- **Everything the emulators say**: every cycle and instruction figure, every gate and runner step, the
  screens (the buffer's waveform page, drawn by the pool's `waveform()`, was not drawn here). The generated
  `.asm`, `.json` and the compiled C chunk were not regenerated from their sources (no assembler, no
  compiler); the build used them as committed, and `code-fresh` is the gate's.
- **Keys first on the unit**: what a pass costs with a knob held, so how far apart the polls fall (the
  recorder's meter, `rt_poll`'s plan every 150 ms) when eight passes in nine skip them. Read as bounded;
  the feel is the owner's.
- **The step lag by ear**: the tick less 2 ms is from field measurements at three tempos; swing, a track
  at another scale and a microtimed trig were not reasoned through, and the emulator's step is the only
  case gated.
- **`TRK_ROUTE` on the unit** (from v0.29's list, still open): whether a stolen voice's new track reaches
  the DSP on its trigger block. The rule on state reads it every block now.
- **Saved data and old projects**: nothing in this diff changes a saved format (read: the overviews and the
  waiting trigs are RAM only). The old-projects gate step (`docs/ROADMAP.md`, item 10) is still open.
- The unit tests beyond `test_smear_stage.py`, `test_rubber_pulled.py`, `test_mverb_program.py` and
  `test_digidrum_program.py` (32 passed).
