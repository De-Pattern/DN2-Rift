# SMEAR cuts out (v0.27): what the guard does to it, and three changes

The owner, 2026-11-26, on v0.27: SMEAR, alone, "cuts out completely" for 30 to 50 s whatever the
settings, and comes back if he keeps triggering. He asked what the guard is really doing and
whether it can ease up. Branch `qa/v0.27-smear-guard`. Read from the source; **not reproduced
and nothing measured**: the bench was not set up in this session.

## What happens to a SMEAR track each block

1. **The sampler's track loop** (`sampler/program.py`, `G.around(... struck=G.STRUCK, stop=stop)`)
   runs the slot's `voice()`. For SMEAR that is only `smear_glue`: at a note `smear_latch`, then
   fifteen words into the mailbox for smear.asm. The guard expects it to cost its last cost x 1.5,
   **at least FLOOR, 60,000 cycles, on every block** (v0.27's easing went to FASCIA's walk only;
   this call passes no `trig`). So the glue, about a thousand instructions, is left out whenever
   fewer than 60,000 cycles remain under the limit at the sampler's turn.
2. **Left out once:** the slot's buffer is zeroed and the mailbox is not written, so smear.asm
   renders nothing that block, with its own guard never asked. A note on that block is lost: the
   trigger exists only in that block's frame.
3. **Left out a second time in the same note** (v0.49's rule, `STRUCK`): `stop()` sets the voice's
   `on` to 0. The mailbox then says 0 frames and SMEAR is silent **until a later note whose own
   block fits**. A sample machine's note ends by itself; a SMEAR note loops for minutes, so two
   short blocks anywhere in it are enough.
4. **smear.asm's own guard** (`smear/stage.py`, `play()`), a separate copy: last cost x 1.5, at
   least FLOOR on every block, against the same LIMIT. A block it leaves out is counted in SKIPS
   but **not flagged in SKIPMASK**, so the page shows no CPU.

That matches the report: complete silence, not a crackle; no setting in particular; back only
with repeated triggers. What it does not explain by itself is the length, 30 to 50 s: the limit
would have to stay short that long. The limit is `min(0.6 P, max(P - TAIL - P/8, P/4))`, TAIL the
stock's tail held at its peak and eased by 1/4096 a frame (1/e in 2.7 s), so a high TAIL lasts
seconds, unless it is being raised again. **To measure on the unit or in the coupled emulator:**
LIMIT, TAIL, and how far into the frame the sampler's loop starts, with one SMEAR track sounding.

A second place a note can be silent, not changed here: `smear_latch` zeroes `on` and `frames`
before it reads the pool, so a note that arrives while the pool's header is not POOL_MAGIC, or
whose entry fails `entry_check`, plays nothing until the next note. If the link rewrites the pool
while playing, that is the same symptom.

## The owner's answers (2026-11-26, after the first three commits)

Nothing else was running, and **the silence starts on a trigger, not in the middle of a note.**
That moves the weight from the stop rule (which silences mid-note) to the note's latch:

- `smear_latch` zeroes `on` and `frames`, then sets them only if the pool's header is POOL_MAGIC,
  SAMP is inside the directory's count (or a buffer), and the entry passes `entry_check`. A note
  whose latch fails is silent until the next note whose latch succeeds. A held note is never
  affected (it latches only at its trigger), which is what he sees.
- When the directory is not whole on the DSP: `smp_load()` sends the page with every entry empty
  (K_BLANK), then each slot's frames and its entry, the whole page last. It runs at power-on, at
  a project switch (`pools.c`) and after the import tool's LOAD or END; the page shows LOADING n%.
  A SMEAR note in that window, on a slot not yet in, plays nothing. For a large pool that window
  is tens of seconds, the length he reports.
- Also rewritten while playing: the head (K_HEAD: the magic and the count, after every live entry
  and when a recording starts) and single entries (K_ENTRY).

**Not established:** that a load was running when he heard it, or whether SAMP's value in the
frame is always right on the trigger's own block (SLICE and GRID needed v0.28's relatch because
the key's note reaches the DSP a block after its trigger). To find out, in the coupled emulator:
a SMEAR note on every block for a minute after `smp_load()`, and on the blocks around a K_HEAD,
logging the latch's `on`. On the unit: what SMEAR's page shows for the sample while it is silent.

A change to weigh once the cause is known (not written): a note whose latch fails tries the latch
again on the following blocks for a short while, so a slot that arrives, or a header rewritten,
costs a few milliseconds instead of the whole note.

## The changes (each one commit, emit only: no model, sound or saved data changes)

1. **The glue is never struck out, and is expected to cost SMEAR_GLUE (6,000).** `stop()` does
   nothing for a SMEAR slot; `expect` sets the glue's expected cost. smp.asm +9 instructions
   (5,471 to 5,480, emitted unresolved). This is the fix for the report.
2. **A block smear.asm's guard leaves out sets the slot's SKIPMASK bit**: CPU on the page tells
   the truth.
3. **smear.asm's guard eased as the walk's was:** last cost x 1.25, FLOOR only on a note's block,
   otherwise at least SMR_IDLE_FLOOR (30,000). **Take this one only after measuring** SMEAR's
   worst jump in cost from one block to the next (GRN, DENS and OVLP at 127): the expectation
   must stay within P/8 of the real cost, or a frame can run long. With VOC_ON the VOC_PEAK rule
   is untouched.

## For the build session

- Regenerate smp.asm and smear.asm (not regenerated here), run `rprof`/`rcost`, then the steps
  that read them (`smear`, `mstress`, `rcost`, `fkeep`, the coupled steps), then the full gate.
- Set SMEAR_GLUE and SMR_IDLE_FLOOR from the measurements; both are guesses.
- A gate case worth adding: the clock made to move (as `fkeep`) so a SMEAR slot is left out twice
  in one note, then given time: it must sound again without a new note. Negative control: the
  v0.27 code stays silent.
- The other sample machines keep v0.49's stop; only SMEAR's endless note makes it wrong there.
