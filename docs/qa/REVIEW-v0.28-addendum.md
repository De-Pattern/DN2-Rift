# Review of v0.28: addendum

The review task ran twice for `rc/v0.28` (66bffc8): this session started with no message and no `qa/v0.28` on the
remote, and found `REVIEW-v0.28.md` already pushed when it came to push its own. The charter allows one pass, so
this is not a second report: only what the first does not have. The first report stands.

This session had the owner's stock OS 1.11, Digitakt II 1.17 and Machinedrum images (his project's files), so the
Python side ran: `dnfw mods apply` built v0.27's source to the released file byte for byte (sha256 3b987e6c...).
Still no SHARC runner, no ColdFire emulator, no assemblers. Nothing here is a gate result.

## One finding more

**B1. A retriggered sample voice is expected to cost one render; it runs two.** *Read; not measured.*
`src/dnfw/sampler/program.py:264-296` (on `rc/v0.28`): a note on a voice still sounding sets `kill`, and the block
renders the old note fading out, then the new one (v0.18's retrigger). The guard (`:3285`) expects
max(last cost x 1.25, 40,000) on that block: about 40,000 for a voice whose last block cost 30,000. The 30,800
behind `SMP_FLOOR` is rprof's strike of a silent voice, once, on block 1 (`scripts/sharc_waverider_m5.py:5376`).
v0.27's 60,000 on every block covered the double render by accident. WERP's segment boundary (`:288`, `segnext`)
is the same double render with no trigger bit: expected at last cost x 1.25, floor 12,000.
What a user could meet: several sample tracks retriggered on one block over ringing samples (a downbeat) each
run past what was expected of them; the limit's P/8 absorbs a few. Past it the frame overruns: a crackle, never
harm. This sharpens the first report's C2. To settle it: rprof with a second strike while the first rings, per
sample machine, and WERP across a boundary. If it is real, an `expect=` on the guard call that doubles the
expectation when the trigger bit and the voice's `on` are both set (and on `segnext`) keeps v0.28's gain elsewhere.

A smaller one, beside the first report's C8: `dgd_type` (`csrc/waverider/page.c:153`) reads the kit's TYPE, the
page (`smp_page.c:1048`) the shown value. If TYPE can be p-locked, a held locked trig shows that type's O1..O4 on
the page and the kit's type's names in the header. Read.

## Measured here

| | v0.27 | v0.28 | how |
|---|---|---|---|
| DSP upload to spare (of 1,048,575) | 1,951 | 5,949 | `safety.preflight` on each build |
| MAIN OS, unpacked | 3,494,916 | 3,495,576 | the same builds |
| Master reverb, model steps a block | 26,102 | 15,830 | `mverb.program` in run mode, noise in, PRE 32 / DEC 96 / FREQ 64 / GAIN 64 |

- `safety.preflight` passes on the file `rc/v0.28` builds (bootstrap, updater, metadata, Outbox, signature, DSP
  size). The file's sha256 is a69ae35d7f90e57087013e2ab78d774eb5563e50e46779ca9f3f52f783f194b3; if the build
  session's differs, one of the two trees is not 66bffc8.
- `test_mverb_program.py` (13 cases) and `test_rubber_pulled.py` pass on `rc/v0.28`; `test_glass_coldfire.py`
  skips, as written.
- The first report's C7 (the kept loop never run): run here once with `FAST = False`, 40 blocks of noise, bit for
  bit `live.Verb`. It holds today; the test case is still worth adding.
- The reverb's tail, a 0.1 s burst, to fall 60 dB: DEC 64 4.23 -> 4.08 s, DEC 96 13.79 -> 12.00 s; DEC 127 past
  30 s with either pair. Consistent with the first report's table.
- The committed ColdFire chunk carries "0.28" once and "0.27" nowhere.

Model steps count every constant load, so they are not the unit's instructions; the build session's runner
figures (27,284 -> 14,548 instructions, 43,263 -> 28,581 cycles) were not re-measured.

## One proposal more

**The reverb's short lines in L2, not DDR** (bit for bit; arithmetic on the cost model's weights, not a
measurement). After v0.28 about half the reverb's 28,581 cycles are its lines' DDR accesses (10 each, the lines
at 0x826c0100). The four input diffusers `i0..i3` are 2,048 words (8,192 bytes), read and written once each a
sample: 8 accesses x 32 x 6 cycles x 0.95, about 1,460 cycles a block for 8 KB of L2. The tank's two modulated
all-passes (`a_ap`, `b_ap`, 16 KB together, three accesses a sample each) another 1,090. An hour, if L2 has room.

## Not checked

As the first report, less the unit tests named above and the upload's spare bytes. `gen_waverider_code.py --check`
could not run (no m68k assembler).
