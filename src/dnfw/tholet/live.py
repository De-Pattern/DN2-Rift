"""THOLET's voice on the SHARC's arithmetic (float32 after every operation, organ.live's leaves:
recip, exp2f, expf, sin_turns, note_hz, xs_uni; no pow, sqrt, log or division). The SHARC program
is held to this bit for bit, as RIFT's other machines are. The concept is Error Kit's.

The sound is model.py's (the design model, the owner's audition, 2026-11-18), rebuilt for the DSP:
- **The strike**: one of six Kawai grand transients (VCSL, CC0), 50 ms at 24 kHz in mu-law
  (hits.json), read at the note's ratio with linear interpolation; FELT darkens it (a one-pole
  low-pass), quietens it and adds a felt thud (noise through a one-pole, a 12 ms decay).
- **The strings**: twelve partials on each of two strings detuned by STRK, each a two-pole
  resonator struck once at the note (a damped sine from phase 0). Partials stretched by
  n (1 + B n^2 / 2 - B^2 n^4 / 8) (sqrt's series; B n^2 < 0.1 on the keyboard), amplitudes from
  where the hammer strikes, TONE and FELT, and the velocity (vel^(0.5 + 0.1 n) as exp2f of
  log2(vel) from a table); EP morphs the first four toward a Rhodes tine and fades the rest; the
  pickup's bark y + 0.35 EP y^2; a 1.5 ms rise under the strike. Note-off: the damper, every
  partial's radius down to REL's.
- **The cloud** (GRAN > 0): the voice's own sound in a ring (0.35 s, DDR on the DSP), read back by
  up to 8 expodec grains (instant attack, exponential decay), each at 1 + GFM 0.5 sin(2 pi fm t)
  of its start; GDEN grains a second (the gap uniform in 0.25 .. 1.75 of the mean: no log for the
  model's exponential), GSPR how far back they start; its level GRAN x (1 - the strings'
  envelope), so it swells into the tail.
- The pitch, the partials and the strike's ratio are set at the note and when TUNE, HAMR, TONE,
  FELT, DEC, EP or STRK move (a knob change re-tunes the resonators in place, keeping their state).

**Controls** (knobs 0..127). Page 1: TUNE HAMR TONE FELT / DEC EP STRK LEV.
Page 2: GRAN GDEN GSIZ GFM / GSPR REL VSNS BRTH (BRTH: the strike's level against the strings).
"""
from __future__ import annotations

import json
import pathlib

import numpy as np

from ..organ.live import F, DT, recip, exp2f, expf, sin_turns, note_hz

FS = 48000
SUB = 32
NP_ = 12                                    # partials a string
NR = 2 * NP_                                # resonators a voice
NG = 8                                      # grains at most
RING = 16384                                # the cloud's ring (0.341 s; a power of two)
CONTROLS = ("TUNE", "HAMR", "TONE", "FELT", "DEC", "EP", "STRK", "LEV",
            "GRAN", "GDEN", "GSIZ", "GFM", "GSPR", "REL", "VSNS", "BRTH")
DEFAULTS = dict(TUNE=64, HAMR=1, TONE=64, FELT=0, DEC=80, EP=0, STRK=40, LEV=100,
                GRAN=0, GDEN=60, GSIZ=50, GFM=30, GSPR=60, REL=40, VSNS=90, BRTH=64)
RETUNE = ("TUNE", "HAMR", "TONE", "FELT", "DEC", "EP", "STRK")
INV127 = F(F(1.0) / F(127.0))
LN60 = F(6.9078)
LOG2E = F(1.4426950)
REST_AMP = F(2.0e-5)
REST_BLOCKS = 32

_H = json.loads(pathlib.Path(__file__).with_name("hits.json").read_text(encoding="utf-8"))
HIT_N = _H["n"]
HIT_NOTES = tuple(_H["notes"])
HIT_NAMES = tuple(_H["names"])
NH = len(HIT_NOTES)
HIT_BYTES = tuple(bytes.fromhex(h) for h in _H["hits"])


def _mulaw(b: int) -> float:
    b = ~b & 0xFF
    sign, ex, mant = b & 0x80, (b >> 4) & 7, b & 0x0F
    m = (((mant << 3) + 0x84) << ex) - 0x84
    return (-m if sign else m) / 32768.0


MULAW = tuple(F(_mulaw(b)) for b in range(256))      # the DSP's 256-word table
# the hammer's position (1/7 of the string): |sin(pi p / 7)|, and each partial's T60 share
HPOS = tuple(F(abs(np.sin(np.pi * p / 7.0))) for p in range(1, NP_ + 1))
RP = tuple(F(1.0 / (1.0 + 0.05 * p * p)) for p in range(1, NP_ + 1))
# the tine's first four partials: (ratio, level, T60 share)
TINE = ((F(1.0), F(1.0), F(1.0)), (F(2.0), F(0.18), F(0.5)), (F(5.8), F(0.55), F(0.06)), (F(7.8), F(0.08), F(0.04)))
# log2 of the velocity (v / 127), v = 1..127 (v 0: -16)
VLOG2 = (F(-16.0),) + tuple(F(np.log2(v / 127.0)) for v in range(1, 128))
# the hits' notes' frequencies, x 2 (their tables are at 24 kHz): the ratio is f0 x HINV[k]
HINV = tuple(F(0.5 / (440.0 * 2.0 ** ((n - 69) / 12.0))) for n in HIT_NOTES)


def hit_sample(k: int, i: int) -> F:
    return MULAW[HIT_BYTES[k][i]]


def xs32(x):
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x


def uni(rng) -> F:
    rng[0] = xs32(rng[0])
    return F(F(rng[0] >> 8) * F(1.0 / 16777216.0))


def kq(knobs: dict, name: str) -> F:
    return F(F(knobs[name]) * INV127)


class Voice:
    """one slot's THOLET voice: block(knobs, trig, note, vel, off) -> 32 samples"""

    def __init__(self, slot: int = 0):
        self.rng = [(0x74686F00 + 0x01000193 * (slot + 1)) & 0xFFFFFFFF or 1]
        self.on = False
        self.ring = np.zeros(RING, np.float32)
        self.clr = RING // 512                  # the DSP clears the ring 512 words a block: no cloud till then
        self.reset()

    def reset(self):
        self.y1 = [F(0.0)] * NR
        self.y2 = [F(0.0)] * NR
        self.c0 = [F(0.0)] * NR
        self.c1 = [F(0.0)] * NR
        self.cw = [F(0.0)] * NR                # cos w, kept for the damper
        self.amp = [F(0.0)] * NR               # each resonator's strike (sin w x its level)
        self.hp = F(0.0)                       # the strike's read position (24 kHz samples)
        self.hr = F(0.0)                       # its step
        self.hk = 0
        self.lz = F(0.0)                       # FELT's low-pass
        self.tz = F(0.0)                       # the thud's low-pass
        self.te = F(0.0)                       # the thud's envelope
        self.rise = F(0.0)                     # the strings' 1.5 ms rise
        self.env = F(1.0)                      # the strings' reference envelope (for the cloud)
        self.ed = F(1.0)
        self.gate = F(0.0)
        self.vel = F(1.0)
        self.vl2 = F(0.0)
        self.f0 = F(261.6)
        self.sig = None
        self.quiet = 0
        self.wp = 0                            # the ring's write position
        self.gpos = [F(0.0)] * NG              # each grain: its read position, step, window, gain, left
        self.ginc = [F(0.0)] * NG
        self.gw = [F(0.0)] * NG
        self.gd = [F(0.0)] * NG
        self.gn = [0] * NG
        self.nxt = 960                         # samples to the next grain
        self.t = 0                             # samples since the note
        self.fph = F(0.0)                      # the grains' FM phase (turns)

    # -- the note's settings ----------------------------------------------------------------
    def tune(self, k: dict, fresh: bool):
        """the partials (and, on a fresh strike, their states) from the knobs"""
        felt, ep, tone, dec = kq(k, "FELT"), kq(k, "EP"), kq(k, "TONE"), kq(k, "DEC")
        pitch = F(self.note + F(F(k["TUNE"]) - F(64.0)))
        f0 = note_hz(pitch)
        self.f0 = f0
        pm = F(pitch - F(60.0))
        B = F(F(0.00015) * exp2f(F(pm * F(1.0 / 24.0))))
        t60 = F(F(F(0.4) + F(F(18.0) * F(dec * dec))) * exp2f(F(F(F(48.0) - pitch) * F(1.0 / 30.0))))
        self.t60 = t60
        det = exp2f(F(F(kq(k, "STRK") * F(4.0)) * F(1.0 / 1200.0)))
        hard = F(F(F(0.12) + F(F(0.35) * F(F(1.0) - tone))) + F(F(1.4) * felt))
        ep1 = F(F(1.0) - ep)
        self.hk = min(max(int(k["HAMR"]), 0), NH - 1)   # HAMR: the strike's option (0..5), as the DSP's records give it
        self.hr = F(f0 * HINV[self.hk])
        self.ed = expf(F(F(-LN60) * F(DT * recip(t60))))
        for s in range(2):
            dt = F(1.0) if s == 0 else det
            for p in range(1, NP_ + 1):
                i = s * NP_ + p - 1
                fp_ = F(p)
                bn = F(B * F(fp_ * fp_))
                st = F(F(F(1.0) + F(bn * F(0.5))) - F(F(bn * bn) * F(0.125)))
                fp = F(F(F(fp_ * f0) * st) * dt)
                ap = F(F(HPOS[p - 1] * expf(F(F(-hard) * F(p - 1)))) *
                       exp2f(F(F(F(0.5) + F(F(0.1) * fp_)) * self.vl2)))
                tp = F(t60 * RP[p - 1])
                if p <= 4:
                    tr, ta, td = TINE[p - 1]
                    fp = F(F(ep1 * fp) + F(ep * F(F(tr * f0) * dt)))
                    ap = F(F(ep1 * ap) + F(ep * ta))
                    tp = F(F(ep1 * tp) + F(ep * F(t60 * td)))
                else:
                    ap = F(ap * ep1)
                x = F(fp * DT)
                if not (x < F(0.45)):
                    self.c0[i] = self.c1[i] = self.amp[i] = F(0.0)
                    continue
                tp = tp if tp > F(0.02) else F(0.02)
                r = expf(F(F(-LN60) * F(DT * recip(tp))))
                cw = sin_turns(F(x + F(0.25)))
                self.cw[i] = cw
                self.c0[i] = F(F(F(2.0) * r) * cw)
                self.c1[i] = F(-F(r * r))
                self.amp[i] = F(sin_turns(x) * ap)
        if fresh:
            for i in range(NR):
                self.y1[i] = self.amp[i]       # a damped sine from phase 0: y[0] = A sin w
                self.y2[i] = F(0.0)

    def damp(self, k: dict):
        """the key let go: every partial's radius at most REL's"""
        rq = kq(k, "REL")
        rel = F(F(0.04) + F(F(1.2) * F(rq * rq)))
        r = expf(F(F(-LN60) * F(DT * recip(rel))))
        rr = F(r * r)
        for i in range(NR):
            if F(-self.c1[i]) > rr:            # its radius squared is -c1
                self.c0[i] = F(F(F(2.0) * r) * self.cw[i])
                self.c1[i] = F(-rr)

    # -- one block of 32 samples ------------------------------------------------------------
    def block(self, k: dict, trig: bool = False, note: float = 60.0, vel: int = 127, off: bool = False):
        out = np.zeros(SUB, np.float32)
        if self.clr > 0:
            self.clr -= 1
        sig = tuple(int(k[c]) for c in RETUNE)
        if trig:
            if not self.on:
                self.reset()
            self.on = True
            self.note = F(note)
            v = min(max(int(vel), 0), 127)
            self.vel = F(F(v) * INV127)
            self.vl2 = VLOG2[v]
            self.gate = F(1.0)
            self.hp = F(0.0)
            self.lz = self.tz = self.rise = F(0.0)
            self.te = F(1.0)
            self.env = F(1.0)
            self.t = 0
            self.quiet = 0
            self.tune(k, True)
            self.sig = sig
        elif self.on and sig != self.sig:
            self.tune(k, False)
            self.sig = sig
            if self.gate == F(0.0):
                self.damp(k)
        if off and self.on and self.gate != F(0.0):
            self.gate = F(0.0)
            self.damp(k)
        if not self.on:
            return out
        felt, ep, lev = kq(k, "FELT"), kq(k, "EP"), kq(k, "LEV")
        gran, vs, br = kq(k, "GRAN"), kq(k, "VSNS"), kq(k, "BRTH")
        cf = F(F(1.0) - F(F(0.93) * felt))
        cf = cf if cf > F(0.05) else F(0.05)
        f1 = F(F(1.0) - felt)
        f6 = F(felt * F(0.6))
        f25 = F(felt * F(0.25))
        sg = F(F(F(F(0.55) + F(F(0.45) * self.vel)) * F(F(0.9) - F(F(0.4) * ep))) * F(F(br * F(127.0 / 64.0)) * F(0.8)))
        bark = F(F(0.35) * ep)
        velg = F(F(F(1.0) - vs) + F(vs * self.vel))
        og = F(F(lev * velg) * F(0.7))         # the voice near the other machines' level
        td = F(0.998265)                        # the thud's 12 ms e-fold a sample
        rk = F(0.013793)                        # the strings' 1.5 ms rise a sample
        hmax = F(float(HIT_N - 2))
        # the cloud's settings, once a block
        cloud = gran > F(0.0) and self.clr == 0
        if cloud:
            dq, sq, fq, pq = kq(k, "GDEN"), kq(k, "GSIZ"), kq(k, "GFM"), kq(k, "GSPR")
            dens = F(F(2.0) + F(F(120.0) * F(dq * dq)))
            gap = F(F(48000.0) * recip(dens))
            gl = F(F(48000.0) * F(F(0.008) + F(F(0.052) * sq)))
            gdk = expf(F(-recip(F(gl * F(0.22)))))
            fm = F(F(F(3.0) + F(F(40.0) * fq)) * DT)
            fmd = F(fq * F(0.5))
            spr = F(F(pq * F(0.33)) * F(48000.0))
            dry = F(F(1.0) - F(F(0.6) * gran))
            sw = F(gran * F(1.2))
        peak = F(0.0)
        # pass 1: the strike, 32 samples
        sk = [F(0.0)] * SUB
        for j in range(SUB):
            s = F(0.0)
            if self.hp < hmax:
                i0 = int(np.floor(self.hp))
                fr = F(self.hp - F(i0))
                a = hit_sample(self.hk, i0)
                b = hit_sample(self.hk, i0 + 1)
                s = F(a + F(fr * F(b - a)))
                self.hp = F(self.hp + self.hr)
            self.lz = F(self.lz + F(cf * F(s - self.lz)))
            s = F(F(f1 * s) + F(f6 * self.lz))
            if self.te > F(1e-4):
                nz = F(F(uni(self.rng) * F(2.0)) - F(1.0))
                self.tz = F(self.tz + F(F(0.05) * F(F(F(nz * self.te) * f25) - self.tz)))
                self.te = F(self.te * td)
                s = F(s + F(self.tz * F(4.0)))
            sk[j] = F(s * sg)
        # pass 2: the strings, a resonator at a time
        acs = [F(0.0)] * SUB
        for i in range(NR):
            c0, c1, y1, y2 = self.c0[i], self.c1[i], self.y1[i], self.y2[i]
            for j in range(SUB):
                y = F(F(c0 * y1) + F(c1 * y2))
                y2 = y1
                y1 = y
                acs[j] = F(acs[j] + y)
            self.y1[i], self.y2[i] = y1, y2
        # pass 3: the voice
        for j in range(SUB):
            acc = F(acs[j] * F(0.225))        # the model's 0.35, less its random phases' spread (rms)
            acc = F(acc + F(F(bark * acc) * acc))
            self.rise = F(self.rise + F(rk * F(F(1.0) - self.rise)))
            y = F(sk[j] + F(acc * self.rise))
            self.env = F(self.env * self.ed)
            # the cloud
            if cloud:
                self.fph = F(self.fph + fm)
                if self.fph >= F(1.0):
                    self.fph = F(self.fph - F(1.0))
                self.ring[self.wp] = y
                cl = F(0.0)
                self.nxt -= 1
                if self.nxt <= 0:
                    for g in range(NG):
                        if self.gn[g] <= 0:
                            back = F(F(96.0) + F(uni(self.rng) * spr))
                            rate = F(F(F(1.0) + F(fmd * sin_turns(self.fph))) + F(F(F(uni(self.rng) * F(0.04)) - F(0.02))))
                            pos = F(F(self.wp) - back)
                            self.gpos[g] = F(pos + F(RING)) if pos < F(0.0) else pos
                            self.ginc[g] = rate
                            self.gw[g] = F(1.0)
                            self.gd[g] = gdk
                            self.gn[g] = int(gl)
                            break
                    nx = F(gap * F(F(0.25) + F(F(1.5) * uni(self.rng))))
                    self.nxt = max(int(nx), 64)
                for g in range(NG):
                    if self.gn[g] > 0:
                        pp = self.gpos[g]
                        i0 = int(np.floor(pp))
                        fr = F(pp - F(i0))
                        a = self.ring[i0 & (RING - 1)]
                        b = self.ring[(i0 + 1) & (RING - 1)]
                        cl = F(cl + F(F(a + F(fr * F(b - a))) * self.gw[g]))
                        self.gw[g] = F(self.gw[g] * self.gd[g])
                        pp = F(pp + self.ginc[g])
                        self.gpos[g] = F(pp - F(RING)) if pp >= F(RING) else pp
                        self.gn[g] -= 1
                self.wp = (self.wp + 1) & (RING - 1)
                y = F(F(y * dry) + F(F(cl * sw) * F(F(1.0) - self.env)))
            o = F(y * og)
            out[j] = o
            a = o if o >= F(0.0) else F(-o)
            peak = a if a > peak else peak
            self.t += 1
        if not all(F(-16.0) < out[j] < F(16.0) for j in range(SUB)):
            self.on = False
            self.reset()
            return np.zeros(SUB, np.float32)
        if self.gate == F(0.0) or self.env < F(1e-3):
            self.quiet = self.quiet + 1 if peak < REST_AMP else 0
            if self.quiet >= REST_BLOCKS:
                self.on = False
        return out


def render(note: float = 60.0, secs: float = 4.0, vel: int = 127, gate: float | None = None, **kn) -> np.ndarray:
    k = dict(DEFAULTS)
    k.update(kn)
    v = Voice(0)
    nb = int(secs * FS) // SUB
    off_b = None if gate is None else int(gate * FS) // SUB
    return np.concatenate([v.block(k, b == 0, note, vel, b == off_b) for b in range(nb)])
