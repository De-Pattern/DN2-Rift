"""SMEAR (working name): a granular, phase-vocoded, stretchy looper sample machine, loosely
after Qu-Bit's Nebulae v2 (owner, 2026-11-18: queue item 2, "GRID and WERP first").

This is the float64 reference model for the owner's ear, not yet the DSP contract. It is a
transcription of the owner's own MIT pedal port (De-Pattern/Nebulae-Granular_Looper_Pedal,
src/nebulae_dsp.cpp, itself a transcription of QB_Nebulae_V2's `a_granularlooper.instr`):

- **VOC**: Csound's `mincer` (FFT 2048, 4x overlap, hop 512, phase-locked): the read point
  and the pitch are independent, so a sound stretches without changing pitch, and pitches
  without changing speed.
- **GRN**: `partikkel`'s subset: up to 10 grains at once, density 0.12..2500 Hz, overlap
  (grain size against density), spray (position scatter) and pitch randomisation per grain,
  a window bank, an RMS limiter (0.20).
- A constant-power BLEND, VOC <-> PLAY <-> GRN (PLAY is the plain read at SPEED, the
  pedal's dry).

What changes on the Digitone (a machine voice, not a pedal):
- The buffer is a sample slot or a FLEX buffer, not a live 120 s recording.
- A trig starts the read phase at START (the pedal's reset); the note (and TUNE) set PITCH,
  so it plays chromatically; SPEED is the read rate over the loop (+1 = as recorded, 0 =
  frozen, negative = backwards), detented at +-1 as on the pedal.
- 48 kHz, a 32-sample block: the vocoder's frame (2 forward FFTs, 1 inverse) must be spread
  over a hop's 16 blocks on the SHARC (docs/smear.md, the cost).
"""

from __future__ import annotations

import math

import numpy as np

SR = 48000
FFT_N = 2048
DECIM = 4
HOP = FFT_N // DECIM
WIN_LEN = 512
MAX_GRAINS = 10
GRAIN_AMP = 0.45
RMS_CEIL = 0.20


# ---------------------------------------------------------------------------- windows
def windows() -> dict[str, np.ndarray]:
    n = WIN_LEN
    i = np.arange(n + 1)
    out = {}
    h = n >> 1
    x = np.concatenate([-6.0 + np.arange(h) * 12.0 / n, np.arange(n + 1 - h) * 12.0 / n])
    out["GAUS"] = np.exp(-(x * x) / 2.0)
    a = 2 * math.pi * i / n
    out["BHAR"] = 0.35878 - 0.48829 * np.cos(a) + 0.14128 * np.cos(2 * a) - 0.01168 * np.cos(3 * a)
    m = n // 16
    e = np.empty(n + 1)
    e[:m] = 0.001 * 1000.0 ** (np.arange(m) / (m - 1))
    e[m:] = 0.001 ** (np.arange(n + 1 - m) / (n - m))
    e[0] = e[-1] = 0.0
    out["EXPO"] = e
    out["TRI"] = np.where(i < h, i * 2.0 / n, 2.0 - i * 2.0 / n)
    r = np.zeros(n + 1)
    k = 15 * n // 16
    r[:k] = np.arange(k) / k
    r[k:] = 1.0 - np.arange(n + 1 - k) / (n + 1 - k)
    out["RAMP"] = r
    xs = -math.pi + i * 2 * math.pi / n
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.where(np.abs(xs) < 1e-9, 1.0, np.sin(xs) / xs)
    out["SINC"] = s
    out["RECT"] = np.ones(n + 1)
    return out


WINDOWS = windows()
WIN_NAMES = ("GAUS", "BHAR", "EXPO", "TRI", "RAMP", "SINC", "RECT")


# ---------------------------------------------------------------------------- control laws
def law_speed(g: float) -> float:
    """SPEED 0..1 -> -4..+4, detented at +-1 (the pedal's LawSpeed)."""
    k = g * 8.0 - 4.0
    if 0.975 <= abs(k) <= 1.025:
        k = math.copysign(1.0, k)
    return k


def law_density(g: float) -> float:
    t = (math.tanh(g * 2 - 1) + 0.8) * 0.4
    u = g * 2 - 1
    c = (u ** 3 + 1) * 0.5
    s = t * 0.25 + c * 0.75
    return math.exp(s * (math.log(2500.0) - math.log(0.12)) + math.log(0.12))


def law_grain_ms(overlap: float, gf: float) -> float:
    sc = min(max(overlap * overlap, 0.0), 1.0)
    maxpw = 4.0 if gf < 4 else 6.0
    return min(sc * (1.0 / gf) * maxpw * 1000.0 + 1.0, 8000.0)


def law_blend(g: float) -> tuple[float, float, float]:
    """BLEND 0..1 -> (voc, play, grain), constant power: VOC at 0, PLAY at the middle, GRN at 1."""
    if 0.48 <= g <= 0.52:
        g = 0.5
    g = 0.0 if g < 0.01 else 1.0 if g > 0.99 else g
    df = min(max(abs(g * 4 - 2) - 1, -1.0), 1.0)
    vf = min(g * 4 - 1, 1.0)
    gf = max(g * 4 - 3, -1.0)
    return (min(max(math.sqrt(max(0.5 * (1 - vf), 0)), 0), 1),
            math.sqrt(max(0.5 * (1 - df), 0)),
            min(max(math.sqrt(max(0.5 * (1 + gf), 0)), 0), 1))


# ---------------------------------------------------------------------------- the engines
def _read(buf: np.ndarray, pos: np.ndarray) -> np.ndarray:
    n = len(buf)
    p = np.mod(pos, n)
    i0 = np.floor(p).astype(np.int64)
    fr = p - i0
    return buf[i0] + fr * (buf[(i0 + 1) % n] - buf[i0])


class Mincer:
    """Phase-locked phase vocoder: `time` (samples, per output sample) is the read point."""

    def __init__(self):
        self.win = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(FFT_N) / FFT_N)
        self.prev = np.zeros(FFT_N // 2 + 1, complex)
        self.ola = np.zeros(FFT_N + HOP)
        self.cnt = HOP

    def process(self, buf, time, pitch, n):
        out = np.empty(n)
        size = len(buf)
        scaling = (8.0 / DECIM) / 3.0
        s = 0
        while s < n:
            if self.cnt == HOP:
                spos = HOP * int(time[s] / HOP)
                spos = (spos - 1) % size + 1
                pf = spos + pitch * np.arange(FFT_N)
                f = np.fft.rfft(_read(buf, pf) * self.win)
                b = np.fft.rfft(_read(buf, pf - HOP * pitch) * self.win)
                pn = self.prev / (np.abs(self.prev) + 1e-20)
                d = np.conj(b) * pn                      # phase(prev) - phase(b)
                lk = d.copy()
                lk[1:-1] += d[:-2] + d[2:]               # phase lock: the neighbours' sum
                lk[0] = (d[0] + d[1]).real
                lk[-1] = (d[-1] + d[-2]).real
                lk = lk + 1e-15
                u = lk / np.abs(lk)
                o = f * u
                self.prev = o
                fr = np.fft.irfft(o, FFT_N) * self.win
                self.ola[:FFT_N] += fr
                self.cnt = 0
            take = min(HOP - self.cnt, n - s)
            out[s:s + take] = self.ola[:take] * scaling
            self.ola = np.concatenate([self.ola[take:], np.zeros(take)])
            self.cnt += take
            s += take
        return out


class Granular:
    def __init__(self, seed=0x1234567):
        self.rng = np.random.default_rng(seed)
        self.gphase = 0.0
        self.grains: list[list] = []           # [pos, delta, envphase, envinc, order]
        self.order = 0
        self.rms = 0.0
        self.gprev = 1.0
        self.b = math.exp(-2 * math.pi * 10.0 / SR)

    def process(self, buf, ppos, gfreq, gms, pitch, window, n, spray=0.0, prand=0.0):
        tab = len(buf)
        out = np.zeros(n)
        ginc = gfreq / SR
        wavfreq = pitch / (tab / SR)
        dur = SR * gms / 1000.0
        # launches in this block
        ph = self.gphase + ginc * np.arange(1, n + 1)
        launches = np.nonzero(np.floor(ph) > np.floor(np.concatenate([[self.gphase], ph[:-1]])))[0]
        self.gphase = ph[-1] - math.floor(ph[-1])
        starts = {}
        for s in launches:
            if dur < 1:
                continue
            if len(self.grains) >= MAX_GRAINS:
                self.grains.sort(key=lambda g: g[4])
                self.grains.pop(0)
            p = ppos[s]
            if spray > 1e-4:
                p = abs(p + self.rng.uniform(-1, 1) * spray * spray)
                p -= math.floor(p)
            else:
                p = min(max(p, 0.0), 1.0)
            dl = (wavfreq / SR) * tab
            if prand > 1e-4:
                dl *= 2 ** (self.rng.uniform(-1, 1) * prand * prand * 120.0 / 1200.0)
            self.order += 1
            g = [p * tab, dl, 0.0, 1.0 / dur, self.order]
            self.grains.append(g)
            starts[id(g)] = s
        keep = []
        for g in self.grains:
            s0 = starts.get(id(g), 0)
            m = n - s0
            k = np.arange(m)
            env_ph = g[2] + g[3] * k
            live = env_ph < 1.0
            m2 = int(live.sum())
            if m2:
                sm = _read(buf, g[0] + g[1] * k[:m2])
                ei = env_ph[:m2] * WIN_LEN
                e0 = np.floor(ei).astype(int)
                ef = ei - e0
                e1 = np.minimum(e0 + 1, WIN_LEN)
                en = window[e0] + ef * (window[e1] - window[e0])
                out[s0:s0 + m2] += sm * GRAIN_AMP * en
            g[0] += g[1] * m
            g[2] += g[3] * m
            if g[2] < 1.0:
                keep.append(g)
        self.grains = keep
        # the RMS limiter, block rate (the pedal's)
        acc = self.rms
        for v in out:
            acc = self.b * acc + (1 - self.b) * v * v
        self.rms = acc
        r = math.sqrt(acc)
        gn = min(r, RMS_CEIL) / r if r > 1e-12 else 1.0
        ramp = self.gprev + (gn - self.gprev) * np.arange(1, n + 1) / n
        self.gprev = gn
        return out * ramp


# ---------------------------------------------------------------------------- a voice
class Voice:
    """One SMEAR voice over `buf` (float, mono). Controls are 0..1 like the pedal's pots,
    except pitch (a ratio) and the window (a name)."""

    BLOCK = 32

    def __init__(self, buf: np.ndarray):
        self.buf = np.asarray(buf, float)
        self.voc = Mincer()
        self.grn = Granular()
        self.phase = 0.0

    def trig(self):
        self.phase = 0.0
        self.voc = Mincer()

    def render(self, seconds, *, speed=0.625, pitch=1.0, start=0.0, size=1.0, blend=0.0,
               density=0.5, overlap=0.5, spray=0.0, prand=0.0, window="TRI", ctl=None):
        """`ctl(t)` may return a dict overriding any control at time t (for sweeps)."""
        n_total = int(seconds * SR)
        out = np.zeros(n_total)
        blen = len(self.buf)
        for b0 in range(0, n_total, self.BLOCK):
            c = dict(speed=speed, pitch=pitch, start=start, size=size, blend=blend,
                     density=density, overlap=overlap, spray=spray, prand=prand, window=window)
            if ctl:
                c.update(ctl(b0 / SR))
            n = min(self.BLOCK, n_total - b0)
            spd = law_speed(c["speed"])
            lstart = c["start"] * blen
            lsize = max(c["size"] ** 2 * (blen - lstart), 2.0)
            inc = spd / lsize
            ph = self.phase + inc * np.arange(1, n + 1)
            ph -= np.floor(ph)
            self.phase = ph[-1]
            tpos = lstart + ph * lsize
            ppos = tpos / blen
            vg, dg, gg = law_blend(c["blend"])
            y = np.zeros(n)
            if vg > 1e-4:
                y += vg * self.voc.process(self.buf, tpos, c["pitch"], n)
            if dg > 1e-4:
                y += dg * _read(self.buf, tpos)
            if gg > 1e-4:
                gf = law_density(c["density"])
                y += gg * self.grn.process(self.buf, ppos, gf, law_grain_ms(c["overlap"], gf),
                                           c["pitch"], WINDOWS[c["window"]], n,
                                           c["spray"], c["prand"])
            a = np.abs(y)
            hot = a > 0.9
            y[hot] = np.sign(y[hot]) * (0.9 + 0.1 * np.tanh((a[hot] - 0.9) / 0.1))
            out[b0:b0 + n] = y
        return out


def speed_knob(ratio: float) -> float:
    """The SPEED control (0..1) that gives a read rate `ratio` (-4..+4)."""
    return (ratio + 4.0) / 8.0
