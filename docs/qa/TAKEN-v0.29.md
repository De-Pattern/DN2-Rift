# QA's review of v0.29: what the build session took (2026-11-27)

The review arrived on `qa/v0.29` (b899ff8) while v0.29's gate ran. v0.29 ships as gated; what is taken goes
into v0.30 (the `v31` tree), each item its own change, gated with v0.30.

| Item | Decision |
|---|---|
| B1 SMEAR mono misses notes on one block (a chord kept its voices; a glue left out by the guard left two) | **Taken, v0.30**: the rule on state, not on the edge (`stage._mono`): of a track's voices that are on, one stays, a triggered one before one that is not, the higher mailbox among equals. Runner: two notes on one block on one track (one left), and its control on two tracks (both) |
| C1 the runner's several-voice SMEAR cases played one voice (TRK_ROUTE at zero) | **Taken, v0.30**: `_route_identity` (voice v plays track v) in `step_smear`'s cases and `mstress` |
| C2 the mono rule has no model and no unit test | Partly: the runner's cases now cover both edges and a tie; `stage.Model` without the rule is deferred (the model is the gate's bit-exact reference through the program, which carries the rule) |
| C3 `gstress` has no negative control | Deferred: a control run (SMP_FLOOR 0) needs the step to take a floor override; with the next guard change |
| C4 DIGIDRUM's heavy range 40..99 should be 41..100 | **Taken, v0.30** (`GE 41`, `LT 101`) |
| C5 SMEAR's STRT and SIZE show decimals the engine does not read | Deferred: `ctl_pos` for SMEAR's STRT changes its model; the owner's call by ear, after v0.30 |
| C6 Discord handles in public comments and the manual | **Taken, v0.30**: handles since v0.28 replaced by "a tester" in comments, and the thanks taken out of the v0.29 and v0.30 manual entries. Older entries' credits (heavylight, Error Kit's THOLET) predate the rule and are credits the owner asked for |
| C7 the PC-histogram probe in `run()`'s loop | Kept: one `is not None` test an instruction while off, in a probe the optimization work uses; recorded |
| Optimization 1: the mono scan only on blocks with a trigger | Deferred: the rule on state (B1) must also see a block after a skipped glue; measure its cost on the runner first |
| Optimization 2: the reverb's lines as pointers | Deferred, as in v0.28 |
| Note: smp.asm has 86 bytes left in its L2 span | Recorded: the next smp.asm change finds room first |
