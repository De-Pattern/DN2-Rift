"""RESON: eight resonant bands as an insert, ported from the owner's Viscera (vsc_engine.c,
reson() and reson_control(), Viscera 1.1.3, github.com/De-Pattern/viscera).

What changed for the DN2, and nothing else:
- 48 kHz, one instance per voice (the insert runs per voice, docs/fx-platform.md), mono;
- the modulator is the voice itself (SELF), its own output (OUTPUT), or Viscera's OSC/NOISE;
  INPUT and PARTNER have no meaning per voice;
- pings come from the detector (HIGH, FULL, LOW) and from NOTES: the voice's note start;
  QUANT and HITS (Viscera's listener) are not here;
- the CPU guard's relief steps are the DN2 guard's business (it skips the insert, dry);
- Viscera's fast exp2/log2/sqrt/tan approximations are exact functions here: this is the
  reference model; the DSP port's float32 live model will fix its own arithmetic.

The panel (an INSERT page of eight, MIX on FX page 1):
    PROF MODE RESO WDTH  /  SHFT LIQ  DUST DROP
PROF loads one of Viscera's six profiles (rprof, vsc_ui.c); the knobs then move what they name.
Values are Viscera's 0..127.
"""
from __future__ import annotations

import math

import numpy as np

from .common import RATE, ULAW, njit, ulaw_enc, xorshift

# the parameter vector's layout (Viscera's G_B* order, without TRACK and QUANT)
NAMES = (["MODE", "RESO", "MIX", "WIDTH"] + [f"G{b}" for b in range(8)] + [f"F{b}" for b in range(8)]
         + [f"D{b}" for b in range(8)]
         + ["SHIFT", "LIQ", "FDBK", "SPEC", "VMOD", "OSC", "ATK", "REL", "DEPTH",
            "TRIG", "SENS", "HARD", "DUST", "COHES", "DROP", "MIGR"])
IX = {n: i for i, n in enumerate(NAMES)}

MODES = ("OFF", "FILTER", "VOCODE", "PING", "HYBRID")
TRIGS = ("OFF", "HIGH", "FULL", "LOW", "NOTES")
VMODS = ("SELF", "OSC", "NOISE", "OUTPUT")

# vsc_params.c's defaults: LIQUID MEMORY
DEFAULTS = dict(MODE=4, RESO=66, MIX=83, WIDTH=76,
                **{f"G{b}": v for b, v in enumerate((38, 110, 38, 30, 30, 34, 103, 30))},
                **{f"F{b}": 64 for b in range(8)},
                **{f"D{b}": v for b, v in enumerate((78, 64, 50, 41, 35, 26, 20, 11))},
                SHIFT=64, LIQ=44, FDBK=10, SPEC=64, VMOD=0, OSC=40, ATK=18, REL=54, DEPTH=72,
                TRIG=1, SENS=90, HARD=89, DUST=0, COHES=80, DROP=0, MIGR=20)

# vsc_ui.c's rprof: each profile is the defaults with these changed
_G = lambda *v: {f"G{b}": x for b, x in enumerate(v)}  # noqa: E731
PROFILES = {
    "LIQ MEM": {},
    "GLASS": {**_G(25, 30, 25, 25, 40, 99, 105, 97), "RESO": 41, "HARD": 120, "MIX": 90, "WIDTH": 90,
              "LIQ": 30, "DUST": 30, "COHES": 90},
    "THROAT": {"MODE": 2, "G0": 100, "G1": 108, "G2": 104, "G3": 96, "G6": 40, "VMOD": 3, "DEPTH": 100,
               "ATK": 30, "REL": 70, "RESO": 50, "WIDTH": 50, "MIX": 85, "LIQ": 20, "TRIG": 0},
    "DUST": {"MODE": 3, "DUST": 70, "COHES": 40, "RESO": 100, **_G(85, 95, 90, 88, 92, 86, 95, 84),
             "DROP": 40, "MIGR": 50, "MIX": 100, "TRIG": 2},
    "RADIO": {"MODE": 1, "WIDTH": 20, "LIQ": 0, **_G(40, 60, 105, 105, 105, 105, 50, 40), "MIX": 75,
              "RESO": 30, "TRIG": 0},
    "DROPS": {"DROP": 50, "MIGR": 20, "DUST": 15, "COHES": 100, "FDBK": 12},
}
PROFILE_NAMES = tuple(PROFILES)

# the DN2 page
PAGE = ("PROF", "MODE", "RESO", "WDTH", "SHFT", "LIQ", "DUST", "DROP")
_PAGE_TO = {"RESO": "RESO", "WDTH": "WIDTH", "SHFT": "SHIFT", "LIQ": "LIQ", "DUST": "DUST", "DROP": "DROP"}


def params(prof: str | int = "LIQ MEM", **knobs) -> np.ndarray:
    """The parameter vector: a profile, then the page's knobs (and MIX) over it.
    MODE may be a name; any Viscera name (G0, D3, FDBK...) may be given too."""
    if isinstance(prof, int):
        prof = PROFILE_NAMES[prof]
    v = {**DEFAULTS, **PROFILES[prof]}
    for k, x in knobs.items():
        if k == "MODE" and isinstance(x, str):
            x = MODES.index(x)
        if k == "TRIG" and isinstance(x, str):
            x = TRIGS.index(x)
        if k == "VMOD" and isinstance(x, str):
            x = VMODS.index(x)
        v[_PAGE_TO.get(k, k)] = x
    return np.array([float(v[n]) for n in NAMES])


SUB = 32                                     # control rate: once a sub-block (as Viscera's VSC_SUB)
RING = 1024                                  # the droplets' memory, mu-law (at 48 kHz: 21 ms)
EV = 4                                       # envelopes and gains every fourth sample

_HZ = np.array([200., 400., 800., 1200., 1600., 2400., 3200., 4800.])
_W1 = np.array([0.5, 0.45, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1])
_W2 = np.array([0.3, -0.6, 0.5, -0.4, 0.7, -0.5, 0.9, -0.8])


class Reson:
    """One voice's RESON. `process(x, p, note_on)` filters a buffer in place of the voice;
    note_on: sample indices where the voice starts a note (NOTES pings)."""

    def __init__(self, seed: int = 0x9E3779B9):
        self.f = np.zeros(_NF)              # the float state
        self.i = np.zeros(_NI, dtype=np.int64)
        self.i[_RNG] = seed & 0xFFFFFFFF
        self.i[_ARMED] = 1
        self.ring = np.full(RING, 0xFF, dtype=np.int64)   # mu-law silence
        self.drops = np.zeros((3, 8))       # pos inc amp du len t dest on

    def process(self, x: np.ndarray, p: np.ndarray, note_on=()) -> np.ndarray:
        x = np.asarray(x, dtype=float).copy()
        notes = np.zeros(len(x), dtype=np.int64)
        for k in note_on:
            if 0 <= k < len(x):
                notes[k] = 1
        _run(x, np.asarray(p, dtype=float), notes, self.f, self.i, self.ring, self.drops, ULAW, _HZ, _W1, _W2,
             RATE)
        return x


# the float state's layout
_B = 8
(_CY1, _CY2, _RY1, _RY2, _RX1, _RX2, _MY1, _MY2, _CD1, _CD2, _CB0, _AB0, _RD1, _RD2, _RB0, _PN, _GAIN, _GSTEP,
 _GG, _ENV, _OENV, _PW, _INJ) = (k * _B for k in range(23))
_S = 23 * _B
(_CX1, _CX2, _MX1, _MX2, _EXC, _EXCD, _LQ0, _LQ1, _LQT0, _LQT1, _LQS0, _LQS1, _HP, _LP, _EF, _ES, _ACT, _OSC,
 _FB, _DC) = range(_S, _S + 20)
_NF = _S + 20
_RNG, _ARMED, _REFR, _RW = range(4)
_NI = 4


@njit(cache=True)
def _rnd(i):
    s, v = xorshift(i[_RNG])
    i[_RNG] = s
    return v


@njit(cache=True)
def _rndu(i):
    return (_rnd(i) >> 8) * (1.0 / 16777216.0)


@njit(cache=True)
def _control(f, i, p, n, hz, w1, w2, sr):
    """reson_control(): tuning, decays, gains and LIQUID's walks, once a sub-block."""
    for k in range(_NF):            # nothing sinks to a denormal
        if abs(f[k]) < 1e-26:
            f[k] = 0.0
    mode = int(p[0])
    cont = 0.0 if mode == 3 else (0.5 if mode == 4 else 1.0)
    liq = p[29] * (1.0 / 127.0)
    for w in range(2):
        lq, lqt, lqs = f[_LQ0 + w], f[_LQT0 + w], f[_LQS0 + w]
        if abs(lq - lqt) < abs(lqs) * 1.5 or lqs == 0.0:
            lqt = _rndu(i) * 2.0 - 1.0
            lqs = (lqt - lq) * n / ((0.35 + _rndu(i) * (1.6 if w else 0.9)) * sr)
            f[_LQT0 + w], f[_LQS0 + w] = lqt, lqs
        f[_LQ0 + w] = lq + lqs
    shift, t0 = p[28] - 64.0, p[1] * (8.0 / 127.0)
    kw = 2.0 ** (-p[3] * (5.0 / 127.0))
    for b in range(8):
        mv = liq * (w1[b] * f[_LQ0] + w2[b] * f[_LQ1])
        fr = hz[b] * 2.0 ** ((shift + p[12 + b] - 64.0) / 64.0) * (1.0 + 0.03 * mv)
        T = 0.01 * 2.0 ** (t0 + (p[20 + b] - 64.0) / 32.0) * (1.0 + 0.3 * liq * w2[b] * f[_LQ1])
        fr = min(max(fr, 16.0), 0.45 * sr)
        g = math.tan(math.pi * fr / sr)
        g2 = g * g
        kk = min(max(2.2 / (fr * T), 0.004), 1.6)
        ia = 1.0 / (1.0 + g * kk + g2)
        f[_RD1 + b] = 2.0 * (g2 - 1.0) * ia
        f[_RD2 + b] = (1.0 - g * kk + g2) * ia
        f[_RB0 + b] = g * kk * ia
        f[_PN + b] = 2.5 * sr / (6.2831853 * fr * kk)
        kc = kk if kk > kw else kw
        ic = 1.0 / (1.0 + g * kc + g2)
        f[_CD1 + b] = 2.0 * (g2 - 1.0) * ic
        f[_CD2 + b] = (1.0 - g * kc + g2) * ic
        f[_AB0 + b] = g * kc * ic
        f[_CB0 + b] = f[_AB0 + b] * cont * 8.0 * math.sqrt(0.125 / kc)
        v = p[4 + b]
        lin = 0.0 if v < 0.5 else 2.0 ** ((-60.0 + v * (66.0 / 127.0) + 3.0 * liq * w1[b] * f[_LQ0]) * 0.1660964)
        f[_GSTEP + b] = (lin - f[_GAIN + b]) / n


@njit(cache=True)
def _ping(f, p, vel, sr):
    """reson_ping(): a burst into every band, by its gain and (SPECTR) the modulator's energy."""
    spec = p[31] / 127.0
    mx = 1e-6
    for b in range(8):
        mx = max(mx, f[_ENV + b])
    ex = 1.0 + 3.0 * spec
    for b in range(8):
        w = 2.0 ** (ex * math.log2(f[_ENV + b] / mx + 1e-4))
        f[_PW + b] = (1.0 - spec + spec * w) * f[_PN + b]
    hard = p[39] / 127.0
    tau = (0.004 - 0.0037 * hard) * sr
    f[_EXCD] = 2.0 ** (-1.4427 / tau)
    f[_EXC] += vel * 0.7 / tau


@njit(cache=True)
def _run(x, p, notes, f, i, ring, drops, ulaw, hz, w1, w2, sr):
    N = len(x)
    mode, vm, trig = int(p[0]), int(p[32]), int(p[37])
    if mode == 0:
        return
    cont = 0.0 if mode == 3 else (0.5 if mode == 4 else 1.0)
    voc = mode == 2 or mode == 4
    depth, wet = p[36] / 127.0, p[2] / 127.0
    sa_, sr_ = p[34] / 127.0, p[35] / 127.0
    att = 1.0 - 2.0 ** (-1.4427 * EV / ((0.0005 + 0.05 * sa_ * sa_) * sr))
    rel = 1.0 - 2.0 ** (-1.4427 * EV / ((0.005 + 0.6 * sr_ * sr_) * sr))
    fdbk = p[30] * (0.85 / 127.0)
    hpk, lpk = 0.35, 0.03
    sens = p[38] / 127.0
    th = 0.25 * 2.0 ** (-sens * 9.0)
    fa, fr_ = 1.0 / (0.001 * sr), 1.0 / (0.015 * sr)
    sa, srl = 1.0 / (0.06 * sr), 1.0 / (0.3 * sr)
    dust, cohes = p[40] / 127.0, p[41] / 127.0
    drop, migr = p[42] / 127.0, p[43] / 127.0
    dust_p = 0.0 if vm == 2 else dust * dust * (300.0 / sr)
    osc_inc = 110.0 * 2.0 ** (24.0 / 12.0) / sr        # the OSC modulator: a fixed A (no note here)
    shape = p[33] * (4.0 / 127.0)
    vd8 = depth * 8.0 if voc else 0.0
    vd3 = depth * 3.0 if voc else 0.0
    vbase = 1.0 - depth if voc else 1.0
    other = vm == 1 or vm == 2
    self_ = (not other) and vm != 3
    opk = np.zeros(8)
    pos = 0
    while pos < N:
        n = min(SUB, N - pos)
        _control(f, i, p, n, hz, w1, w2, sr)
        on = 0
        for b in range(8):
            opk[b] = 0.0
            if f[_GAIN + b] > 1e-6 or f[_GSTEP + b] > 0.0:
                on |= 1 << b
            else:
                f[_GAIN + b] += f[_GSTEP + b] * n
                f[_OENV + b] *= 0.9
        for j in range(n):
            k = pos + j
            xin = x[k]
            if trig == 4 and notes[k]:
                _ping(f, p, 1.0, sr)
            if vm == 2:
                r = _rndu(i) * 2.0 - 1.0
                m = r if dust > 0.7 else (r * 3.0 if _rndu(i) < dust * dust * 0.3 else 0.0)
            elif vm == 1:
                f[_OSC] += osc_inc
                if f[_OSC] >= 1.0:
                    f[_OSC] -= 1.0
                ph = f[_OSC]
                sn, saw, pul = math.sin(2 * math.pi * ph), 2.0 * ph - 1.0, (1.0 if ph < 0.3 else -1.0)
                m = (sn + (saw - sn) * shape * 0.5 if shape < 2.0 else saw + (pul - saw) * (shape - 2.0) * 0.5) * 0.5
            else:
                m = xin
            # the detector: a fast against a slow envelope of the chosen band
            f[_LP] += (m - f[_LP]) * lpk
            f[_HP] += (m - f[_HP]) * hpk
            d = m - f[_HP] if trig == 1 else (f[_LP] if trig == 3 else m)
            a = abs(d)
            f[_EF] += (a - f[_EF]) * (fa if a > f[_EF] else fr_)
            f[_ES] += (a - f[_ES]) * (sa if a > f[_ES] else srl)
            nov = f[_EF] - 1.8 * f[_ES]
            tha = th + 0.4 * f[_ES]
            f[_ACT] += ((1.0 if nov > th else 0.0) - f[_ACT]) * 0.0005
            if i[_REFR] > 0:
                i[_REFR] -= 1
            if 1 <= trig <= 3:
                if nov > tha and i[_ARMED] == 1 and i[_REFR] == 0:
                    _ping(f, p, min(max(nov / th * 0.2, 0.15), 1.0), sr)
                    i[_ARMED] = 0
                    i[_REFR] = int(0.04 * sr)
                elif nov < tha * 0.5:
                    i[_ARMED] = 1
            # dust: specks into one band each; COHES gathers them round the hits
            if dust_p > 0.0 and _rndu(i) < dust_p * (1.0 - cohes + cohes * 6.0 * f[_ACT]):
                b = _rnd(i) & 7
                f[_INJ + b] += (_rndu(i) * 2.0 - 1.0) * f[_PN + b] * (0.15 + 2.0 * f[_EF])
            f[_EXC] *= f[_EXCD]
            e = f[_EXC]
            fb = f[_FB] * fdbk
            dc_ = xin - f[_CX2]
            dm = m - f[_MX2]
            f[_CX2], f[_CX1] = f[_CX1], xin
            f[_MX2], f[_MX1] = f[_MX1], m
            y = 0.0
            upd = (j & (EV - 1)) == 0
            for b in range(8):
                if not (on >> b) & 1:
                    continue
                vc = 0.0
                if cont > 0.0:
                    vc = f[_CB0 + b] * dc_ - f[_CD1 + b] * f[_CY1 + b] - f[_CD2 + b] * f[_CY2 + b]
                    f[_CY2 + b], f[_CY1 + b] = f[_CY1 + b], vc
                u = e * f[_PW + b] + f[_INJ + b] + fb
                vr = f[_RB0 + b] * (u - f[_RX2 + b]) - f[_RD1 + b] * f[_RY1 + b] - f[_RD2 + b] * f[_RY2 + b]
                f[_RX2 + b], f[_RX1 + b] = f[_RX1 + b], u
                f[_RY2 + b], f[_RY1 + b] = f[_RY1 + b], vr
                f[_INJ + b] = 0.0
                sb = vc + vr
                em = 0.0
                if other:
                    vm_ = f[_AB0 + b] * dm - f[_CD1 + b] * f[_MY1 + b] - f[_CD2 + b] * f[_MY2 + b]
                    f[_MY2 + b], f[_MY1 + b] = f[_MY1 + b], vm_
                    em = abs(vm_)
                if upd:
                    en = em if other else (abs(sb) if self_ else f[_OENV + b])
                    env = f[_ENV + b]
                    env += (en - env) * (att if en > env else rel)
                    f[_ENV + b] = env
                    g = f[_GAIN + b]
                    ve = env * vd8
                    f[_GAIN + b] = g + f[_GSTEP + b] * EV
                    gg = g * (vbase + (ve if ve < vd3 else vd3))
                    f[_GG + b] = gg
                    ao = abs(sb * gg)
                    if ao > opk[b]:
                        opk[b] = ao
                else:
                    gg = f[_GG + b]
                y += sb * gg
            if fdbk > 0.0:
                f[_DC] += (y - f[_DC]) * 0.001
                fy = y - f[_DC]
                f[_FB] = fy / (1.0 + abs(fy))
            else:
                f[_FB] = 0.0
            dsum = 0.0
            if drop > 0.0:
                rw = i[_RW]
                ring[rw] = ulaw_enc(y)
                i[_RW] = (rw + 1) & (RING - 1)
                ps = drop * (0.4 + cohes * 6.0 * f[_ACT]) * (60.0 / sr)
                r = _rndu(i)
                for q in range(3):
                    if drops[q, 7] == 0.0:
                        if r < ps:
                            r = 2.0
                            ln = int((0.004 + _rndu(i) * 0.014) * sr)
                            drops[q, 7] = 1.0
                            drops[q, 5] = 0.0
                            drops[q, 4] = ln
                            drops[q, 3] = 1.0 / ln
                            drops[q, 0] = float((i[_RW] + RING - ln - 64 - (_rnd(i) & 511)) & (RING - 1))
                            drops[q, 1] = 1.0 + (_rndu(i) - 0.5) * 0.02
                            drops[q, 2] = 0.7 + _rndu(i) * 0.6
                            dest = _rnd(i) & 7
                            if f[_GAIN + dest] < 1e-3:
                                dest = (dest + 5) & 7
                            drops[q, 6] = dest
                        else:
                            r -= ps
                        continue
                    ip = int(drops[q, 0]) & (RING - 1)
                    uu = drops[q, 5] * drops[q, 3]
                    v = ulaw[ring[ip]] * 4.0 * uu * (1.0 - uu) * drops[q, 2]
                    dsum += v
                    f[_INJ + int(drops[q, 6])] += v * migr * 3.0
                    drops[q, 0] += drops[q, 1]
                    if drops[q, 0] >= RING:
                        drops[q, 0] -= RING
                    drops[q, 5] += 1.0
                    if drops[q, 5] >= drops[q, 4]:
                        drops[q, 7] = 0.0
            o = xin * (1.0 - wet) + (y + dsum * drop * (1.0 - migr)) * wet
            if o != o:
                for kk in range(_NF):
                    f[kk] = 0.0
                o = 0.0
            x[k] = o
        for b in range(8):
            if (on >> b) & 1:
                f[_OENV + b] += (opk[b] - f[_OENV + b]) * (0.27 if opk[b] > f[_OENV + b] else 0.016)
        pos += n
