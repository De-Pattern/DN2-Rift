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
- **Memory**: L1 block 1 has no free room left (it runs to 0x2e7000). A frame and its
  twiddles (about 16 KB a voice, plus 12 KB of shared tables) would sit in L2, at about 4x an
  access.
- **The next cuts**:
  - stages 0 and 1 without multiplies (their twiddles are 1 and -i);
  - radix 4 (half the passes over memory);
  - reclaiming L1 that RIFT doesn't use (PING, SHFT and GRAN's rooms, if RIFT carries
    none of them).
- Until those land, plan on one or two VOC voices a track. The SHARC runner's cost step
  measures it before any cap is set.

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
