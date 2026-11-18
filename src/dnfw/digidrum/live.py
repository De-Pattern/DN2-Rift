"""DIGIDRUM's voice on the SHARC's arithmetic: float32 after every operation, Ravel's rv_math leaves
(organ.live: recip, exp2f, expf, sin_turns, note_hz, xs_bi), no tanh, no pow, no division. The SHARC
program will be held to this bit for bit, as RIFT's other machines are.

The sound is model.py's (v2, the owner's ear, 2026-11-18), rebuilt in that arithmetic. These are the
differences from the model:
- every envelope is a one-pole decay, multiplied in sample by sample, its coefficient from expf once
  a note (or once a block where a knob sets it);
- tanh is a rational soft clip, `sat` (Pade, exact at 0 and odd), clamped at +-1 beyond |x| = 3;
- noise is Ravel's bipolar xorshift (uniform), not a Gaussian;
- powers become squares (SD BASIC's ratio: 1 + 4 INHM^2, the model's INHM^1.5) or exp2f of a
  log2 (SD VINTAGE's mode tilt);
- the clap's hits keep their uneven gaps, with fixed small offsets in place of the model's random
  jitter; its crunch is the soft clip driven harder, not |x|^0.4;
- no normalisation to a peak (that needs the whole hit): each type has a fixed output gain, set so
  its defaults peak near the model's 0.8 (`GAIN`).

**Controls** (knobs 0..127). Page 1: TYPE TUNE PNCH DEC, then the type's own four (model.OWN).
Page 2: OVER and Machinedrum-style tone shaping: EQF EQG (a peaking EQ), AMD AMF (amplitude
modulation), FLTF FLTW (a base/width band filter: a high-pass at the base, a low-pass the width
above it), and LEV. 
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, DT, recip, exp2f, expf, sin_turns, note_hz, xs_bi

FS = 48000
SUB = 32
TYPES = ("BD MODERN", "SD BASIC", "SD VINTAGE", "CP VINTAGE", "CY ALLOY", "PC CARBON")
OWN = {"BD MODERN": ("SWEP", "SMOD", "TMOD", "MENV"),
       "SD BASIC": ("SWEP", "INHM", "MDFB", "MENV"),
       "SD VINTAGE": ("SWEP", "INHM", "FCMP", "MENV"),
       "CP VINTAGE": ("SPCR", "BAL", "BODY", "BENV"),
       "CY ALLOY": ("SHIM", "RADIO", "MOD", "MENV"),
       "PC CARBON": ("SWEP", "INHM", "MOD", "MENV")}
BASE_NOTE = {"BD MODERN": 31, "SD BASIC": 50, "SD VINTAGE": 50, "CP VINTAGE": 60, "CY ALLOY": 72,
             "PC CARBON": 60}
GAIN = {"BD MODERN": F(0.74), "SD BASIC": F(0.74), "SD VINTAGE": F(0.74), "CP VINTAGE": F(0.74),
        "CY ALLOY": F(0.74), "PC CARBON": F(0.74)}
INV127 = F(F(1.0) / F(127.0))
INV2PI = F(0.159154943)
LN_60DB = F(6.9078)
IDLE = F(1.0e-5)
SD_MODES = (1.0, 1.59, 2.14, 2.30, 2.65, 2.92, 3.16, 3.50)
CY_RATIOS = (1.0, 1.483, 1.932, 2.546, 2.630, 3.897)
CP_GAPS = (1.0, 1.18, 1.35)
CP_JIT = (0, 19, -13, 23)                  # samples: the hands never land on the grid
CP_LV = (F(0.75), F(0.9), F(0.8), F(1.0))


def sat(x):
    """tanh's stand-in: x (27 + x^2) / (27 + 9 x^2), +-1 beyond |x| = 3"""
    x = F(x)
    if x >= F(3.0):
        return F(1.0)
    if x <= F(-3.0):
        return F(-1.0)
    x2 = F(x * x)
    return F(F(x * F(F(27.0) + x2)) * recip(F(F(27.0) + F(F(9.0) * x2))))


def decay(t):
    """the one-pole coefficient a sample for an e-fold time of T seconds"""
    return expf(F(F(0.0) - recip(F(F(t) * F(FS)))))


def t60(t):
    """the coefficient for a T60 (to -60 dB) of T seconds"""
    return expf(F(F(0.0) - F(LN_60DB * recip(F(F(t) * F(FS))))))


def wrap1(x):
    """a phase kept in [0, 1): one subtraction (every increment is under a turn)"""
    return F(x - F(1.0)) if x >= F(1.0) else x


def square(x):
    """the sign of sin(2 pi x): +1 or -1"""
    return F(1.0) if sin_turns(x) >= F(0.0) else F(-1.0)


def triangle(r):
    """r in [0, 1): -1 at 0, +1 at 0.5"""
    return F(F(F(4.0) * r) - F(1.0)) if r < F(0.5) else F(F(3.0) - F(F(4.0) * r))


class Bp:
    """a two-pole resonator: v = x + c a1 - r^2 a2, out (1 - r) v"""

    def __init__(self, fc, r):
        self.c = F(F(F(2.0) * F(r)) * sin_turns(F(F(F(fc) * DT) + F(0.25))))
        self.r2 = F(F(r) * F(r))
        self.g = F(F(1.0) - F(r))
        self.a1 = self.a2 = F(0.0)

    def __call__(self, x):
        v = F(F(F(x) + F(self.c * self.a1)) - F(self.r2 * self.a2))
        self.a2, self.a1 = self.a1, v
        return F(v * self.g)


class Svf:
    """the TPT state-variable filter (organ.live's, all three outputs); `set` once a block"""

    def __init__(self):
        self.ic1 = self.ic2 = F(0.0)
        self.k = self.a1 = self.a2 = self.a3 = F(0.0)

    def set(self, hz, k):
        hz = min(max(F(hz), F(10.0)), F(21600.0))
        t = F(F(hz * DT) * F(0.5))                                        # tan(pi hz / fs) ...
        g = F(sin_turns(t) * recip(sin_turns(F(t + F(0.25)))))            # ... as sin / cos
        self.k = F(k)
        self.a1 = recip(F(F(1.0) + F(g * F(g + self.k))))
        self.a2 = F(g * self.a1)
        self.a3 = F(g * self.a2)

    def tick(self, x):
        """-> (lp, bp, hp)"""
        v3 = F(x - self.ic2)
        v1 = F(F(self.a1 * self.ic1) + F(self.a2 * v3))
        v2 = F(F(self.ic2 + F(self.a2 * self.ic1)) + F(self.a3 * v3))
        self.ic1 = F(F(F(2.0) * v1) - self.ic1)
        self.ic2 = F(F(F(2.0) * v2) - self.ic2)
        return v2, v1, F(F(x - F(self.k * v1)) - v2)


PAGE2 = ("OVER", "EQF", "EQG", "AMD", "AMF", "FLTF", "FLTW", "LEV")
PAGE2_DEFAULTS = {"OVER": 0, "EQF": 64, "EQG": 64, "AMD": 0, "AMF": 64, "FLTF": 0, "FLTW": 127, "LEV": 100}
SQRT2_INV = F(0.70710678)


class Tone:
    """page 2, after the drum (the Machinedrum's order: EQ, then the base/width filter, then AM):
    - EQF the peak's note (k + 24: 41 Hz .. 13 kHz), EQG its gain, +-15 dB at 0 / 127 (64 flat), Q 1;
    - FLTF the base (a high-pass at note k: 8 Hz at 0, open), FLTW the width above it in semitones,
      where a low-pass sits (127: open);
    - AMD the depth of a sine tremolo, AMF its rate (0.1 .. 100 Hz, exponential);
    - LEV the level, 1.0 at 100."""

    def __init__(self):
        self.eq, self.hp, self.lp = Svf(), Svf(), Svf()
        self.am = F(0.0)

    def set(self, k: dict):
        g = F(F(F(k.get("EQG", 64) - 64) * F(15.0 / 64.0)) * F(0.166096405))     # dB -> log2 of amplitude
        self.eq_g = F(exp2f(g) - F(1.0))
        self.eq_on = k.get("EQG", 64) != 64
        self.eq.set(note_hz(F(k.get("EQF", 64) + 24)), F(1.0))
        f = k.get("FLTF", 0)
        self.hp_on = f > 0
        self.hp.set(note_hz(F(f)), SQRT2_INV * F(2.0))
        top = f + k.get("FLTW", 127)
        self.lp_on = top < 135
        self.lp.set(note_hz(F(top)), SQRT2_INV * F(2.0))
        self.amd = F(F(k.get("AMD", 0)) * INV127)
        self.amf = F(F(0.1) * exp2f(F(F(F(k.get("AMF", 64)) * INV127) * F(9.97))))   # 0.1 .. 100 Hz
        self.lev = F(F(k.get("LEV", 100)) * F(F(1.0) / F(100.0)))

    def tick(self, x):
        if self.eq_on:
            _, bp, _ = self.eq.tick(x)
            x = F(x + F(self.eq_g * bp))
        if self.hp_on:
            x = self.hp.tick(x)[2]
        if self.lp_on:
            x = self.lp.tick(x)[0]
        if self.amd > F(0.0):
            m = F(F(0.5) + F(F(0.5) * sin_turns(self.am)))
            x = F(x * F(F(1.0) - F(self.amd * m)))
            self.am = wrap1(F(self.am + F(self.amf * DT)))
        return F(x * self.lev)


class Voice:
    """one DIGIDRUM voice. A trig starts a hit of the type and knobs at that moment; the type's own
    knobs and DEC are read at the trig (a hit is one gesture), PNCH, OVER and page 2 every block.
    The pitch is the type's base note + (TUNE - 64) + (the played note - 60), so C4 plays the
    drum at its own pitch and the keyboard tunes it; VEL is the trig's velocity / 127."""

    def __init__(self, slot: int = 0):
        self.slot = slot
        self.on = False
        self.rng = [0x2545F491 + slot]
        self.tone = Tone()

    def trig(self, k: dict, note: float | None, vel: float = 1.0):
        ty = TYPES[min(k["TYPE"] * len(TYPES) >> 7, len(TYPES) - 1)]
        self.ty, self.on, self.n = ty, True, 0
        q = {c: F(F(k.get(c, 64)) * INV127) for c in ("PNCH", "DEC", "OVER", *OWN[ty])}
        self.q = q
        nt = F(60.0) if note is None else F(note)
        self.f0 = note_hz(F(F(F(BASE_NOTE[ty]) + F(k.get("TUNE", 64) - 64)) + F(nt - F(60.0))))
        self.vel = F(vel)
        dec = F(F(0.02) * exp2f(F(q["DEC"] * F(9.0))))              # 20 ms .. 10 s
        self.amp, self.amp_k = F(1.0), t60(dec)
        self.pb, self.pb_k = F(1.0), decay(F(0.035))               # PNCH's accent
        self.ph = [F(0.0)] * 8
        self.prev = F(0.0)
        if ty == "BD MODERN":
            self.ph[1] = F(0.25)
            sw = q["SWEP"]
            self.sw, self.sw_k = F(F(9.0) * sw), decay(F(F(0.006) + F(F(0.07) * sw)))
            m = q["MENV"]
            self.me, self.me_k = F(F(0.2) + F(F(0.8) * m)), decay(F(F(0.004) + F(F(0.3) * m)))
            self.smod = F(F(F(q["SMOD"] * q["SMOD"]) * F(1.6)) * INV2PI)
            self.tmod = F(F(F(q["TMOD"] * q["TMOD"]) * F(2.2)) * INV2PI)
            self.sub, self.sub_k = F(0.55), decay(F(F(0.12) + F(F(0.5) * dec)))
            self.clk, self.clk_k = F(0.35), decay(F(0.0015))
            self.amp_k = t60(F(dec * F(1.3)))
        elif ty in ("SD BASIC", "PC CARBON"):
            sw = q["SWEP"]
            self.sw, self.sw_k = F(F(2.5) * sw), decay(F(F(0.003) + F(F(0.03) * sw)))
            i = q["INHM"]
            self.ratio = (F(F(1.0) + F(F(4.0) * F(i * i))) if ty == "SD BASIC"
                          else F(F(1.41) + F(F(5.3) * i)))
            mod = q["MDFB"] if ty == "SD BASIC" else q["MOD"]
            self.idx = F(F(mod * F(8.0)) * INV2PI)
            self.fb = F(F((q["MDFB"] if ty == "SD BASIC" else F(0.3)) * F(1.2)) * INV2PI)
            self.me, self.me_k = F(1.0), decay(F(F(0.003) + F(F(0.25) * q["MENV"])))
            if ty == "SD BASIC":
                self.nz, self.nz_k = F(F(0.866) * q["MDFB"]), decay(F(F(0.02) + F(F(0.15) * q["DEC"])))
        elif ty == "SD VINTAGE":
            self.sw, self.sw_k = q["SWEP"], decay(F(0.02))
            spread = F(F(0.6) + F(F(0.8) * q["INHM"]))
            tilt = F(F(1.5) - F(F(1.3) * q["FCMP"]))
            self.modes = []
            for j, r in enumerate(SD_MODES):
                rr = F(F(1.0) + F(F(F(r) - F(1.0)) * spread))
                amp = exp2f(F(tilt * F(-np.log2(1 + j))))           # (1 / (1 + j)) ^ tilt
                self.modes.append([rr, F(amp * F(0.4)), F(1.0), t60(F(dec * F(F(1.0) - F(F(0.08) * F(j)))))])
            b = F(F(0.5) + F(F(0.5) * q["MENV"]))
            self.wire, self.wire_k = F(F(0.6) * b), decay(F(F(0.03) + F(F(0.25) * q["MENV"])))
            self.lp = F(0.0)
        elif ty == "CP VINTAGE":
            sp = q["SPCR"]
            gap = F(F(0.0045) + F(F(0.020) * min(sp, F(0.5))))
            at, t = [0], F(0.0)
            for g in CP_GAPS:
                t = F(t + F(gap * F(g)))
                at.append(int(np.trunc(F(t * F(FS)))))
            self.hit_at = [a + j for a, j in zip(at, CP_JIT)]
            self.hit_k = [decay(F(F(0.0028) + F(F(0.002) * F(j)))) for j in range(4)]
            self.hit_e = [F(0.0)] * 4
            self.tail_at = self.hit_at[-1]
            self.tail, self.tail_k = F(0.0), decay(F(F(0.045) + F(dec * F(0.35))))
            tf = exp2f(F(F(k.get("TUNE", 64) - 64) * F(F(1.0) / F(12.0))))
            bright = F(F(0.6) + F(F(0.4) * self.vel))
            self.crack = Bp(F(F(F(1250.0) * tf) * F(F(0.85) + F(F(0.3) * bright))), F(0.94))
            self.slap = Bp(F(F(F(2600.0) * tf) * bright), F(0.90))
            self.diff = Bp(F(F(900.0) * tf), F(0.88))
            self.tail_lv = F(F(5.0) * F(F(0.5) + F(F(0.5) * self.vel)))
            self.crunch = F(F(sp - F(0.5)) * F(2.0)) if sp > F(0.5) else F(0.0)
            bod = q["BODY"]
            self.bidx = F(F(F(1.0) + F(F(4.0) * bod)) * INV2PI)
            self.bratio = F(F(1.0) + F(F(2.0) * bod))
            self.benv, self.benv_k = F(1.0), decay(F(F(0.01) + F(F(0.3) * q["BENV"])))
            self.bal = q["BAL"]
        elif ty == "CY ALLOY":
            self.fa = F(self.f0 * F(F(1.0) + F(F(3.0) * q["RADIO"])))
            self.fb = F(self.f0 * F(F(1.37) + F(F(4.0) * q["SHIM"])))
            self.me, self.me_k = F(1.0), decay(F(F(0.01) + F(F(0.5) * q["MENV"])))
            self.cmod = F(F(q["MOD"] * F(6.0)) * INV2PI)
            self.hx = self.hy = F(0.0)

    def sample(self) -> F:
        ty, n = self.ty, self.n
        if ty == "BD MODERN":
            f = F(self.f0 * F(F(1.0) + self.sw))
            d = F(f * DT)
            self.ph[0] = wrap1(F(self.ph[0] + d))                 # the body
            self.ph[1] = wrap1(F(self.ph[1] + F(d * F(1.5))))     # the triangle's (from a quarter)
            self.ph[2] = wrap1(F(self.ph[2] + F(d * F(0.5))))     # the sub's
            p = self.ph[0]
            sq = F(F(square(F(p * F(2.0))) * self.smod) * self.me)
            tr = F(F(triangle(self.ph[1]) * self.tmod) * self.me)
            body = sin_turns(F(F(p + sq) + tr))
            sub = F(sin_turns(F(self.ph[2] + F(0.25))) * self.sub)
            click = F(xs_bi(self.rng) * self.clk)
            y = F(F(F(body + sub) * self.amp) + click)
            self.sw = F(self.sw * self.sw_k)
            self.me = F(self.me * self.me_k)
            self.sub = F(self.sub * self.sub_k)
            self.clk = F(self.clk * self.clk_k)
        elif ty in ("SD BASIC", "PC CARBON"):
            f = F(self.f0 * F(F(1.0) + self.sw))
            self.ph[1] = wrap1(F(self.ph[1] + F(F(f * self.ratio) * DT)))
            m = sin_turns(F(self.ph[1] + F(self.fb * self.prev)))
            self.prev = m
            self.ph[0] = wrap1(F(self.ph[0] + F(f * DT)))
            y = sin_turns(F(self.ph[0] + F(F(self.idx * self.me) * m)))
            if ty == "SD BASIC":
                y = F(F(F(0.7) * y) + F(xs_bi(self.rng) * self.nz))
                self.nz = F(self.nz * self.nz_k)
            y = F(y * self.amp)
            self.sw = F(self.sw * self.sw_k)
            self.me = F(self.me * self.me_k)
        elif ty == "SD VINTAGE":
            s = F(F(1.0) + self.sw)
            y = F(0.0)
            for j, md in enumerate(self.modes):
                self.ph[j] = wrap1(F(self.ph[j] + F(F(F(self.f0 * md[0]) * s) * DT)))
                y = F(y + F(F(sin_turns(self.ph[j]) * md[1]) * md[2]))
                md[2] = F(md[2] * md[3])
            x = xs_bi(self.rng)
            self.lp = F(self.lp + F(F(0.35) * F(x - self.lp)))
            y = F(y + F(F(x - self.lp) * self.wire))
            self.wire = F(self.wire * self.wire_k)
            self.sw = F(self.sw * self.sw_k)
            self.amp = F(1.0)                   # each mode has its own decay
        elif ty == "CP VINTAGE":
            h = F(0.0)
            for j in range(4):
                if n == self.hit_at[j]:
                    self.hit_e[j] = CP_LV[j]
                h = F(h + self.hit_e[j])
                self.hit_e[j] = F(self.hit_e[j] * self.hit_k[j])
            if n == self.tail_at:
                self.tail = F(1.0)
            x = xs_bi(self.rng)
            cr, sl = self.crack(x), self.slap(x)
            df = self.diff(xs_bi(self.rng))
            clap = F(F(F(7.0) * F(F(cr + F(F(0.6) * sl)) * h)) + F(F(df * self.tail) * self.tail_lv))
            self.tail = F(self.tail * self.tail_k)
            if self.crunch > F(0.0):
                clap = F(F(F(F(1.0) - self.crunch) * clap) + F(self.crunch * sat(F(clap * F(4.0)))))
            self.ph[0] = wrap1(F(self.ph[0] + F(self.f0 * DT)))
            self.ph[1] = wrap1(F(self.ph[1] + F(F(self.f0 * self.bratio) * DT)))
            body = F(sin_turns(F(self.ph[0] + F(self.bidx * sin_turns(self.ph[1])))) * self.benv)
            self.benv = F(self.benv * self.benv_k)
            y = F(F(F(F(1.0) - self.bal) * clap) + F(self.bal * body))
            y = F(y * self.amp)
        else:                                   # CY ALLOY
            m = F(self.cmod * self.me)
            s = F(0.0)
            self.ph[0] = wrap1(F(self.ph[0] + F(self.fa * DT)))
            self.ph[1] = wrap1(F(self.ph[1] + F(self.fb * DT)))
            for r in CY_RATIOS:
                r = F(r)
                s = F(s + square(F(F(self.ph[0] * r) + F(m * sin_turns(F(self.ph[1] * r))))))
            self.me = F(self.me * self.me_k)
            self.hy = F(F(0.9) * F(F(self.hy + s) - self.hx))
            self.hx = s
            y = F(F(self.hy * F(F(1.0) / F(6.0))) * self.amp)
        self.amp = F(self.amp * self.amp_k) if ty != "SD VINTAGE" else self.amp
        self.n = n + 1
        return y

    def block(self, k: dict, trig: bool = False, note: float | None = None, vel: float = 1.0):
        if trig:
            self.trig(k, note, vel)
        out = np.zeros(SUB, dtype=np.float32)
        if not self.on:
            return out
        pn = F(F(k.get("PNCH", 30)) * INV127)
        ov = F(F(k.get("OVER", 0)) * INV127)
        g_over = F(F(1.0) + F(F(20.0) * F(ov * ov)))
        n_over = recip(F(sat(g_over) * F(1.0)))
        drive = F(F(1.0) + F(F(2.0) * pn))
        n_pn = recip(sat(drive))
        gain = GAIN[self.ty]
        self.tone.set(k)
        peak = F(0.0)
        for i in range(SUB):
            y = self.sample()
            if pn > F(0.0):
                bump = F(F(1.0) + F(F(F(2.5) * pn) * self.pb))
                y = F(sat(F(F(y * bump) * drive)) * n_pn)
            self.pb = F(self.pb * self.pb_k)
            y = F(y * self.vel)
            if ov > F(0.0):
                y = F(sat(F(y * g_over)) * n_over)
            y = self.tone.tick(F(y * gain))
            out[i] = y
            peak = max(peak, F(abs(y)))
        if self.n > 4800 and peak < IDLE:
            self.on = False
        return out


def render(type_: str, secs: float = 1.2, note=None, vel: float = 1.0, **kn) -> np.ndarray:
    """a whole hit (for auditions and tests)"""
    k = {"TYPE": int(TYPES.index(type_) * 128 // len(TYPES) + 5), "TUNE": 64, "PNCH": 30, "DEC": 64,
         "OVER": 0}
    for c in OWN[type_]:
        k[c] = 64
    k.update(kn)
    v = Voice()
    n = int(secs * FS) // SUB
    return np.concatenate([v.block(k, trig=(b == 0), note=note, vel=vel) for b in range(n)])
