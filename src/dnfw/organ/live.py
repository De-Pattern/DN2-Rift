"""ORGAN on the SHARC's arithmetic: ref.py (Ravel's C, bit for bit) with every variable divide
made the SHARC's way, a multiply by FASCIA's `recip` (the seed 0x7ef311c7 - bits and three
Newton steps), and the two constant divides (by 20 and by 3) multiplies by their float32
reciprocals. Nothing else differs: the divides are all once a block, so the samples' arithmetic
is ref.py's exactly. This is the SHARC program's contract (bit-exact, test_organ_program);
test_organ_live holds it to ref.py within a tolerance.
"""
from __future__ import annotations

import numpy as np

from ..fascia.live import recip as _recip
from ..fascia.live import INV127

F = np.float32


def recip(x):
    return F(_recip(F(x)))


INV20 = F(F(1.0) / F(20.0))
INV3 = F(F(1.0) / F(3.0))
I32 = np.int32
FS = 48000
DT = F(1.0) / F(48000.0)              # RV_DT
NYQ = F(24000.0)
SUB = 32
LOG2E = F(1.44269504088896)
TWO_PI = F(6.28318530717958647692)    # FM_TWO_PI
CHIFF_FLOOR = F(1e-30)               # the chiff's decay is ended here (the SHARC flushes denormals)
# RIFT v0.5, page 3 (owner, 2026-11-16: attack and tone, "do not change the core sounds"): every new
# control at 0 leaves v0.4's voice bit for bit (test_organ_live). Their constants:
CEL_STEP = F(0.125)                  # CELESTE's rank fades in and out over 8 blocks (5.3 ms): no click
KC_COEF = F(0.9917013)               # the key click's decay a sample: exp(-1 / (48000 x 2.5 ms))
KC_TIME = F(0.0125)                  # the key click sounds while the voice is this young
ROT_SLEW = F(1.4)                    # the rotor's speed follows RSPD with a 0.7 s lag (its inertia)
# page 4 (the owner's flute clip, 2026-11-16: the jet's turbulence inside the tone, a 28..50 Hz flutter,
# a downward voice-break with a component at half the pitch 3..8 dB under the note, the breath
# blooming into the tone over seconds): the jet (filtered noise once a block), its constants
J_CLIP = F(3.0)
BK_UP, BK_DOWN = F(0.15), F(0.03)    # the break's envelope: quick in, slower out (a block)


# -- rv_math.h ------------------------------------------------------------------------------------
def floorf(x):
    t = F(int(np.int32(np.trunc(x)))) if abs(float(x)) < 2.1e9 else F(np.trunc(x))
    return F(t - F(1.0)) if t > x else t


def exp2f(x):
    x = F(x)
    if x < F(-126.0):
        return F(0.0)
    if x > F(127.0):
        x = F(127.0)
    n = floorf(x)
    f = F(x - n)
    p = F(0.000218775048)
    p = F(F(p * f) + F(0.00123878215))
    p = F(F(p * f) + F(0.00968458045))
    p = F(F(p * f) + F(0.0554804263))
    p = F(F(p * f) + F(0.240230502))
    p = F(F(p * f) + F(0.693146929))
    p = F(F(p * f) + F(1.0))
    s = np.array([(int(n) + 127) << 23], dtype=np.uint32).view(np.float32)[0]
    return F(p * s)


def expf(x):
    return exp2f(F(F(x) * LOG2E))


def _sin_half(x):
    x2 = F(x * x)
    p = F(-2.50521084e-8)
    p = F(F(p * x2) + F(2.75573192e-6))
    p = F(F(p * x2) - F(1.98412698e-4))
    p = F(F(p * x2) + F(8.33333333e-3))
    p = F(F(p * x2) - F(1.66666667e-1))
    return F(x + F(F(x * x2) * p))


def _sin_r(r):
    r = F(r)
    if r > F(0.25):
        r = F(F(0.5) - r)
    elif r < F(-0.25):
        r = F(F(-0.5) - r)
    return _sin_half(F(r * TWO_PI))


def sin_turns(ph):
    return _sin_r(F(ph - floorf(F(ph + F(0.5)))))


def sinf(x):
    k = floorf(F(F(F(x) * F(0.159154943)) + F(0.5)))
    r = F(F(F(x) - F(k * F(6.28125))) - F(k * F(1.93530718e-3)))
    return _sin_r(F(r * F(0.159154943)))


def cosf(x):
    return sinf(F(F(x) + F(1.57079633)))


def tanf(x):
    c = cosf(x)
    if abs(c) < F(1e-7):
        c = F(-1e-7) if c < F(0.0) else F(1e-7)
    return F(sinf(x) * recip(c))


def sqrtf(x):
    x = F(x)
    if x <= F(0.0):
        return F(0.0)
    u = int(np.array([x], dtype=np.float32).view(np.uint32)[0])
    y = np.array([(0x1FBD1DF5 + (u >> 1)) & 0xFFFFFFFF], dtype=np.uint32).view(np.float32)[0]
    for _ in range(3):
        y = F(F(0.5) * F(y + F(x * recip(y))))
    return y


def clampf(x, lo, hi):
    return x if (x > lo and x < hi) else (hi if x > lo else lo)


def clampi(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


# -- rv_dsp.h -------------------------------------------------------------------------------------
def xs32(s):
    x = s if s else 0x2545F491
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x, x


def xs_bi(st):
    st[0], v = xs32(st[0])
    return F(F(np.int32(np.uint32(v).view(np.int32))) * F(1.0 / 2147483648.0))


def note_hz(n):
    return F(F(440.0) * exp2f(F(F(F(n) - F(69.0)) * F(F(1.0) / F(12.0)))))


class SVF:
    __slots__ = ("ic1", "ic2", "g", "k", "a1", "a2", "a3")

    def __init__(self):
        self.ic1 = self.ic2 = self.g = self.k = self.a1 = self.a2 = self.a3 = F(0.0)

    def set(self, hz, q):
        hz = clampf(F(hz), F(10.0), F(NYQ * F(0.9)))
        g = tanf(F(F(F(3.14159265) * hz) * DT))
        self.g = g
        self.k = F(F(1.0) / (F(0.05) if q < F(0.05) else F(q)))
        self.a1 = recip(F(F(1.0) + F(g * F(g + self.k))))
        self.a2 = F(g * self.a1)
        self.a3 = F(g * self.a2)

    def tick_bp(self, x):
        v3 = F(x - self.ic2)
        v1 = F(F(self.a1 * self.ic1) + F(self.a2 * v3))
        v2 = F(F(self.ic2 + F(self.a2 * self.ic1)) + F(self.a3 * v3))
        self.ic1 = F(F(F(2.0) * v1) - self.ic1)
        self.ic2 = F(F(F(2.0) * v2) - self.ic2)
        return v1


# -- the pipes (rv_organ.h, generated by Ravel's tools/gen_organ.py) ---------------------------
ORG_N = 256
STOPS = ("FLUTE", "NACHTHORN", "PRINCIPAL", "GAMBA", "TRUMPET")
GAIN = [F(v) for v in (1.0, 1.05, 1.5, 2.4, 2.4)]
RATIO = [F(v) for v in (0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 1.0)]


def tables() -> np.ndarray:
    """org_tab[5][3][256], as committed (tables.json, from Ravel's rv_organ.h)."""
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).with_name("tables.json")).read_text(encoding="utf-8"))
    return np.array(d["org_tab"], dtype=np.int64)


def load_tables(path) -> np.ndarray:
    """org_tab[5][3][256] from Ravel's rv_organ.h."""
    import re
    src = open(path, encoding="utf-8").read()
    body = src[src.index("org_tab[ORG_STOPS][3][ORG_N] = {"):]
    rows = re.findall(r"\{([-0-9,\s]+)\}", body)
    vals = [[int(v) for v in r.replace("\n", " ").split(",") if v.strip()] for r in rows[:15]]
    t = np.array(vals, dtype=np.int64).reshape(5, 3, ORG_N)
    assert t.min() >= -128 and t.max() <= 127
    return t


class Organ:
    """One voice's organ_t (rv_int.h) and its two functions. eff: the 16 knobs as floats."""

    def __init__(self, tables: np.ndarray, rng: int):
        self.tab = tables
        self.ph = [F(0.0)] * 8
        self.dly = [F(0.0)] * 8
        self.cents = [F(0.0)] * 8
        self.t = self.chiff = self.air_lp = self.wind = self.wind_v = self.trem_ph = F(0.0)
        self.ch = SVF()
        self.ns = [0]
        self.rng = rng & 0xFFFFFFFF
        # v0.5, page 3: the percussion, the key click (its own noise: the pipes' stream is untouched),
        # the mixture's two pipes, the rotor, CELESTE's fade, the note's velocity
        self.pe = self.pph = self.kc = self.kprev = self.rph = self.rhz = self.rlp = self.cel_g = F(0.0)
        self.rs = F(0.0)
        self.mph = [F(0.0), F(0.0)]
        self.kns = [0]
        self.pvel = F(1.0)
        # page 4: the jet (its noise, two lowpass stages), the break, the half-pitch phase, the
        # darkening's lowpass, the edge's SVF
        self.jns = [0]
        self.jv1 = self.jv2 = self.bk = self.hph = self.blp = F(0.0)
        self.j = self.press = self.dep = self.tot = F(0.0)
        self.ed = SVF()

    def note(self, eff, vel=F(1.0)) -> None:
        e = [F(v) for v in eff] + [F(0.0)] * (32 - len(eff))     # Ravel's 16: pages 3 and 4 at 0
        spread = F(e[10] * F(F(0.035) / F(127.0)))
        wind = F(e[12] * F(F(4.0) / F(127.0)))
        if not self.ns[0]:
            self.ns[0] = self.rng | 1
        self.t = F(0.0)
        self.chiff = F(1.0)
        for k in range(8):
            self.dly[k] = F(spread * F(F(xs_bi(self.ns) * F(0.5)) + F(0.5)))
            self.cents[k] = F(F(wind * F(0.5)) * xs_bi(self.ns))
            self.ph[k] = F(F(xs_bi(self.ns) * F(0.5)) + F(0.5))
        # v0.5: page 3's strike (no draw from the pipes' noise)
        if not self.kns[0]:
            self.kns[0] = ((self.rng + 0x3C6EF372) & 0xFFFFFFFF) | 1
        if not self.jns[0]:
            self.jns[0] = ((self.rng + 0x7F4A7C15) & 0xFFFFFFFF) | 1
        self.hph = F(0.0)
        self.pe = self.kc = F(1.0)
        self.pph = self.kprev = F(0.0)
        self.mph = [F(0.0), F(0.0)]
        self.cel_g = F(1.0) if F(e[15] * F(F(14.0) / F(127.0))) > F(0.01) else F(0.0)
        self.pvel = F(vel)

    def render(self, eff, f, n: int = SUB) -> np.ndarray:
        e = [F(v) for v in eff] + [F(0.0)] * (32 - len(eff))     # Ravel's 16: pages 3 and 4 at 0
        f = F(f)
        stop = clampi(int(np.int32(F(e[0] + F(0.5)))), 0, 4)
        speech = F(F(0.01) * exp2f(F(e[9] * F(F(3.9) / F(127.0)))))
        dt = F(F(n) * DT)
        chiff = F(e[8] * F(F(1.0) / F(127.0)))
        air = F(e[11] * F(F(0.06) / F(127.0)))
        wind = F(e[12] * F(F(1.0) / F(127.0)))
        trem = F(e[13] * F(F(1.0) / F(127.0)))
        trem_hz = F(F(3.0) * exp2f(F(e[14] * F(F(1.6) / F(127.0)))))
        celeste = F(e[15] * F(F(14.0) / F(127.0)))
        tot, onset = F(0.0), F(0.0)
        idx, lvl, inc, share = [], [], [], []
        self.wind_v = F(self.wind_v + F(F(F(xs_bi(self.ns) - self.wind_v) * dt) * F(3.0)))
        self.wind = F(self.wind + F(F(F(self.wind_v - self.wind) * dt) * F(1.5)))
        self.trem_ph = F(self.trem_ph + F(trem_hz * dt))
        self.trem_ph = F(self.trem_ph - floorf(self.trem_ph))
        tr = F(trem * sin_turns(self.trem_ph))
        wob = F(self.wind * wind)
        # v0.5: CELESTE's rank fades in or out (8 blocks), no longer a step
        if celeste > F(0.01):
            if self.cel_g < F(1.0):
                self.cel_g = F(self.cel_g + CEL_STEP)
                if self.cel_g > F(1.0):
                    self.cel_g = F(1.0)
        elif self.cel_g > F(0.0):
            self.cel_g = F(self.cel_g - CEL_STEP)
            if self.cel_g < F(0.0):
                self.cel_g = F(0.0)
        # v0.5: the rotor (ROTR, RSPD): its speed with inertia, its phase, the pipes' Doppler
        rot = F(e[22] * F(F(1.0) / F(127.0)))
        rotc = F(0.0)
        self.rs = F(0.0)
        if rot > F(0.0):
            target = F(F(0.6) * exp2f(F(e[23] * F(F(3.55) / F(127.0)))))
            if self.rhz <= F(0.0):
                self.rhz = target
            else:
                self.rhz = F(self.rhz + F(F(F(target - self.rhz) * dt) * ROT_SLEW))
            self.rph = F(self.rph + F(self.rhz * dt))
            self.rph = F(self.rph - floorf(self.rph))
            self.rs = sin_turns(self.rph)
            rotc = F(F(rot * F(8.0)) * sin_turns(F(self.rph + F(0.25))))
        # v0.5, page 4: the jet's turbulence (BRTH, TURB), the pressure (PRES, PVEL), the break (BREK)
        b = F(e[24] * F(F(1.0) / F(127.0)))
        brk = F(e[26] * F(F(1.0) / F(127.0)))
        edge = F(e[30] * F(F(1.0) / F(127.0)))
        press = F(F(e[28] * F(F(1.0) / F(127.0))) + F(F(e[31] * F(F(1.0) / F(127.0))) * F(self.pvel - F(0.5))))
        press = clampf(press, F(0.0), F(1.0))
        self.press = press
        self.j = F(0.0)
        if b > F(0.0) or brk > F(0.0) or edge > F(0.0):
            fc = F(F(1.5) * exp2f(F(e[25] * F(F(5.3) / F(127.0)))))
            a = F(F(fc * TWO_PI) * dt)
            if a > F(1.0):
                a = F(1.0)
            self.jv1 = F(self.jv1 + F(F(xs_bi(self.jns) - self.jv1) * a))
            self.jv2 = F(self.jv2 + F(F(self.jv1 - self.jv2) * a))
            self.j = clampf(F(F(self.jv2 * sqrtf(recip(a))) * F(3.5)), F(-J_CLIP), J_CLIP)
        rotc = F(rotc + F(F(F(b * F(50.0)) * self.j) + F(press * F(15.0))))
        if brk > F(0.0):
            tgt = clampf(F(F(F(self.j + F(press * F(1.5))) - F(F(2.2) - F(brk * F(2.4)))) * F(2.0)), F(0.0), F(1.0))
            self.bk = F(self.bk + F(F(tgt - self.bk) * (BK_UP if tgt > self.bk else BK_DOWN)))
        else:
            self.bk = F(0.0)
        self.dep = F(self.bk * F(F(0.35) + F(e[27] * F(F(1.0) / F(127.0)))))
        for k in range(8):
            if k < 7:
                lv = F(e[1 + k] * F(F(1.0) / F(127.0)))
            else:
                lv = F(F(e[2] * F(F(0.8) / F(127.0))) * self.cel_g) if self.cel_g > F(0.0) else F(0.0)
            age = F(self.t - self.dly[k])
            sp = F(speech * F(F(1.0) - F(F(k if k < 7 else 1) * F(0.07))))
            if lv < F(0.002):
                continue
            g = F(0.0) if age <= F(0.0) else F(F(1.0) - expf(F(F(-age) * recip(sp))))
            cents = F(F(F(F(F(self.cents[k] - F(F(F(1.0) - g) * F(18.0))) + F(wob * F(3.0))) + F(tr * F(6.0)))
                      + (celeste if k == 7 else F(0.0))) + rotc)
            fr = F(F(f * RATIO[k]) * exp2f(F(cents * F(F(1.0) / F(1200.0)))))
            if fr > F(F(0.45) * F(FS)):
                continue
            idx.append(k)
            lvl.append(F(F(lv * g) * F(F(F(1.0) + F(tr * F(0.22))) + F(wob * F(0.03)))))
            inc.append(F(F(fr * DT) * F(ORG_N)))
            room = F(F(F(0.45) * F(FS)) * recip(fr))
            if room >= F(24.0):
                sh = F(0.0)
            elif room >= F(4.0):
                sh = F(F(F(24.0) - room) * INV20)
            else:
                sh = F(F(1.0) + clampf(F(F(F(4.0) - room) * INV3), F(0.0), F(1.0)))
            share.append(sh)
            tot = F(tot + lv)
            onset = F(onset + g)
        nr = len(idx)
        tot = F(F(F(0.55) * recip(sqrtf(tot)) if tot > F(1.0) else F(0.55)) * GAIN[stop])
        self.tot = tot
        self.ch.set(F(f * F(3.0)) if F(f * F(3.0)) < F(9000.0) else F(9000.0), F(5.0))
        yb = [F(0.0)] * n
        for j in range(nr):
            r = idx[j]
            lo = 0 if share[j] < F(1.0) else 1
            sh = F(share[j] - F(lo))
            ph, dp, lv = self.ph[r], inc[j], lvl[j]
            ta, tb = self.tab[stop][lo], self.tab[stop][lo + 1]
            for i in range(n):
                ph = F(ph + dp)
                if ph >= F(ORG_N):
                    ph = F(ph - F(ORG_N))
                i0 = int(ph)
                fr = F(ph - F(i0))
                i1 = (i0 + 1) & (ORG_N - 1)
                a = F(F(int(ta[i0])) + F(F(int(ta[i1] - ta[i0])) * fr))
                if sh > F(0.001):
                    b = F(F(int(tb[i0])) + F(F(int(tb[i1] - tb[i0])) * fr))
                    a = F(a + F(F(b - a) * sh))
                yb[i] = F(yb[i] + F(a * lv))
            self.ph[r] = ph
        out = np.zeros(n, dtype=np.float32)
        ons = F(onset * recip(F(nr))) if nr else F(0.0)
        for i in range(n):
            y = yb[i]
            ns = xs_bi(self.ns)
            y = F(y * F(F(1.0) / F(127.0)))
            bp = self.ch.tick_bp(ns)
            self.air_lp = F(self.air_lp + F(F(ns - self.air_lp) * F(0.08)))
            y = F(y + F(F(F(F(bp * chiff) * self.chiff) * F(0.5))
                        + F(F(self.air_lp * air) * F(F(0.3) + F(F(0.7) * ons)))))
            out[i] = F(y * tot)
            self.chiff = F(self.chiff * F(0.9992))
            if self.chiff < CHIFF_FLOOR:       # past it the SHARC would meet denormals (about 2.3 s)
                self.chiff = F(0.0)
        self.t = F(self.t + dt)
        return out

    def post(self, y, eff, f) -> np.ndarray:
        """v0.5, page 3, after the level and TRIM: the percussion, the key click and the mixture
        (summed, x 0.45 and the velocity's gain), the velocity's gain on all, then the rotor. Every
        control at 0 returns Y untouched."""
        e = [F(v) for v in eff] + [F(0.0)] * (32 - len(eff))     # Ravel's 16: pages 3 and 4 at 0
        f = F(f)
        y = np.array(y, dtype=np.float32)
        n = len(y)
        stop = clampi(int(np.int32(F(e[0] + F(0.5)))), 0, 4)
        perc = F(e[16] * F(F(0.9) / F(127.0)))
        pon = False
        if perc > F(0.0):
            pf = F(f * (F(3.0) if e[18] >= F(1.0) else F(2.0)))
            pon = pf < F(F(0.45) * F(FS))
            pinc = F(pf * DT)
            tau = F(F(0.04) * exp2f(F(e[17] * F(F(5.2) / F(127.0)))))
            pcoef = expf(F(F(-DT) * recip(tau)))
        else:
            self.pe = F(0.0)
        kk = F(e[19] * F(F(0.48) / F(127.0)))
        if self.t > KC_TIME:
            self.kc = F(0.0)
        kon = kk > F(0.0) and self.kc > F(0.0)
        mix = []
        if e[21] > F(0.0):
            for j, (ratio, gain) in enumerate(((F(6.0), F(0.55)), (F(16.0), F(0.35)))):
                fr = F(f * ratio)
                if fr < F(F(0.42) * F(FS)):
                    mix.append((j, F(F(fr * DT) * F(ORG_N)), F(F(e[21] * F(gain / F(127.0))) * F(F(1.0) / F(127.0)))))
        xon = pon or kon or bool(mix)
        von = e[20] > F(0.0)
        vg = F(F(1.0) - F(F(e[20] * F(F(1.0) / F(127.0))) * F(F(1.0) - self.pvel))) if von else F(1.0)
        rot = F(e[22] * F(F(1.0) / F(127.0)))
        if rot > F(0.0):
            am = F(F(1.0) - F(F(rot * F(0.3)) * F(F(0.5) + F(F(0.5) * self.rs))))
            rsw = F(F(rot * F(0.5)) * F(F(0.5) - F(F(0.5) * self.rs)))
        ta = self.tab[stop][1]
        # page 4
        b = F(e[24] * F(F(1.0) / F(127.0)))
        edge = F(e[30] * F(F(1.0) / F(127.0)))
        if b > F(0.0):
            lfl = F(F(1.0) + F(F(b * F(0.45)) * self.j))
            if lfl < F(0.0):
                lfl = F(0.0)
            bdark = F(F(b * F(0.5)) * clampf(F(F(0.5) - F(F(0.5) * self.j)), F(0.0), F(1.0)))
        blon = e[29] > F(0.0)
        if blon:
            tb = F(F(0.03) * exp2f(F(e[29] * F(F(6.7) / F(127.0)))))
            gb = F(F(1.0) - expf(F(F(-self.t) * recip(tb))))
        eon = edge > F(0.0) or blon
        if eon:
            eg = F(edge * F(2.0))
            if blon:
                eg = F(eg + F(F(F(1.0) - gb) * F(1.2)))
            eg = F(F(F(eg * F(F(1.0) + F(F(b * F(0.5)) * self.j))) * self.tot) * TRIM)
            self.ed.set(f, F(6.0))
        hon = self.dep > F(0.0)
        if hon:
            hinc = F(F(f * F(0.5)) * DT)
            hn = recip(F(F(1.0) + F(self.dep * F(0.5))))
        for i in range(n):
            v = y[i]
            if xon:
                x = F(0.0)
                if pon:
                    x = F(x + F(F(sin_turns(self.pph) * self.pe) * perc))
                    self.pph = F(self.pph + pinc)
                    self.pph = F(self.pph - floorf(self.pph))
                    self.pe = F(self.pe * pcoef)
                    if self.pe < CHIFF_FLOOR:
                        self.pe = F(0.0)
                if kon:
                    nz = xs_bi(self.kns)
                    x = F(x + F(F(F(nz - self.kprev) * self.kc) * kk))
                    self.kprev = nz
                    self.kc = F(self.kc * KC_COEF)
                for j, inc, lv in mix:
                    ph = F(self.mph[j] + inc)
                    if ph >= F(ORG_N):
                        ph = F(ph - F(ORG_N))
                    self.mph[j] = ph
                    i0 = int(ph)
                    fr = F(ph - F(i0))
                    i1 = (i0 + 1) & (ORG_N - 1)
                    a = F(F(int(ta[i0])) + F(F(int(ta[i1] - ta[i0])) * fr))
                    x = F(x + F(a * lv))
                v = F(v + F(F(x * F(0.45)) * vg))
            if von:
                v = F(v * vg)
            if b > F(0.0):
                v = F(v * lfl)
            if blon:
                v = F(v * gb)
            if hon:
                v = F(F(v * F(F(1.0) + F(self.dep * sin_turns(self.hph)))) * hn)
                self.hph = F(self.hph + hinc)
                self.hph = F(self.hph - floorf(self.hph))
            if b > F(0.0):
                self.blp = F(self.blp + F(F(v - self.blp) * F(0.12)))
                v = F(v + F(bdark * F(self.blp - v)))
            if eon:
                v = F(v + F(self.ed.tick_bp(xs_bi(self.jns)) * eg))
            if rot > F(0.0):
                self.rlp = F(self.rlp + F(F(v - self.rlp) * F(0.15)))
                v = F(F(v * am) + F(rsw * F(self.rlp - v)))
            y[i] = v
        return y


# -- the DN2's voice (the SHARC program's contract, dnfw.organ.program) --------------------------
# ORGAN's sixteen controls ride FASCIA's records (a track is one machine or the other; docs/organ.md):
# STOP on WAV1's 0..120 choice record (FASCIA's TYPA), the fifteen others on 0..127 records with a
# stock CC where one is free (FASCIA's HARD, TUNE, DAMP, DEC, MORPH, FORM, SHIFT, LPG, CHAR, CLIK,
# WATR, FOLD, SIDE) and FM Tone's DUST, TZFM. The panel's order is Ravel's knob order.
CONTROLS = ("STOP", "R16", "R8", "R4", "R223", "R2", "R135", "R1",
            "CHIFF", "SPEECH", "SPREAD", "AIR", "WIND", "TREM", "TRATE", "CELESTE",
            "PERC", "PDEC", "PHRM", "KCLK", "VELO", "MIXT", "ROTR", "RSPD",     # v0.5: page 3
            "BRTH", "TURB", "BREK", "BDEP", "PRES", "BLOM", "EDGE", "PVEL")     # v0.5: page 4
RIDES = ("TYPA", "HARD", "TUNE", "DAMP", "DEC", "MORPH", "FORM", "SHIFT",
         "LPG", "CHAR", "CLIK", "WATR", "FOLD", "SIDE", "DUST", "TZFM",
         "BEND", "MIX", "TYPB", "GEOM", "MATL", "POS", "COUP", "RING",
         "BUZZ", "BODA", "BODB", "CTYP", "XMOD", "ATK", "FDBK", "VARY")     # FASCIA's control each rides
PHRM = 18                             # page 3's choice: the percussion's harmonic, 2ND or 3RD
TRIM = F(0.519)                       # Ravel's per-engine trim (rv_synth.c): ORGAN at FASCIA's level
MAGIC = 0x4F524721                    # 'ORG!': the voice's state was written by a strike


def knob_of(word: int, top: int) -> int:
    """a record word -> 0..127, as FASCIA's read_frame (dnfw.fascia.machines.knob)"""
    v = min(max(((word & 0xFFFF) >> 8), 0), top)
    if top == 127:
        return v
    return int(F(F(F(v) * F(254.0 / (200 if top == 100 else 240))) + F(0.502)))


# v0.5: an ORGAN sound made in v0.4 holds stock's record defaults on the 16 records pages 3 and 4
# ride (MACHINE SEL and TRK + CLEAR reset the sound to them and v0.4 wrote only its own 16; v0.4
# had no page, LFO or lock that could move them). That exact set reads as pages 3 and 4 at 0, so
# the organ sounds as it did; the ColdFire puts v0.5's defaults on both pages at their first turn
# (fmt.c org_legacy). The words: FM Tone's 0x4000s, WAV2's 0, the PD and OFS records' 0x3200.
LEGACY_WORDS = (0x4000, 0x4000, 0x0000, 0x4000, 0x4000, 0x4000, 0x4000, 0x4000,
                0x4000, 0x3200, 0x3200, 0x3200, 0x3200, 0x0000, 0x0000, 0x0000)
LEGACY_TOPS = (127, 127, 120, 127, 127, 127, 127, 127, 127, 100, 100, 100, 100, 127, 127, 127)
LEGACY = tuple(knob_of(w, t) for w, t in zip(LEGACY_WORDS, LEGACY_TOPS))


def eff_of(knobs) -> list:
    """the knobs (0..127 ints) -> Ravel's eff: STOP is its option 0..4 ((k 5) >> 7), PHRM its
    option 0..1 ((k 2) >> 7), the rest the knob itself; pages 3 and 4 all 0 on a v0.4 sound"""
    e = [F(int(k)) for k in knobs]
    e[0] = F(min((int(knobs[0]) * 5) >> 7, 4))
    e[PHRM] = F(min((int(knobs[PHRM]) * 2) >> 7, 1))
    if tuple(int(k) for k in knobs[16:32]) == LEGACY:
        e[16:32] = [F(0.0)] * 16
    return e


def fade_ramp() -> np.ndarray:
    """a steal's fade over one block: 1 - (i + 1) / 32"""
    return np.array([F(F(1.0) - F(F(i + 1) * F(1.0 / SUB))) for i in range(SUB)], dtype=np.float32)


class Voice:
    """one slot's ORGAN voice, block by block: a trig arms it, a sounding voice fades over one
    block first (the steal), the strike is Ravel's organ_note, and it plays until the next note
    (as the Monomachine's machines: the DN2's amp envelope shapes what is heard). A non-finite
    output rests the voice and clears its state (it is written again at the next strike)."""

    def __init__(self, tables: np.ndarray, slot: int):
        self.tab, self.slot = tables, slot
        self.on = self.pending = self.fading = 0
        self.pnote = F(0.0)
        self.pvel = F(1.0)
        self.f = F(0.0)
        self.org = None

    def block(self, knobs, trig: bool, note: float, vel: int = 127) -> np.ndarray:
        """VEL: the trig's velocity, 0..127 (the frame's header word 52 + 2t, >> 8)"""
        e = eff_of(knobs)
        if trig:
            self.pnote = F(note)
            self.pvel = F(F(min(max(int(vel), 0), 127)) * INV127)
            self.pending = 1
            self.fading = self.on
        if self.fading and self.on:
            y = self.org.post(self.org.render(e, self.f) * TRIM, e, self.f) * fade_ramp()
            self.fading = self.on = 0
            return self._check(y.astype(np.float32))
        if self.pending:
            self.pending = 0
            n = self.pnote if np.isfinite(self.pnote) else F(0.0)
            self.f = note_hz(n)
            if self.org is None:
                self.org = Organ(self.tab, 0x2545F491 + self.slot)
            self.org.note(e, self.pvel)
            self.on = 1
        if not self.on:
            return np.zeros(SUB, dtype=np.float32)
        return self._check(self.org.post((self.org.render(e, self.f) * TRIM).astype(np.float32), e, self.f))

    def _check(self, y):
        if not np.all(np.isfinite(y)):
            self.on = self.fading = 0
            self.org = None
            return np.zeros(SUB, dtype=np.float32)
        return y
