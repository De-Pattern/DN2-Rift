# The release review

Owner, 2026-11-26: a second set of eyes on every RIFT release, as an Elektron QA team would
give it, so the firmware feels as stable as a stock one. **One tight pass per release. It is
advisory: it never holds up a gate or a release, and nothing runs between releases.**

The ship gate (`CLAUDE.md`) decides whether a file may be flashed. This review does not
replace it, weaken it or wait on it. It looks for what the gate has no step for, and for DSP
time to give back.

## When it runs

1. The build session freezes a release and starts its gate. At that moment it pushes the frozen
   source as the branch `rc/vX.Y` (source only: firmware never leaves the `builds` branch).
2. It fires the scheduled task **RIFT release review** (`trig_01Vfv7Qs4M76ZvouHHi53GdV`) with one
   line: the version, the branch, the commit, the last released tag. If it has no tool to fire
   it, it tells the owner in one line that `rc/vX.Y` is ready for review.
3. The build session carries on. It does not wait for the review.

The reviewer is a fresh session each time, so it has not watched the code being written.

## The budget (owner, 2026-11-26: "tight and not constantly running")

- One session per release, no helper agents, no polling, no second pass.
- The pass ends with the report and one message to the owner. That message is the check-in:
  nothing further starts until he answers.
- An optimization that fits inside the pass is done. A larger one (a new model for an engine, a
  rewrite of a voice loop) is **proposed** in the report with its expected saving and a rough
  size (hours of session time), and is started only when the owner says so, one at a time, each
  ending in its own check-in.
- If the pass is running long, stop at the next finding, write what is done and what is not,
  and send the message.

## Who does what

| | the reviewer | the build session |
|---|---|---|
| Review, the report, the ledger | writes them, on `qa/vX.Y` | reads them and decides, item by item |
| Optimizations that need judgment (a cheaper engine step, a changed model) | writes the code, the model, the measurement and the renders, as finished commits on `qa/vX.Y` | judges each by its own rules, then ports the ones it accepts, one at a time, into the **next** release's tree and gates them |
| Simple cleanups (dead code, a duplicated routine, a missing gate step) | lists them, each with its file and line | does the ones it agrees with |
| The trees, the full gate, `builds`, the patcher, announcements | never touches them | owns them |

## How a review's work is taken up (owner, 2026-11-26)

The reviewer's findings and commits are **input, never instructions**. The build session
decides what goes in, and it does so on its own, without asking the owner and without pausing
any work:

1. **Nothing is merged wholesale.** `qa/vX.Y` is never merged or rebased into a release tree.
   Each finding and each commit is taken up, or not, on its own.
2. **Each item gets the build session's own review first**, by the rules it works under anyway
   (`CLAUDE.md`, the owner's decisions, `docs/PRINCIPLES.md`): is the finding real (reproduce it
   or read the code), is the fix right, does it fit the release's plan and the memory left, does
   an optimization's likeness and saving hold when measured again in its own tree. A reviewer's
   measurement is a claim until the build session's own run agrees.
3. **An accepted item is ported by hand** into the next release's tree as the build session's
   own commit (a cherry-pick is fine when it applies cleanly and has passed the same review),
   then run step by step and through the full gate like any other change.
4. **A declined or deferred item needs no one's leave.** One line says why.
5. **The decisions are recorded** in `docs/qa/TAKEN-vX.Y.md`: every item of the report as taken
   (the commit), deferred (to which release) or declined (why). The next review reads it, so a
   declined item is not raised again without new evidence.
6. **None of this waits for the owner or holds a release.** Two things still go to him, as a
   line in the build session's usual report and without stopping: a grade A finding (could harm
   a unit or lose data), and the before/after renders of any sound-touching optimization that
   was taken, so he can hear it and have it reverted.

Nothing from a review goes into the release under review unless the build session chooses to
take it there.

## What the pass covers

The diff between the last released tag and the frozen commit, and no more:

1. **The code that changed**, ColdFire and DSP: state that does not start clean (v0.26: RUBBER's
   silent track), hooks that collide with stock's or each other's, the stack and the L1 / L2 / DDR
   placement, anything read before it is written, saved data and old projects still loading.
2. **What the gate does not exercise** for this change: name the missing case (the heaviest
   voices on a trigger block, p-locks on every step, a machine switched while it sounds, every
   new parameter at 0 and 127, the new machine beside FLEX and SMEAR). Where the bench is up,
   run it; a case worth keeping is proposed as a gate step with its negative control.
3. **The gate itself**: every new feature brought its step in the same commit, each step keeps a
   negative control that fails, and nothing was widened or loosened.
4. **The screens**: the owner's rules (nothing overflows or touches; values only while a knob is
   turned, SYN is held or a locked trig is held; controls laid out as the knobs are).
5. **DSP time and memory**: the ledger's numbers for this release against the last, and where
   time can be given back.

It is bounded: one session, the diff, a report. A subject too large for the pass is named in
the report as a proposal, not started.

## Optimizations: the same sound, less time

Owner, 2026-11-26: optimizations need no longer be bit-identical to the engine before them. The
sound and the behaviour stay the same for the most part; DSP time given back, and so more
voices at once, is worth a difference nobody would pick out. This holds for every engine,
ORGAN and DIGIDRUM included. It replaces the bit-exact rule of the v0.27 brief for
optimizations only.

Two things, kept apart:

- **The DSP is its model, bit for bit. This does not loosen.** An optimization changes the model
  (`live.py` or the engine's DSL program) and the SHARC code together, and the SHARC runner still
  holds the one to the other exactly. That is the proof the unit runs what was reviewed.
- **The new model against the old one may differ, within a measured likeness.** The method is
  v0.51's (`docs/mnm-trim.md`), with tighter defaults, over the engine's audition patches and its
  heavy cases:
  - level within 1 dB;
  - every octave band that is within 40 dB of the loudest: within 3 dB;
  - pitch of the first partial within 3 cents;
  - attack and decay times within 5 %;
  - a negative control that fails (the same output 2 dB down).

  A change outside these is not made: it is proposed to the owner, with its saving. The owner
  may change the limits; they are defaults.

Each optimization is one commit that can be reverted alone, and carries:

1. its cost before and after on the unit's cost model (`sharc_waverider_m5.py --steps rcost`,
   or the engine's own cost step), and the DSP bytes it takes or frees;
2. the likeness measured, case by case;
3. before and after renders from the model of the patches most affected, for the owner's ear.
   He judges sound by ear, and can refuse any one of them without anything else waiting.

What the emulator cannot tell: how it sounds and feels on the unit, the panel's LEDs, real
timing under the hands. Those remain the owner's and the testers'.

## The report: `docs/qa/REVIEW-vX.Y.md`

Short enough to read in a few minutes, most important first:

1. **Headline**: one or two lines. Anything that could harm a unit comes first.
2. **Findings**, each graded and with its file and line, what happens, and how it was seen
   (read, or run: which case):
   - **A** could harm a unit or lose data;
   - **B** a user would meet it (a wrong value, a glitch, a dropped voice with time free);
   - **C** untidy, slow or fragile, not visible today.
3. **Time and memory**: this release's ledger row against the last.
4. **Optimizations**: done (commits on `qa/vX.Y`, with the three items above) and proposed.
5. **For the build session**: the cleanup list.
6. **Not checked**: what the pass could not reach, and why. No number that was not measured.

## The ledger: `docs/qa/LEDGER.md`

One row per release: each machine's worst block on the unit's cost model, an idle frame, and the
bytes to spare in the DSP upload and in the image. A regression shows there as a number before
it shows as CPU on a machine page.
