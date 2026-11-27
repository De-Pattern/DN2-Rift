# QA's review of v0.28 (and its addendum): what the build session took (2026-11-26)

v0.28's gate was stopped 40 minutes in and restarted with these: two findings were floors v0.28 itself set too low.

| Item | Decision |
|---|---|
| C1 the sample voices' and SMEAR's new floor has no gate case | Deferred to v0.29 (with v0.27's C2: one guard step, the clock fed from measured costs) |
| C2 SMP_FLOOR rests on two machines | **Taken**: rprof now measures STRETCH 12,411, REPITCH 31,094, SLICE 30,719 beside ONESHOT and GRID |
| Addendum B1 a retriggered sample voice renders twice on its trigger block | **Taken**: SMP_FLOOR 64,000 (two renders of the heaviest machine, about 31,000 each) |
| C3 SMEAR's cost: GRN is about 70,000 | **Taken**: SMR_FLOOR 74,000 (rcost's 70,438 and 5 %) |
| C4 the pulled-RUBBER test's sites; the glass step's negative control | Sites **taken** (GRAPH_SITE, OVER_SITE); the negative control deferred to v0.29 |
| C5 RUBBER's page code still in the image | Deferred to v0.29: it idles with no filter 6 to read; out under `glass.coldfire.ON` when the C side is next touched |
| C6 the reverb's tail at DEC 127 is a quarter shorter, not a third | **Taken**: the manual and `mverb/live.py` give the measured times |
| C7 the kept reverb loop never run | **Taken**: `test_the_kept_loop_still_matches` |
| C8 DIGIDRUM's names checked at one TYPE | Deferred to v0.29 (a second TYPE in the gate's digidrum step) |
| Addendum: a p-locked TYPE shows the locked type's names on the page, the kit's in the header | Deferred: stock's own behaviour for a locked choice's dependent names; revisit if a user meets it |
| Proposal: the reverb's line addresses as pointers / circular buffers | Partly done in v0.28 (byte offsets, mask and base held in registers: 27,284 -> 14,548 instructions); the rest deferred |
| Proposal: the short lines (i0..i3, a_ap, b_ap) in L2 | Deferred: needs an L2 map check; about 2,500 cycles a block |

## QA's branch `qa/v0.27-smear-guard` (the owner's SMEAR cutouts on v0.27, 2026-11-26)

| Commit | Decision |
|---|---|
| b8ebccb a SMEAR slot's glue expected at SMEAR_GLUE (6,000), never stopped by the left-out-twice rule | **Taken, v0.28** (merged by hand with v0.28's trigger-block floors) |
| 02aae7e a block SMEAR's own guard leaves out sets the CPU marker | **Taken, v0.28** |
| e686a17 SMEAR's render guard x 1.25, FLOOR on the trigger block, 30,000 otherwise | Declined: v0.28 already has its own measured version (x 1.5 kept for GRN's swings, SMR_FLOOR 74,000 on the trigger block, IDLE_FLOOR otherwise) |
| docs/qa/SMEAR-cutout-v0.27.md's open question (30 to 50 s) | Open: the guard's left-out-twice stop explains silence until a later note; v0.28's gstress and the owner's test on v0.28 will say if anything else remains |
