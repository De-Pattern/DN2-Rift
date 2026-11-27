# QA's review of v0.27: what the build session took (2026-11-26)

| Item | Decision |
|---|---|
| B1 CONTOUR: FDBK raised from 0 during a high note was not expected | **Taken, v0.28**: the pitch expectation on every block with FDBK up (`contour/program.py`), CTR_PEAK / CTR_MID set from the runner's worst at 4 and 2 steps (88,000 / 48,000) |
| C1 flexlevel's LEVEL 20 case asked 40 pairs | **Taken, v0.28**: DN2 mk2 v0.75's check (dac720c), 200 pairs and two int16 steps of slack |
| C2 no gate step for ORGAN, CONTOUR and SPALL on a trigger block | Deferred to v0.29: a guard step with the clock fed from measured costs |
| C3 the in-key keys not driven in the emulator | Deferred: a tester's pass on a unit (the gate's `inkey` step drives the logic) |
| C4 a FLEX take follows the source track's LEVEL: say so | **Taken, v0.28**: the manual's FLEX section |
| CTR_MID 64,000 against 44,600 measured | **Taken, v0.28**: 48,000 (the runner's 45,145 at 2 steps, and 6 %) |
