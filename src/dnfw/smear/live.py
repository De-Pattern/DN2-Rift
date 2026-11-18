"""SMEAR's vocoder (VOC) as the DSP computes it: the float32 contract (phase 1, first part).

The design and its reference are `model.py` (float64, the pedal's `Mincer`). This module is
what the SHARC program will be held to bit for bit. It follows the same rules as RIFT's
other live models:
- float32 after every operation, in the DSP's order;
- add, subtract, multiply, compare, FLOAT/TRUNC, table reads and integer arithmetic;
- no division and no square root. The reciprocal square root is an integer seed and two
  Newton steps.

**A hop** (512 samples, 16 blocks of 32). At the hop's first block the voice latches:
- the read point `tim` (samples into the buffer);
- the pitch ratio.

The frame is then computed over the hop's blocks, one job a block (`program.N_JOBS`, 15),
and added to the overlap-add ring at the end of job 14's block, so it sounds from the next
block on. After a reset, nothing is added until a hop has started (job 0). In the model the whole frame is computed at that last block. That gives the same
result, because no job reads anything the other blocks change.

The frame:
1. `spos` = the read point, floored to a multiple of HOP and wrapped into (0, size]: an
   integer.
2. Two windowed reads of FFT_N samples, at `spos + pitch * i` (F) and HOP x pitch earlier
   (B). Both are linearly interpolated, and B reuses F's fraction (Csound's `mincer` does
   the same). The offsets are formed apart from `spos` (`read_frames`), so a long buffer
   loses no precision.
3. Both are transformed (`fft.forward`, Csound's packing; the Nyquist and DC bins are real).
4. The phase step. `d = conj(B) x prev / |prev|`, then phase-locked (each bin plus its two
   neighbours), normalised, and applied to F: `out = F x u`. `out` is the next `prev`.
5. The inverse (`fft.inverse`, 1024 x the signal). It is windowed and scaled by
   (2/3)/1024: `mincer`'s 4x-overlap scaling with the transform's 1/1024 folded in. It is
   then added into the 2048-sample overlap-add ring, from its read point on.

The output, a sample: the ring's word at the read point, which is then cleared, and the
read point moves on (mod 2048).
"""

from __future__ import annotations

import numpy as np

from . import fft as F

f32 = np.float32
FFT_N = F.REAL_N
HOP = 512
BLOCK = 32
BLOCKS_PER_HOP = HOP // BLOCK            # 16
BINS = FFT_N // 2 + 1                    # 1025
OLA_JOB = 14                             # the hop's job that adds the frame (program.N_JOBS - 1)
EPS_PREV = f32(1e-30)
EPS_LOCK = f32(1e-15)
SCALE = f32(f32(2.0 / 3.0) * f32(1.0 / 1024.0))
WIN = np.array([f32(0.5) - f32(0.5) * F.cos2048(i) for i in range(FFT_N)], f32)   # Hann, from fft.QSIN


def rsqrt(x: np.ndarray) -> np.ndarray:
    """1 / sqrt(x) for x > 0, float32: the seed 0x5f3759df - (bits >> 1), then two Newton
    steps y = y (1.5 - (0.5 x) y y) in that order."""
    x = np.asarray(x, f32)
    y = (np.uint32(0x5F3759DF) - (x.view(np.uint32) >> np.uint32(1))).astype(np.uint32).view(f32)
    h = f32(0.5) * x
    for _ in range(2):
        t = h * (y * y)
        y = y * (f32(1.5) - t)
    return y


def read_frames(buf: np.ndarray, tim: float, pitch: float):
    """Step 2: the two windowed reads (float32). The read point `spos` is an integer (a
    multiple of HOP), so the offsets are formed apart from it: x = pitch x i is at most
    4 x 2048 = 8192, where float32 still resolves a ten-thousandth of a sample, whatever the
    buffer's length. F reads at spos + trunc(x) with the fraction x - trunc(x); B reads at
    spos + floor(x - HOP x pitch), with F's fraction."""
    size = len(buf)
    spos = HOP * int(np.floor(tim / HOP))
    spos = (spos - 1) % size + 1
    p = f32(pitch)
    i = np.arange(FFT_N).astype(f32)
    x = p * i
    t = x.astype(np.int64)                            # TRUNC (x >= 0)
    frac = x - t.astype(f32)
    hp = f32(f32(HOP) * p)
    xb = x - hp
    tb = xb.astype(np.int64)                          # TRUNC, toward zero ...
    tb = tb - (tb.astype(f32) > xb)                   # ... then down: floor
    idx, ib = spos + t, spos + tb

    def sample(k):
        k = k % size
        s0 = buf[k]
        s1 = np.where(k + 1 < size, buf[np.minimum(k + 1, size - 1)], s0)
        return s0 + frac * (s1 - s0)
    return sample(idx) * WIN, sample(ib) * WIN


def bins(X: np.ndarray):
    """The packed spectrum as (re, im) of bins 0..1024."""
    re = np.empty(BINS, f32)
    im = np.zeros(BINS, f32)
    re[0], re[-1] = X[0], X[1]
    re[1:-1], im[1:-1] = X[2::2], X[3::2]
    return re, im


def pack(re, im) -> np.ndarray:
    X = np.empty(FFT_N, f32)
    X[0], X[1] = re[0], re[-1]
    X[2::2], X[3::2] = re[1:-1], im[1:-1]
    return X


def phase_step(Fr, Fi, Br, Bi, Pr, Pi):
    """Step 4. Returns the output spectrum (re, im); it is also the next prev."""
    n = rsqrt(Pr * Pr + Pi * Pi + EPS_PREV)
    pr, pi = Pr * n, Pi * n
    dr = Br * pr + Bi * pi
    di = Br * pi - Bi * pr
    lr = dr.copy()
    li = di.copy()
    lr[1:-1] = (dr[:-2] + dr[1:-1]) + dr[2:]
    li[1:-1] = (di[:-2] + di[1:-1]) + di[2:]
    lr[0], li[0] = dr[0] + dr[1], f32(0)
    lr[-1], li[-1] = dr[-2] + dr[-1], f32(0)
    lr = lr + EPS_LOCK
    m = rsqrt(lr * lr + li * li)
    ur, ui = lr * m, li * m
    Or, Oi = Fr * ur - Fi * ui, Fr * ui + Fi * ur
    Oi[0] = Oi[-1] = f32(0)                       # the DC and Nyquist bins are real
    return Or, Oi


class Voc:
    """One voice's vocoder, block by block."""

    def __init__(self, buf):
        self.buf = np.asarray(buf, f32)
        self.reset()

    def reset(self):
        self.Pr = np.zeros(BINS, f32)
        self.Pi = np.zeros(BINS, f32)
        self.ring = np.zeros(FFT_N, f32)
        self.r = 0
        self.job = 0
        self.latched = (0.0, 1.0)
        self.armed = False                 # a hop has started since the reset

    def frame(self, tim, pitch):
        fw, bw = read_frames(self.buf, tim, pitch)
        Fr, Fi = bins(F.forward(fw))
        Br, Bi = bins(F.forward(bw))
        Or, Oi = phase_step(Fr, Fi, Br, Bi, self.Pr, self.Pi)
        self.Pr, self.Pi = Or, Oi
        x = F.inverse(pack(Or, Oi))
        return (WIN * x) * SCALE

    def block(self, tim: float, pitch: float, job: int | None = None) -> np.ndarray:
        """One block of 32 output samples. TIM and PITCH are this block's; only a hop's
        first block's are used. JOB: which of the hop's 16 blocks this is (None: the
        voice's own count, from its reset)."""
        if job is not None:
            self.job = job
        if self.job == 0:
            self.latched = (tim, pitch)
            self.armed = True
        out = np.empty(BLOCK, f32)
        for s in range(BLOCK):
            out[s] = self.ring[self.r]
            self.ring[self.r] = f32(0)
            self.r = (self.r + 1) & (FFT_N - 1)
        if self.job == OLA_JOB and self.armed:
            fr = self.frame(*self.latched)
            k = (self.r + np.arange(FFT_N)) & (FFT_N - 1)
            self.ring[k] = self.ring[k] + fr
        self.job = (self.job + 1) % BLOCKS_PER_HOP
        return out


# ================================================================================ GRN
GRAINS = 8
WIN_LEN = 128                    # a grain window's points less one (the design's 512, every fourth)
GRAIN_AMP = f32(0.45)
RMS_CEIL = f32(0.20)
RMS_B = f32(np.exp(-2 * np.pi * 10.0 / 48000.0))
RMS_C = f32(f32(1.0) - RMS_B)
LCG_A, LCG_C = 1664525, 1013904223
LN2 = (f32(0.693147180559945), f32(0.240226506959101), f32(0.0555041086648216))


def exp2_small(x: f32) -> f32:
    """2^x for |x| <= 0.1 (a grain's detune, in octaves): 1 + x (c1 + x (c2 + x c3))."""
    c1, c2, c3 = LN2
    return f32(1.0) + x * (c1 + x * (c2 + x * c3))


class Grn:
    """The grains, sample by sample, as the DSP computes them.

    A voice's state:
    - the launch phasor;
    - the random generator (an LCG; r = its word as a signed fraction, -1..1);
    - a launch counter;
    - the limiter's mean square and gain;
    - per grain: active, read point (integer and fraction), step (integer and fraction),
      window phase and step, and its launch number (for stealing the oldest).

    A grain reads the buffer with linear interpolation; the next sample wraps to 0 at the
    end. Its window is one of model.WINDOWS (513 points), read with linear interpolation.
    Its value is (s x 0.45) x w.

    Launch, at the sample the phasor passes 1:
    - into the first free slot, else the oldest's;
    - at the block's read point plus trunc(r x spray x size), wrapped;
    - with step pitch x 2^(r' x prand x 0.1) (r' the generator's next value; the detune is
      at most +-0.1 octave, the pedal's 120 cents);
    - its window advancing 1/dur a sample, ending at 1.

    The limiter acts at the block's end: the mean square moves sample by sample
    (b ms + (1 - b) v^2); the gain is min(1, 0.2 x rsqrt(ms + 1e-30)); it is ramped across
    the block from the last block's."""

    def __init__(self, buf, window: np.ndarray):
        self.buf = np.asarray(buf, f32)
        self.win = np.asarray(window, f32)
        self.gphase = f32(0)
        self.rng = 0x1234567
        self.order = 0
        self.ms = f32(0)
        self.gain = f32(1)
        self.g = [dict(on=0, pi=0, pf=f32(0), di=0, df=f32(0), e=f32(0), ei=f32(0), o=0)
                  for _ in range(GRAINS)]

    def rnd(self) -> f32:
        self.rng = (self.rng * LCG_A + LCG_C) & 0xFFFFFFFF
        v = self.rng - (1 << 32) if self.rng >> 31 else self.rng
        return f32(v * 2.0 ** -31)

    def launch(self, read: int, pitch: f32, spray: f32, prand: f32, envinc: f32):
        slot = next((k for k, g in enumerate(self.g) if not g["on"]), None)
        if slot is None:
            slot = min(range(GRAINS), key=lambda k: self.g[k]["o"])
        size = len(self.buf)
        r1 = self.rnd()
        off = int(np.trunc(f32(f32(r1 * spray) * f32(size))))
        pos = (read + off) % size
        r2 = self.rnd()
        step = f32(pitch * exp2_small(f32(f32(r2 * prand) * f32(0.1))))
        di = int(np.trunc(step))
        self.order += 1
        self.g[slot] = dict(on=1, pi=pos, pf=f32(0), di=di, df=f32(step - f32(di)), e=f32(0),
                            ei=envinc, o=self.order)

    def block(self, read: int, pitch, ginc, envinc, spray, prand, n=32) -> np.ndarray:
        """READ: the read point (an integer sample) this block; GINC: launches a sample
        (density / 48000); ENVINC: 1 / (grain length in samples), 0 for no grains."""
        pitch, ginc, envinc = f32(pitch), f32(ginc), f32(envinc)
        spray, prand = f32(spray), f32(prand)
        size = len(self.buf)
        out = np.zeros(n, f32)
        for s in range(n):
            self.gphase = f32(self.gphase + ginc)
            if self.gphase >= f32(1):
                self.gphase = f32(self.gphase - f32(1))
                if envinc > f32(0):
                    self.launch(read, pitch, spray, prand, envinc)
            acc = f32(0)
            for g in self.g:
                if not g["on"]:
                    continue
                if g["e"] >= f32(1):
                    g["on"] = 0
                    continue
                i0 = g["pi"]
                i1 = i0 + 1 if i0 + 1 < size else 0
                s0 = self.buf[i0]
                v = f32(s0 + f32(g["pf"] * f32(self.buf[i1] - s0)))
                x = f32(g["e"] * f32(WIN_LEN))
                e0 = int(np.trunc(x))
                ef = f32(x - f32(e0))
                w0 = self.win[e0]
                w = f32(w0 + f32(ef * f32(self.win[e0 + 1] - w0)))
                acc = f32(acc + f32(f32(v * GRAIN_AMP) * w))
                pf = f32(g["pf"] + g["df"])
                pi_ = i0 + g["di"]
                if pf >= f32(1):
                    pf = f32(pf - f32(1))
                    pi_ += 1
                if pi_ >= size:
                    pi_ -= size
                g["pf"], g["pi"] = pf, pi_
                g["e"] = f32(g["e"] + g["ei"])
            out[s] = acc
        ms = self.ms
        for v in out:
            ms = f32(f32(RMS_B * ms) + f32(RMS_C * f32(v * v)))
        self.ms = ms
        gn = f32(RMS_CEIL * rsqrt(np.array([f32(ms + EPS_PREV)]))[0])
        gn = min(gn, f32(1))
        dg = f32(f32(gn - self.gain) * f32(1.0 / n))
        gc = self.gain
        for s in range(n):
            gc = f32(gc + dg)
            out[s] = f32(out[s] * gc)
        self.gain = gn
        return out


# ================================================================================ the voice
SR = 48000
CONTROLS = ("TUNE", "SPD", "BLND", "SAMP", "STRT", "SIZE", "DENS", "OVLP",
            "SPRY", "PRND", "WIN", "LEV")
DEFAULTS = dict(TUNE=64, SPD=80, BLND=0, SAMP=0, STRT=0, SIZE=127, DENS=64, OVLP=64,
                SPRY=0, PRND=0, WIN=3, LEV=100)
WIN_NAMES = ("GAUS", "BHAR", "EXPO", "TRI", "RAMP", "SINC", "RECT")
MIN_LOOP = 64


def _speed(k: int) -> float:
    """SPD 0..127: 64 is 0 (frozen); +-4 at the ends; within 0.06 of +-1 it is +-1 (80, 48)."""
    s = (k - 64) / 63.0 * 4.0
    if abs(abs(s) - 1.0) < 0.06:
        s = math.copysign(1.0, s)
    return s


def _tables():
    from . import model as M
    t = {}
    t["SPD"] = np.array([_speed(k) for k in range(128)], f32)
    b = np.array([M.law_blend(k / 127) for k in range(128)], f32)
    t["VG"], t["PG"], t["GG"] = b[:, 0].copy(), b[:, 1].copy(), b[:, 2].copy()
    gf = np.array([M.law_density(k / 127) for k in range(128)])
    t["GINC"] = (gf / SR).astype(f32)
    t["GLEN"] = np.where(gf < 4, 4.0, 6.0) * 1000.0 / gf       # ms at full overlap, less 1
    t["GLEN"] = t["GLEN"].astype(f32)
    t["SQ"] = ((np.arange(128) / 127.0) ** 2).astype(f32)      # OVLP, SPRY, PRND, SIZE
    t["LEV"] = (np.arange(128) / 100.0).astype(f32)
    t["WIN"] = [M.WINDOWS[n][::M.WIN_LEN // WIN_LEN].astype(f32) for n in WIN_NAMES]
    return t


import math  # noqa: E402

TABLES = _tables()


def recip(x: f32) -> f32:
    """1/x for x >= 1: the seed 0x7ef311c7 - bits, then three Newton steps (FASCIA's)."""
    x = f32(x)
    r = np.array([0x7EF311C7 - int(np.array([x], f32).view(np.uint32)[0])], np.uint32).view(f32)[0]
    for _ in range(3):
        r = f32(r * f32(f32(2.0) - f32(x * r)))
    return r


class Voice:
    """A whole SMEAR voice, block by block (32 samples), float32.

    The read point is an integer sample and a fraction in [0, 1). The speed is split the
    same way (floor and remainder), so a long buffer keeps its precision. It moves sample
    by sample and wraps within the loop [lstart, lstart + lsize).
    - VOC reads at the hop's first block's read point.
    - GRN reads at each block's.
    - PLAY reads every sample (linear interpolation) and moves the read point.
    - A path whose BLND gain is 0 is not computed.

    `block(k, tr, trig, clock, lane)`:
    - K: the knobs;
    - TR: the pitch ratio, the note and TUNE together (the sampler's `tr`), times the
      sample's rate against 48 kHz;
    - RATE: that rate alone, which scales the speed;
    - CLOCK: the instrument's block count;
    - LANE: the VOC lane this voice holds (0, 1 or None). The hop's job is
      (CLOCK + 8 x LANE) mod 16, so the two lanes' heavy jobs never meet."""

    def __init__(self, buf, rate: float = 1.0):
        self.buf = np.asarray(buf, f32)
        self.rate = f32(rate)
        self.voc = Voc(self.buf)
        self.grn = Grn(self.buf, TABLES["WIN"][3])
        self.pi, self.pf = 0, f32(0)

    def loop(self, k):
        size = len(self.buf)
        lstart = int(np.trunc(f32(f32(k["STRT"] * f32(1 / 128)) * f32(size))))
        lsize = int(np.trunc(f32(TABLES["SQ"][k["SIZE"]] * f32(size - lstart))))
        return lstart, max(lsize, MIN_LOOP)

    def trig(self, k):
        self.pi, self.pf = self.loop(k)[0], f32(0)
        self.voc.reset()

    def block(self, k: dict, tr: float = 1.0, trig: bool = False, clock: int = 0,
              lane: int | None = 0) -> np.ndarray:
        if trig:
            self.trig(k)
        T = TABLES
        pitch = f32(tr)
        spd = f32(T["SPD"][k["SPD"]] * self.rate)
        si = int(np.floor(spd))
        sf = f32(spd - f32(si))
        lstart, lsize = self.loop(k)
        lend = lstart + lsize
        vg, pg, gg = T["VG"][k["BLND"]], T["PG"][k["BLND"]], T["GG"][k["BLND"]]
        y = np.zeros(32, f32)                         # y = 0, + vg voc, + gg grn, + pg play, x lev
        if vg > 0 and lane is not None:
            y = y + vg * self.voc.block(float(self.pi), float(pitch), (clock + 8 * lane) & 15)
        if gg > 0:
            ov = T["SQ"][k["OVLP"]]
            ms = f32(min(f32(f32(ov * T["GLEN"][k["DENS"]]) + f32(1)), f32(8000)))
            envinc = recip(f32(ms * f32(48)))
            self.grn.win = T["WIN"][min(k["WIN"] * 7 >> 7, 6)]
            y = y + gg * self.grn.block(self.pi, pitch, T["GINC"][k["DENS"]], envinc,
                                        T["SQ"][k["SPRY"]], T["SQ"][k["PRND"]])
        size = len(self.buf)
        for s in range(32):
            if pg > 0:
                i0 = self.pi % size
                i1 = i0 + 1 if i0 + 1 < size else 0
                s0 = self.buf[i0]
                y[s] = f32(y[s] + f32(pg * f32(s0 + f32(self.pf * f32(self.buf[i1] - s0)))))
            pf = f32(self.pf + sf)
            pi = self.pi + si
            if pf >= f32(1):
                pf = f32(pf - f32(1))
                pi += 1
            while pi >= lend:
                pi -= lsize
            while pi < lstart:
                pi += lsize
            self.pi, self.pf = pi, pf
        return (y * TABLES["LEV"][k["LEV"]]).astype(f32)


class Lanes:
    """The two VOC lanes: a note takes a free one, else the one taken longest ago."""

    def __init__(self, n: int = 2):
        self.owner: list = [None] * n
        self.when = [0] * n
        self.t = 0

    def take(self, voice) -> int:
        self.t += 1
        for k, o in enumerate(self.owner):
            if o is voice:
                self.when[k] = self.t
                return k
        k = next((k for k, o in enumerate(self.owner) if o is None),
                 min(range(len(self.owner)), key=lambda k: self.when[k]))
        self.owner[k], self.when[k] = voice, self.t
        return k

    def held(self, voice):
        return next((k for k, o in enumerate(self.owner) if o is voice), None)

    def free(self, voice):
        for k, o in enumerate(self.owner):
            if o is voice:
                self.owner[k] = None
