# SMEAR (working name): a granular, phase-vocoded, stretchy looper

Queue item 2 (owner, 2026-11-18): "turn one of the DT2 sample machines into our granular
phase vocoded stretchy looper machine based loosely on the Qu-Bit Nebulae v2 ... GRID and
WERP first."

## Source

The owner's own pedal port, De-Pattern/Nebulae-Granular_Looper_Pedal (MIT),
`src/nebulae_dsp.cpp`. That code transcribes QB_Nebulae_V2's Csound instrument
`a_granularlooper.instr` (MIT). The reference model is `src/dnfw/smear/model.py`:

- float64;
- matches the pedal's `Mincer` to 57 dB SNR over a second of a two-tone source at speed
  0.37 and pitch 1.26. The difference is the pedal's Csound quirks at DC/Nyquist and the
  reused `frac`.

The auditions come from `scripts/smear_audition.py OUTDIR [SOURCE.wav]`.

## What it is on the Digitone

It is a sample machine voice over a sample slot, or later a FLEX buffer, with three readers
of one loop region:

- **VOC**: the phase vocoder.
  - Csound's `mincer`: FFT 2048, 4x overlap, hop 512, phase-locked.
  - The read point (SPEED) and the pitch are independent: it stretches without changing
    pitch, and pitches without changing speed.
  - SPEED 0 freezes.
- **PLAY**: the plain read at SPEED, like tape (varispeed). This is the pedal's dry.
- **GRN**: the grains.
  - Up to 10 at once, at 0.12..2500 per second (DENS).
  - Size set against density (OVLP).
  - Position scatter (SPRY) and per-grain detune of up to ±120 cents (PRND).
  - A window bank (WIN): GAUS, BHAR, EXPO, TRI, RAMP, SINC, RECT.
  - An RMS limiter at 0.20.
- **BLND** crossfades the three at constant power: VOC at 0, PLAY in the middle, GRN at the
  top.
- **A trig** starts the read phase at STRT. The note and TUNE set the pitch, so it plays
  chromatically.
- **The loop region** is STRT and SIZE (SIZE squared, as on the pedal).
- **The LFOs and p-locks** take the pedal's LFO jobs: read position, loop size, blend.

### Proposed pages (two SRC pages, eight controls each)

| | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| SRC 1 | TUNE | SPD | BLND | SAMP | STRT | SIZE | DENS | OVLP |
| SRC 2 | SPRY | PRND | WIN | LEV | (free) | (free) | (free) | (free) |

- SPD runs −4..+4 with detents at ±1 (the pedal's law); 0 freezes.
- WIN is a word choice, boxed in the LINE style.

### Where it goes

Proposal: SMEAR takes WERP's row in MACHINE SEL. GRID stays until our own stretch
(queue item 4) wants a row. WERP's machine type stays built, as BOUNCE's did, so a project
that holds a WERP track still loads and plays.

## The cost on the SHARC (estimate, before phase 0 measures it)

- **VOC**, per hop (512 samples, which is 16 blocks):
  - two forward real 2048-point FFTs and one inverse, about 35k instructions each;
  - two normalisations of 1,025 bins (a reciprocal square root each), about 50k;
  - 4,096 interpolated reads from the pool in DDR, about 70k.
  - In all about 230k a hop, **about 14k a block** once spread over the hop's 16 blocks
    (one sixteenth of the frame's work a block, never a whole frame in one block).
- **GRN**: 10 grains × 32 samples, with the pool reads, about **8k a block**.
- **A voice**: about 22k a block, about 3.3 % of the frame, the cost of a Monomachine
  machine.
- **State**: about 8k words a voice (the previous frame, the overlap-add, the two analysis
  frames). Where it lives (L1/L2/DDR) is phase 0's question.

## Phase 0 so far (2026-11-18)

- `src/dnfw/smear/fft.py`: the real 2048-point FFT and its inverse, written once in the DSL.
  - The program in run mode equals the float32 numpy model bit for bit
    (`test/test_smear_fft.py`), and the model is a correct FFT: within 1e-4 of numpy's, and
    the round trip to 1e-5.
  - Layout: a radix-2 complex 1024-point kernel, then the real split, in Csound's packing.
  - The twiddles are laid out stage by stage, so every pointer steps one word.
- **Cost**, run-mode instructions: 152k a transform (forward or inverse), 432 instructions
  of code. A hop's three transforms are about 460k; the hop's other work (windowed reads,
  phase lock) is still to write.
- **Memory, the plan**:
  - **L1, about 14 KB.** RIFT carries no PING, SHFT or GRAN. Since v0.45 their L1 rooms,
    0x2e1d00..0x2e5400 (`waverider/dsp.py`: PING's state, GRAN's code and scratch, SHFT's
    and GRAN's state), are loaded and read by nothing; no source names an address in them.
    The SHARC runner must confirm nothing writes there before SMEAR takes it.
  - **One shared 8 KB transform buffer** in that room. A hop's work is cut into jobs, one
    job a block; each job copies a voice's frame in, transforms it and copies it out, so the
    buffer is never held across blocks and the voices share it.
  - **Each voice's own state in DDR**, about 24 KB: the previous output spectrum, the held
    analysis spectrum and the overlap-add. That is about 12k DDR accesses a hop, about 8k
    instruction times a block.
  - **The twiddles in L2**, 20 KB shared.
  - **Estimate**: about 700k instruction times a hop, **about 44k a block a voice
    (6.6 % of the frame)**. That means a cap of 2–4 VOC voices; the unit's meter decides.
    PLAY and GRN cost far less.
- **Latency**: a trig's first vocoder frame comes 16 blocks (about 11 ms) after the note,
  and the overlap-add reaches full level after 2048 samples, as in `mincer`. The PLAY and
  GRN paths start at once. A pre-roll (the first frame computed at the trig) is a later
  option, for percussive sources.
- **The next cuts**:
  - stages 0 and 1 without multiplies (their twiddles are 1 and -i);
  - radix 4 (half the passes over memory);
  - reclaiming L1 that RIFT doesn't use (PING, SHFT and GRAN's rooms, if RIFT carries
    none of them).
- Until those land, plan on one or two VOC voices a track. The SHARC runner's cost step
  measures it before any cap is set.

### The vocoder's jobs (2026-11-18)

`src/dnfw/smear/program.py` holds the read, the phase step and the overlap-add, beside the
transforms. A whole frame's program in run mode equals `live.Voc` bit for bit over three
hops, with the previous spectrum carried and the ring's read point moved
(`test/test_smear_program.py`).

A frame is about 690k run-mode instructions, about 43k a block over its hop, before memory
costs. Its pieces:
- the two reads: about 30k each;
- the two forward transforms and the inverse: 152k each;
- the phase step: about 55k;
- the overlap-add: about 30k.

### Lanes and jobs (2026-11-18, decided)

- **Two VOC lanes for the whole instrument.** A lane is one vocoder's working frames
  (WF and WB, 16 KB) in L2's free room, 0x200b1000..0x200c0000 (60 KB; `waverider/dsp.py`:
  "free again" since SILT's move).
  - The room also holds the shared D scratch (8 KB) and the kernel's stage twiddles, forward
    and inverse (16 KB).
  - The window and the split twiddles go in DDR.
  - Each voice's P and ring stay in its own DDR state.
  - A note on a SMEAR voice takes a free lane, else the oldest's. A voice without a lane
    plays PLAY and GRN but no VOC.
  - The Nebulae is one voice; two lanes give two vocoded notes or tracks at once.
- **A hop is 15 jobs, one a block** (the 16th does none). Run-mode instructions, by
  `program.emit_job`:

| job | what | instructions |
|---|---|---|
| 0, 1 | read F, two halves | 37k, 37k |
| 2, 3 | read B, two halves | 41k, 41k |
| 4–6 | forward F, three parts | 62k, 46k, 45k |
| 7–9 | forward B, three parts | 62k, 46k, 45k |
| 10 | the phase step | 84k |
| 11–13 | inverse, three parts | 31k, 65k, 57k |
| 14 | overlap-add | 33k |

  - The heaviest block is 84k, 12.6 % of the frame a lane, before memory costs.
  - The second lane runs 8 blocks behind the first, so their heaviest jobs never share a
    block.
  - Running the jobs one after another equals the whole frame bit for bit
    (`test_jobs_are_the_frame`).

### Integration plan (phase 2 and 3)

- **The machine type**: WERP's type, 9.
  - SMEAR takes WERP's row in MACHINE SEL and its DSP dispatch.
  - WERP's reader stays in the code, reached from a type no list offers. A project saved
    with a WERP track then still plays it on loading. Whether such a track should open as
    SMEAR instead is the owner's call.
- **The records**: no new ones. SMEAR's twelve controls ride the sample machines' existing
  WaveTone records, away from the recorder screen's (247, 248, 243, 251, 252, 253, 259, and
  FLEX's BUF 244):

| | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| page 1 | TUNE 238 | SPD 254 | BLND 255 | SAMP 256 | STRT 239 | SIZE 258 | DENS 257 | OVLP 260 |
| page 2 | SPRY (a free record, to find) | PRND 242 | WIN 240 | LEV 241 | - | - | - | - |

  - Page 2 shows the sample's waveform behind its controls, with the loop and the read
    point, as the DT2's page 2 does.
  - The tables index each record's own range (STRT 0..120, WIN 0..100, PRND 4..120). SPRY needs one more WaveTone record that no
  sample machine uses: phase 3 reads the record table for it.
  - SPD and BLND have detents (64 is 0 and the middle).
  - WIN gets `smp_quant`'s one-detent-a-choice.
- **The DSP**: SMEAR's own program (`smear.asm`), entered from the sample machines'
  dispatch for type 9, as STRETCH's render is.
  - Its code is about 13 KB as written. Sharing the F and B transforms' code (the buffer
    address from a word, not an immediate) brings it to about 10 KB.
  - It needs a room of its own: FASCIA's L2 span, if FASCIA, ORGAN, SILT and RESONATOR
    leave that much, else the lane room.
  - With the code in the lane room, the stage twiddles move to DDR (about +10k a block a
    lane).
- **The voice's state**: the sampler's 128 bytes keep the slot, the region and the note.
  SMEAR's own state is in DDR, about 16.5 KB a slot:
  - the read point;
  - the grains;
  - P and the ring;
  - the lane it holds.
  The grains' words (about 300 bytes) are the busiest, so they may move to L1 if the runner
  shows they matter.
- **The sample's rate**: a pool entry's rate (for example 44.1 kHz, played at 48 kHz) scales
  SPD and the pitch, as the sampler's `rate` does.

### Memory facts found while planning (2026-11-18)

- **The DSP image has about 39 KB spare** under the 2 MiB USB limit (the v0.9 build is
  2,057,875 bytes). Anything loaded counts against it, zeros included.
  - So the lanes' memory, and each voice's SMEAR state, are **not loaded**. SMEAR clears
    them itself:
    - a lane's P and ring when a voice takes the lane;
    - WF and WB are wholly rewritten every hop;
    - a voice's grains at its first note after power-on (a magic word).
  - Only the code and the tables go in the image: about 13 KB of code, the twiddles
    (16 KB forward and inverse, 4 KB split), and the window (8 KB). That is too much beside
    the 39 KB.
  - **The twiddles are computed at power-on** instead, into their room, from one quarter
    sine table (or from a recurrence checked against the model). That leaves the code and
    a 2 KB seed.
- **L2 that RIFT does not use**:
  - 0x200b1000..0x200c0000 (60 KB, "free again");
  - the Machinedrum voices' 16 KB at 0x200a0000 and the DPRO tables' 4 KB at 0x200a8000
    (`dsp.l2_spans`: RIFT loads neither).
  The lanes, D and the stage twiddles fit with room to spare.
- **Lane-specific addresses**: the jobs use immediates. Either the VOC code is emitted
  once per lane (about 2 x 10 KB of image), or the lane's buffers come from a base
  register (one copy, a few instructions more a loop). The second is the plan, given the
  image.

### The image, done (2026-11-18)

- **Twiddles and the vocoder's window are computed at power-on.**
  - `fft.emit_init` derives them by symmetry from one quarter sine of 513 words (`fft.QSIN`,
    2 KB in the image): the stage-ordered forward and inverse twiddles, the split twiddles
    and the 2048-point Hann window.
  - It costs about 196k instructions once.
  - The model takes its tables from `QSIN` too, so they are equal word for word
    (`test_power_on_tables`). Negation is `0 - x` on both sides.
- **The grain windows are 129 points** (every fourth of the design's 513), seven shapes,
  3.6 KB.

## Build order

0. **Phase 0, the kernels.** Each is measured on the SHARC runner against its float32 model,
   bit for bit:
   - a real 2048-point FFT and its inverse;
   - the spread-over-16-blocks schedule.
1. The float32 contract (`live.py`), in the DSP's order; tests.
2. The program, one voice, then the voice cap from the measured cost; a stress step with a
   negative control.
3. The ColdFire side:
   - the machine type and its records;
   - the two pages in the LINE style;
   - MACHINE SEL's row.
4. The gate steps: bit-exactness, cost, the UI cells, save/load; the full gate; release.
