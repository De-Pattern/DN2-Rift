"""SILT in float32 on the SHARC's own arithmetic (docs/silt-dsp.md, step 1 of the port).

The audition model (work/silt/silt_model.py, numba, float64 with libm) is the sound the owner
approved. This is the same voice, block for block and sample for sample, with every libm call
made the DSP's way (fascia.live's exp2/recip/tanh_r/sqrt and sin/cos/tan of organ.live, a
log2 below) and every value a float32. It is not bit-exact to the audition model (the
primitives differ in their last bits and the feedback loops carry that); test_silt_live holds
it to the model's level and spectrum. The SHARC program (program.py) will be bit-exact to
this file.

Two changes from the audition model, both from the DSP plan:
- QUAL DEEP is NSEC_DEEP filaments (6; the model had 8), the owner's ear to confirm.
- a voice is one Voice; the cap (4 SILT voices) and the stealing live in the ColdFire.
"""
from __future__ import annotations

import numpy as np

from ..fascia.live import exp2, recip, tanh_r, sqrt as sqrtf
from ..organ.live import sinf, cosf, tanf, xs32

F = np.float32
FS = F(48000.0)
IFS = F(1.0 / 48000.0)
SUB = 32
DT = F(32.0 / 48000.0)
PI = F(3.14159265358979)
TWO_PI = F(6.2831853)
INV127 = F(1.0 / 127.0)

CONTROLS = ("PART", "TENS", "MASS", "COHE", "VISC", "GRAIN", "DENS", "BODY",
            "PRESS", "SPEED", "POS", "ROSIN", "SCRAP", "SNAP", "AIR", "INST",
            "SPREAD", "VOICES", "DRIFT", "VIBR", "GLISS", "FORM", "ROUGH", "MORPH",
            "MAT", "GEST", "MODE", "DIST", "LOOP", "SHAPE", "TUNE", "QUAL")
MATS = ("FIBER", "SILT", "SKIN", "FLUID")
GESTS = ("BOW", "SCRAPE", "STACC", "TREMO", "SPICC", "LEGNO", "GLISS", "FRACT", "SWELL", "QUAKE")
MODES = ("SOLO", "MASS", "MASS-8", "SWARM")
DISTS = ("NARROW", "WIDE", "BIMODAL", "ASYM")
LOOPS = ("OFF", "1/16", "1/8", "1/4", "FREE")
SHAPES = ("SOFT", "LINEAR", "EXP", "CHAOTIC")
TUNES = ("FREE", "SCALE", "MICRO", "HARM")
QUALS = ("ECO", "NORMAL", "DEEP")
CHOICES = dict(MAT=MATS, GEST=GESTS, MODE=MODES, DIST=DISTS, LOOP=LOOPS, SHAPE=SHAPES,
               TUNE=TUNES, QUAL=QUALS)
DEFAULTS = dict(PART=42, TENS=66, MASS=53, COHE=70, VISC=43, GRAIN=55, DENS=28, BODY=74,
                PRESS=60, SPEED=64, POS=30, ROSIN=64, SCRAP=10, SNAP=40, AIR=10, INST=20,
                SPREAD=0, VOICES=64, DRIFT=20, VIBR=30, GLISS=64, FORM=40, ROUGH=10, MORPH=0,
                MAT=0, GEST=0, MODE=0, DIST=0, LOOP=0, SHAPE=1, TUNE=0, QUAL=1)

NBR = 2048          # the waveguide's lines (bridge, nut): down to about 24 Hz
NSEC = 8            # filament slots
NSEC_DEEP = 4       # QUAL DEEP's players (owner 2026-11-17: cheap and musical; 6 in the plan, 8 in the model)
NSL = 1024          # a filament's loop
LINE_WORDS = 2 * NBR + NSEC * NSL      # a slot's lines in DDR: br, nk, then the filaments (48 KB)
REST_AMP = F(1e-4)                     # released and this quiet (-80 dB): the voice rests (the guardrails)
FADE = np.array([F(F(1.0) - F(F(i + 1) * F(1.0 / SUB))) for i in range(SUB)], F)   # a block's fade out
CLEAR_WORDS = 512                      # cleared a block when the slot becomes SILT: 24 blocks
assert LINE_WORDS % CLEAR_WORDS == 0
QN_MASS = (2, 3, NSEC_DEEP)
QN_SOLO = (1, 2, 4)
LOG2_10 = F(3.32192809488736)
INV_LN2_2 = F(2.0 / 0.693147180559945)
HARM = tuple(F(c) for c in (0.0, 1200.0, 702.0, 1902.0, 2400.0, 1586.0, 969.0, 1902.0))
MEM = tuple(F(c) for c in (1.0, 1.59, 2.14, 2.30, 2.65, 2.92))
BFR = tuple(F(c) for c in (290.0, 470.0, 1150.0, 2600.0))
BGN = tuple(F(c * 0.012) for c in (1.0, 0.7, 0.45, 0.25))
# the filaments' own constants (tables on the DSP: one word each, so live and the SHARC agree)
FACK = tuple(F(F(F(0.85) + F(F(F(0.3) * F((k * 7) % 5)) * F(0.25))) - F(1.0)) for k in range(8))
IMPK = tuple(F(F(0.6) + F(F(F(0.4) * F((k * 3) % 4)) * F(1.0 / 3.0))) for k in range(8))
SGNK = tuple(F(1.0) if k % 2 else F(-1.0) for k in range(8))     # odd players +, even -
ALTK = tuple(F(1.0) if k % 2 == 0 else F(-1.0) for k in range(8))


# -- arithmetic beyond fascia.live's -------------------------------------------------------
def log2f(x):
    """log2 x for x > 0: the exponent, then 2/ln2 (t + t^3/3 + t^5/5 + t^7/7 + t^9/9),
    t = (m - 1)/(m + 1) of the mantissa m in [1, 2)."""
    x = F(x)
    if x <= F(0.0):
        return F(-126.0)
    b = int(np.array([x], F).view(np.uint32)[0])
    e = ((b >> 23) & 0xFF) - 127
    m = np.array([(b & 0x7FFFFF) | 0x3F800000], np.uint32).view(F)[0]
    t = (m - F(1.0)) * recip(m + F(1.0))
    t2 = t * t
    p = F(1.0 / 9.0)
    for c in (F(1.0 / 7.0), F(1.0 / 5.0), F(1.0 / 3.0), F(1.0)):
        p = p * t2 + c
    return F(e) + INV_LN2_2 * (t * p)


def powf(x, y):
    """x^y for x >= 0 (0 for x = 0)"""
    x = F(x)
    if x <= F(0.0):
        return F(0.0)
    return F(exp2(F(y) * log2f(x)))


def ex(x):
    return F(exp2(F(x) * F(1.44269504088896)))


def mn(a, b):
    a, b = F(a), F(b)
    return a if a < b else b


def mx(a, b):
    a, b = F(a), F(b)
    return a if a > b else b


def clip(x, lo, hi):
    return mn(mx(x, lo), hi)


def crv(x, shape):
    x = F(x)
    if x <= F(0.0):
        return F(0.0)
    if x >= F(1.0):
        return F(1.0)
    if shape == 0:
        return x * x * (F(3.0) - F(2.0) * x)
    if shape == 2:
        return powf(x, 2.5)
    return x


class Rng:
    def __init__(self, seed):
        self.s = (seed | 1) & 0xFFFFFFFF

    def bi(self):
        self.s, v = xs32(self.s)
        if v >= 0x80000000:
            v -= 0x100000000
        return F(F(v) * F(1.0 / 2147483648.0))

    def u(self):
        return self.bi() * F(0.5) + F(0.5)


def rd(buf, n, w, d):
    di = int(d)
    fr = F(d) - F(di)
    r0 = w - di
    if r0 < 0:
        r0 += n
    r1 = r0 - 1
    if r1 < 0:
        r1 += n
    return buf[r0] + (buf[r1] - buf[r0]) * fr


def wander(x, k, rng, slot):
    a = mn(F(1.0), F(k) * DT * F(2.0))
    x[slot + 1] += (rng.bi() * F(1.7) - x[slot + 1]) * a
    x[slot] += (x[slot + 1] - x[slot]) * mn(F(1.0), F(k) * DT)


def bow_k(dv, slope, offset):
    """the bow table's friction: 1/(|dv slope| + offset)^4, at most 1"""
    bt = abs(F(dv) * F(slope)) + F(offset)
    b2 = bt * bt
    b4 = b2 * b2
    if b4 <= F(1.0):
        return F(1.0)
    return recip(b4)


def panel(**kw) -> list:
    p = dict(DEFAULTS)
    for k, v in kw.items():
        if k in CHOICES and isinstance(v, str):
            v = CHOICES[k].index(v)
        p[k] = v
    return [float(p[c]) for c in CONTROLS]


class Voice:
    """one SILT voice: block(P, ...) renders 32 samples; P is the 32 controls (pages 1-3 as
    0..127 values, page 4 as option numbers)."""

    def __init__(self, seed=0x2545F491, bpm=120.0):
        self.rng = Rng(seed)
        self.rng2 = Rng((seed * 7) & 0xFFFFFFFF)
        self.bpm = F(bpm)
        z = lambda n: np.zeros(n, F)
        self.br = z(NBR); self.nk = z(NBR); self.wb = 0; self.wk = 0
        self.sb = np.zeros((NSEC, NSL), F); self.sw = [0] * NSEC
        self.slp = z(NSEC); self.sbow = z(NSEC); self.soff = z(NSEC); self.sdrift = z(2 * NSEC)
        self.svph = z(NSEC); self.sdx = z(NSEC); self.sdy = z(NSEC); self.sdel = z(NSEC)
        self.scnt = [0] * NSEC; self.simp = F(0.0)
        self.body = np.zeros((4, 2), F); self.md = np.zeros((6, 2), F)
        self.bub_f = z(4); self.bub_a = z(4); self.bub_p = z(4); self.bub_r = z(4)
        self.wnd = z(16); self.sk_ap = z(8)
        for n in ("lp", "bow", "hp", "fm1", "fm2", "env_e", "amp", "sk_dx", "sk_dy", "sk_Es",
                  "sk_lp", "sk_E", "sk_s1", "sk_s2", "p_a", "aval", "prev_tgt", "loop_t", "qph",
                  "cl_hp", "cl_b", "mo_c", "h1", "h2", "h3", "h4", "hx1", "hx2", "hx3", "hx4",
                  "f_ax", "f_ay", "g_hold", "t_note", "part_t", "burst", "strike", "sq",
                  "vib_ph", "vib_env", "gl_amt"):
            setattr(self, n, F(0.0))
        self.loop_per = F(1.0); self.f0 = F(110.0); self.vel = F(1.0)
        self.p_n = 0; self.p_i = 0; self.g_cnt = 0
        self.gate = 0
        self.L4 = [0] * 8
        self.clear_at = LINE_WORDS             # the lines' clear: done (a fresh Voice's are zeros)
        self.rest = True                       # silent and costing nothing until a note
        self.fade = False                      # a note of another material: this block fades
        self.w_off = False
        self.seed = seed
        self.waiting = None                    # a note that came during the clear

    def lines(self):
        """the slot's DDR lines in order: br, nk, the filaments"""
        return (self.br, self.nk, *self.sb)

    def become(self):
        """the slot became SILT (or the guard wiped it): its lines clear over 24 blocks"""
        self.clear_at = 0

    def _clear_step(self):
        a = self.clear_at
        for buf, off in zip(self.lines(), (0, NBR, *[2 * NBR + k * NSL for k in range(NSEC)])):
            lo, hi = max(a, off), min(a + CLEAR_WORDS, off + len(buf))
            if lo < hi:
                buf[lo - off:hi - off] = F(0.0)
        self.clear_at = a + CLEAR_WORDS

    # -- a note: the gesture starts again --------------------------------------------------
    def note(self, P, note, vel):
        """a trig (the DN2 gives the note and its velocity; the gate holds until the note-off)"""
        s = self
        mat = int(P[24])
        if s.clear_at < LINE_WORDS or s.fade:  # the lines are clearing (or about to): the note waits
            s.waiting = (note, vel)
            s.w_off = False
            return
        if not s.rest and mat != s.L4[0]:      # another material: the old one fades over a block,
            s.fade = True                      # the lines clear, then this note
            s.waiting = (note, vel)
            s.w_off = False
            return
        s.f0 = F(440.0) * exp2((F(note) - F(69.0)) * F(1.0 / 12.0))
        s.vel = F(vel); s.gate = 1; s.rest = False
        s.t_note = F(0.0); s.strike = F(1.0); s.burst = F(0.0); s.vib_env = F(0.0)
        s.gl_amt = F(0.0)
        s.L4 = [int(P[24 + c]) for c in range(8)]
        dist = s.L4[3]; tune = s.L4[6]
        spread = F(P[16])
        for k in range(NSEC):
            u = s.rng.bi()
            if dist == 0:
                c = u * F(0.5)
            elif dist == 1:
                c = u
            elif dist == 2:
                c = (F(0.6) + F(0.4) * abs(u)) * ALTK[k]
            else:
                c = powf(abs(u), 0.7)
            cents = c * (F(5.0) + spread * F(195.0 / 127.0))
            if tune == 1:
                if spread > F(70.0):
                    cents = F(np.floor(cents * F(0.01) + F(0.5))) * F(100.0)
            elif tune == 2:
                cents = F(np.floor(cents * F(0.02) + F(0.5))) * F(50.0)
            elif tune == 3:
                cents = cents * F(0.2) + HARM[k] * mn(F(1.0), spread * F(1.0 / 64.0))
            s.soff[k] = cents
            s.sbow[k] = F(0.0)
            s.sdel[k] = (F(0.002) + F(P[22]) * INV127 * F(0.035) + (F(1.0) - F(P[3]) * INV127) * F(0.02)) \
                * s.rng2.u()
            s.scnt[k] = -int(s.sdel[k] * FS)
        g_ = s.L4[1]
        s.simp = (F(0.6) + F(0.4) * s.vel) if (g_ == 5 or g_ == 7 or (s.L4[0] == 2 and g_ in (2, 4))) else F(0.0)
        s.loop_t = F(0.0)
        s.loop_per = (F(0.04) + (F(1.0) - F(P[9]) * INV127) * F(0.5)) \
            * (F(1.0) + (F(P[12]) + F(P[22])) * F(0.8 / 254.0) * s.rng2.bi())

    # -- a block ----------------------------------------------------------------------------
    def block(self, P, out=None, off=False):
        """32 samples; OFF: the note-off came in this block's frame (mask 36, bit t)"""
        s = self
        if out is None:
            out = np.zeros(SUB, F)
        if off:
            if s.waiting is not None:
                s.w_off = True                 # the waiting note will start with its gate closed
            else:
                s.gate = 0
        if s.fade:                             # the last block of the old material, faded
            s.fade = False
            s._render(P, out)
            out *= FADE
            s.rest = True                      # the old material is gone
            s.become()
            s._check(out)
            return out
        if s.clear_at < LINE_WORDS:
            s._clear_step()
            out[:] = F(0.0)
            return out
        if s.waiting is not None:
            w_, wo = s.waiting, s.w_off
            s.waiting = None
            s.note(P, *w_)
            if wo:
                s.gate = 0
        if s.rest:
            out[:] = F(0.0)
            return out
        s._render(P, out)
        s._check(out)
        return out

    def _check(self, out):
        """a non-finite sample: the output guard's wipe (silence, the voice rests, its state is
        written again at the next note, its lines clear first)"""
        if not np.isfinite(out).all():
            out[:] = F(0.0)
            seed = self.seed
            Voice.__init__(self, seed, float(self.bpm))
            self.become()

    def _render(self, P, out):
        s = self
        rng, rng2 = s.rng, s.rng2
        P = [F(v) for v in P]
        L4 = s.L4
        t_note = s.t_note + DT
        gate = s.gate
        loopk = L4[4]
        if gate and loopk > 0 and t_note > DT:
            if loopk < 4:
                s.loop_per = F(60.0) * recip(s.bpm) * (F(0.25), F(0.5), F(1.0))[loopk - 1]
            s.loop_t += DT
            if s.loop_t >= s.loop_per:
                s.loop_t -= s.loop_per
                t_note = DT
                s.strike = F(1.0)
                for k in range(NSEC):
                    s.scnt[k] = -int(s.sdel[k] * FS)
                if loopk == 4:
                    s.loop_per = (F(0.04) + (F(1.0) - P[9] * INV127) * F(0.5)) \
                        * (F(1.0) + (P[12] + P[22]) * F(0.8 / 254.0) * rng2.bi())
        s.t_note = t_note
        n = [p * INV127 for p in P[:24]]
        part, tens, mass, cohe, visc, grain, dens, bodyk = n[0:8]
        press, speedk, pos, rosin, scrap, snap, air, inst = n[8:16]
        spread, voices, drift, vibr, glissk, form, rough, morph = n[16:24]
        mat, gest, mode, distk, shape, qual = L4[0], L4[1], L4[2], L4[3], L4[5], L4[7]
        ens = mode == 1 or mode == 2
        lock = (cohe - F(0.55)) * F(1.0 / 0.45) if cohe > F(0.55) else F(0.0)
        loose = (F(0.55) - cohe) * F(1.0 / 0.55) if cohe < F(0.55) else F(0.0)
        sadd = F(0.0); entry = F(1.0)
        tgt = F(0.0); ppush = F(0.0); imp = F(0.0); damp_x = F(1.0); noisy = F(0.0); gn = F(0.0)
        w = s.wnd
        one_m_snap = F(1.0) - snap
        atk = (F(0.004) + one_m_snap * one_m_snap * F(0.6)) * (F(3.0) if shape == 0 else (F(0.3) if shape == 2 else F(1.0)))
        spd = (F(0.04) + speedk * F(0.28)) * (F(0.6) + F(0.4) * s.vel)
        stlen = F(0.03) + grain * F(0.25)
        held = gate or t_note < F(0.05)
        if gest == 0:
            tgt = spd if held else F(0.0)
        elif gest == 1:
            wander(w, 9.0, rng, 6)
            tgt = spd * (F(0.7) + F(0.6) * w[6]) if held else F(0.0)
            ppush = F(0.35) + F(0.2) * w[6]
            noisy = F(0.25)
        elif gest == 2:
            tgt = spd * F(1.3) if t_note < stlen else F(0.0)
            ppush = F(0.15)
            if t_note >= stlen:
                damp_x = F(1.0) + F(6.0) * (F(1.0) - mn(F(1.0), (t_note - stlen) * F(1.0 / 0.08)))
        elif gest == 3:
            rate = F(6.0) + speedk * F(14.0)
            ph = t_note * rate
            ph = ph - F(np.floor(ph))
            tgt = (spd if ph < F(0.5) else -spd) if (gate or t_note < F(0.1)) else F(0.0)
        elif gest == 4:
            k_b = 0
            tt = t_note
            per = F(0.09) + (F(1.0) - speedk) * F(0.12)
            amp_b = F(1.0)
            while tt > per and k_b < 12:
                tt -= per
                per *= F(0.82)
                k_b += 1
                amp_b *= F(0.85)
            tgt = spd * F(1.4) * amp_b if (tt < stlen * F(0.6) and k_b < 12) else F(0.0)
        elif gest == 5:
            imp = s.strike * (F(0.6) + F(0.4) * s.vel)
        elif gest == 6:
            tgt = spd if held else F(0.0)
            gn = clip((P[20] - F(64.0)) * F(1.0 / 63.0), -1.0, 1.0)
            s.gl_amt = gn * F(12.0) * crv(t_note * recip(F(0.4) + (F(1.0) - speedk) * F(3.0)), shape)
        elif gest == 8:
            ramp = crv(t_note * recip(F(0.3) + (F(1.0) - speedk) * F(4.0)), shape)
            tgt = spd * (F(0.15) + F(0.85) * ramp) if held else F(0.0)
            ppush = F(0.3) * ramp
            sadd = F(0.35) * ramp
            entry = ramp
        elif gest == 9:
            ramp = crv(t_note * recip(F(0.5) + (F(1.0) - speedk) * F(4.0)), shape)
            q = s.qph + (F(3.0) + F(17.0) * ramp) * DT
            s.qph = q - F(np.floor(q))
            wander(w, F(6.0) + F(20.0) * ramp, rng, 10)
            tgt = spd * (F(1.0) + F(0.5) * ramp * sinf(TWO_PI * s.qph)) if held else F(0.0)
            ppush = F(0.3) * ramp * (F(0.5) + F(0.5) * w[10])
            sadd = F(0.7) * ramp
        else:
            imp = s.strike
            if t_note < F(0.05) + grain * F(0.8) and rng.u() < (F(0.15) + dens * F(0.8)) * (F(1.0) - t_note):
                imp += F(0.5) * rng.u() * (F(1.0) - mn(F(1.0), t_note * F(1.5)))
        imp_sub = imp - s.strike if gest == 7 else F(0.0)
        s.strike = F(0.0)
        if gest != 6 and abs(P[20] - F(64.0)) > F(0.5):
            gn = clip((P[20] - F(64.0)) * F(1.0 / 63.0), -1.0, 1.0)
            s.gl_amt = gn * F(12.0) * (F(1.0) - crv(t_note * recip(F(0.03) + (F(1.0) - speedk) * F(0.6)), shape))
        if loose > F(0.0) and tgt != F(0.0):
            wander(w, 2.5, rng2, 12)
            tgt *= F(1.0) + loose * F(0.45) * w[12]
        if shape == 2 and t_note < F(0.15):
            ppush += F(0.3) * ex(-t_note * F(20.0))
        stress = mn(F(1.0), F(0.45) * press * press + F(0.25) * rosin * inst + F(0.5) * inst * inst
                    + F(0.3) * rough + F(0.25) * scrap + sadd)
        if stress > F(0.6):
            stress = F(0.6) + F(0.25) * tanh_r((stress - F(0.6)) * F(4.0))
        if morph > F(0.01) and gest in (2, 4, 5, 7) and tgt == F(0.0) and t_note < F(0.05) + F(0.6) * morph \
                and rng2.u() < morph * (F(0.1) + dens * F(0.6)):
            imp += morph * F(0.5) * rng2.u()
        if mat == 2 and P[6] > F(32.0) and t_note < F(0.05) + grain * F(0.4) \
                and rng2.u() < (P[6] - F(32.0)) * F(0.25 / 95.0):
            imp += F(0.25) * (F(0.4) + F(0.6) * rng2.u())
        if imp > F(0.0):
            s.p_n = max(4, int((F(0.00015) + one_m_snap * one_m_snap * F(0.004)) * FS))
            s.p_i = 0
            s.p_a = imp
        if mat == 2 and tgt != F(0.0) and s.prev_tgt == F(0.0) and gest in (2, 3, 4):
            s.p_n = max(4, int((F(0.0002) + one_m_snap * one_m_snap * F(0.003)) * FS))
            s.p_i = 0
            s.p_a = F(0.3) + F(0.5) * snap
        s.prev_tgt = tgt
        if shape == 3:
            wander(w, 5.0, rng, 8)
            tgt *= F(1.0) + F(0.5) * w[8]
        if morph > F(0.01) and tgt != F(0.0):
            s.part_t -= DT
            pmin = F(0.002) + (F(1.0) - dens) * F(0.08)
            if s.part_t <= F(0.0):
                s.part_t = pmin * (F(0.5) + rng.u())
                s.burst = F(1.0) if rng.u() < F(0.3) + F(0.7) * cohe else F(0.3)
                s.mo_c = morph * morph * F(350.0) * rng2.bi()
            tgt = tgt * (F(1.0) - morph) + tgt * morph * s.burst * (F(2.0) if s.part_t > pmin * F(0.6) else F(0.0))
        # pitch
        s.vib_env = mn(F(1.0), s.vib_env + DT * F(1.0 / 0.6))
        v = s.vib_ph + (F(4.5) + F(2.0) * inst) * DT
        s.vib_ph = v - F(np.floor(v))
        wander(w, 0.6, rng, 0)
        wander(w, 11.0, rng, 2)
        wander(w, 7.0, rng, 4)
        vib_s = sinf(TWO_PI * s.vib_ph)
        cents = vibr * F(45.0) * s.vib_env * vib_s + drift * F(25.0) * w[0] + stress * stress * F(25.0) * w[2]
        glp = s.gl_amt * F(100.0) if distk != 3 else F(0.0)
        cents += glp
        if morph > F(0.01):
            cents += s.mo_c
        alpha = (F(0.15) + F(0.6) * press) * snap * (F(0.0) if mat == 2 else F(0.25))
        tau = F(0.01) + mass * F(0.12)
        ov = F(1200.0) * log2f(F(1.0) + alpha * ex(-t_note * recip(tau)))
        cents += ov
        s.sq *= F(0.6703200460)                               # exp(-dt / 0.08)
        if mat == 0 and stress > F(0.35) and tgt != F(0.0) and rng.u() < stress * stress * stress * DT * F(6.0):
            s.sq = F(0.6) + F(0.4) * stress
        f = s.f0 * exp2(cents * F(1.0 / 1200.0))
        # per-block coefficients
        per = FS * recip(mx(f, F(25.0)))
        lpc = (F(0.32) + F(0.55) * (F(1.0) - visc * F(0.8)) * (F(0.55) + F(0.45) * tens)) * (F(1.0) - F(0.3) * mass)
        lpc = clip(lpc * recip(sqrtf(damp_x)) if damp_x != F(1.0) else lpc, 0.08, 0.95)
        lpd = (F(1.0) - lpc) * recip(lpc)
        tot = mn(per - lpd, F(NBR - 4))
        beta = F(0.04) + pos * F(0.4)
        db = clip(tot * beta, 1.5, NBR - 4.0)
        dn = clip(tot - db, 1.5, NBR - 4.0)
        half = clip(db + per * F(0.5), 2.0, NBR - 4.0)
        a_hp = recip(F(1.0) + TWO_PI * F(0.45) * f * IFS)
        lossm = F(0.995) - F(0.4) * morph * morph if morph > F(0.0) else F(0.995)
        stiff = (P[0] - F(42.0)) * F(1.0 / 85.0) if P[0] > F(42.0) else F(0.0)
        fapc = F(-0.9) * stiff
        if stiff > F(0.0):
            fad = (F(1.0) - fapc) * recip(F(1.0) + fapc)
            if fad > tot * F(0.25):
                fad = tot * F(0.25)
                fapc = (F(1.0) - fad) * recip(F(1.0) + fad)
            db = clip(db - fad, 1.5, NBR - 4.0)
        if P[5] > F(55.0):
            gg = (P[5] - F(55.0)) * F(1.0 / 72.0)
            ghold = 1 + int(gg * gg * F(60.0))
        else:
            ghold = 1
        crk = (P[6] - F(32.0)) * F(1.0 / 95.0) if P[6] > F(32.0) else F(0.0)
        pr = mn(F(1.0), press * F(0.85) + ppush + F(0.3) * stress * w[4])
        slope = F(5.5) - pr * F(4.2)
        offset = F(0.92) - rosin * F(0.3)
        breakup = (pr - F(0.7)) * F(1.6) if pr > F(0.7) else F(0.0)
        att = F(1.0) - ex(-recip(atk * FS))
        rel = F(0.000694203)                                  # 1 - exp(-1 / (0.03 fs))
        scr = mn(F(1.0), F(0.5) * scrap + noisy + stress * F(0.15))
        if scr > F(0.3):
            scr = F(0.3) + (scr - F(0.3)) * F(0.5)
        fs_b = exp2(-mass * F(1.9))
        rr = ex(-recip((F(0.02) + F(0.03) * (F(1.0) - visc)) * FS))
        bc = [F(0.0)] * 4; bs = [F(0.0)] * 4
        for k in range(4):
            wk_ = TWO_PI * BFR[k] * fs_b * IFS
            bc[k] = rr * cosf(wk_)
            bs[k] = rr * sinf(wk_)
        fcen = F(300.0) * exp2(form * F(4.5) + s.env_e * F(2.0) * form)
        g_f = tanf(PI * mn(fcen, F(16000.0)) * IFS)
        kq = F(1.0 / 3.0)
        fa1 = recip(F(1.0) + g_f * (g_f + kq)); fa2 = g_f * fa1; fa3 = g_f * fa2
        nm = 2 + int(F(4.0) * voices + F(0.5))
        mc = [F(0.0)] * 6; ms = [F(0.0)] * 6
        if mat == 1:
            ppart = F(1.0) + part
            for k in range(6):
                har = F(k + 1)
                mr = powf(MEM[k] + (har - MEM[k]) * tens, ppart)
                fk = f * mr * (F(1.0) + inst * F(0.02) * s.env_e * F(k + 1))
                fk *= exp2(s.soff[k] * spread * F(3.0 / 1200.0))
                fk = mn(fk, F(20000.0))
                dec = (F(0.04) + (F(1.0) - visc) * F(0.9)) * (F(1.0) + mass) * recip((F(1.0) + F(0.6) * F(k)) * damp_x)
                dec *= F(1.0) - F(0.85) * morph
                r = ex(-recip(dec * FS))
                mc[k] = r * cosf(TWO_PI * fk * IFS)
                ms[k] = r * sinf(TWO_PI * fk * IFS)
        if mat == 2:
            el = F(0.03) + (F(1.0) - tens) * F(0.15) + press * F(0.08)
            sk_E = s.sk_E
            sk_cut = mn(F(16000.0), (f * (F(1.0) + F(3.0) * tens + F(30.0) * sk_E * (F(0.3) + press))
                                     + F(2500.0) * snap * sk_E) * (F(1.0) - F(0.4) * visc))
            cut_l = mn(F(18000.0), f * (F(3.0) + F(25.0) * tens) * (F(1.0) + F(0.5) * sk_E) * (F(1.0) - F(0.5) * visc))
            a_lp = F(1.0) - ex(-TWO_PI * cut_l * IFS)
            fsk = f * (F(1.0) + el * F(2.5) * mx(F(0.0), sk_E - s.sk_Es))
            perk = FS * recip(fsk)
            dmax = perk * F(1.0 / 16.0)
            apc = F(-0.95) * powf(part, 0.7)
            if (F(1.0) - apc) * recip(F(1.0) + apc) > dmax:
                apc = (F(1.0) - dmax) * recip(F(1.0) + dmax)
            Lsk = clip(perk - (F(1.0) - a_lp) * recip(a_lp) - F(4.0) * (F(1.0) - apc) * recip(F(1.0) + apc), 2.0, NBR - 4.0)
            om = F(1.0) - visc
            dsk = (F(0.05) + om * sqrtf(om) * F(2.5)) * (F(0.5) + mass) * recip(damp_x) * (F(1.0) - F(0.8) * morph)
            gsk = exp2(F(-3.0) * LOG2_10 * recip(dsk * fsk))
            nlk = F(1.0) + F(2.0) * inst + F(1.5) * stress
            inlk = recip(nlk)
            g2 = tanf(PI * mn(sk_cut, F(18000.0)) * IFS)
            k2 = recip(F(0.6) + inst * F(2.5))
            b1 = recip(F(1.0) + g2 * (g2 + k2)); b2 = g2 * b1; b3 = g2 * b2
            skd = max(1, int(Lsk * (F(0.03) + F(0.47) * pos)))
        wander(w, F(0.8) + F(3.0) * (F(1.0) - visc), rng2, 14)     # every block (the model's stream)
        if mat == 3:
            melt = crv(t_note * recip((F(0.4) + visc * F(4.0)) * (F(0.5) + (F(1.0) - speedk))), shape)
            fl_f = f * exp2(-(F(1.0) - tens) * F(160.0 / 1200.0) * melt)
            fl_cut = mn(F(16000.0), fl_f * (F(2.0) + F(22.0) * tens * (F(1.0) - F(0.7) * melt)) * (F(1.0) - F(0.5) * visc))
            fl_a = F(1.0) - ex(-TWO_PI * fl_cut * IFS)
            fl_apc = F(-0.5) * part - F(0.3) * melt * (F(0.5) + F(0.5) * w[14])
            perf = FS * recip(fl_f)
            dmx = perf * F(1.0 / 16.0)
            if (F(1.0) - fl_apc) * recip(F(1.0) + fl_apc) > dmx:
                fl_apc = (F(1.0) - dmx) * recip(F(1.0) + dmx)
            fl_L = clip(perf - (F(1.0) - fl_a) * recip(fl_a) - F(4.0) * (F(1.0) - fl_apc) * recip(F(1.0) + fl_apc), 2.0, NBR - 4.0)
            dfl = (F(0.3) + F(2.0) * (F(1.0) - visc)) * (F(0.5) + mass) * (F(1.0) - F(0.5) * melt) * recip(damp_x) \
                * (F(1.0) - F(0.8) * morph)
            gfl = exp2(F(-3.0) * LOG2_10 * recip(dfl * fl_f))
            drate = (F(0.5) + dens * dens * F(30.0)) * (F(0.3) + F(0.7) * melt) * (F(1.0) + F(2.0) * stress)
            drp_dec = ex(-recip((F(0.01) + F(0.05) * (F(1.0) - visc) + F(0.03) * grain) * FS))
        pw0 = max(4, int((F(0.00015) + one_m_snap * one_m_snap * F(0.004)) * FS))
        av_dec = ex(-recip((F(0.01) + grain * F(0.08)) * FS))
        wpos = [F(0.0)] * 6
        if mat == 1:
            for k in range(6):
                wpos[k] = F(0.25) + F(0.75) * abs(sinf(PI * F(k + 1) * (F(0.03) + F(0.47) * pos)))
        # filaments
        nsec = 0
        if mode >= 1:
            nsec = QN_MASS[qual]
            nsec = max(1, int(F(F(nsec) * (F(0.25) + F(0.75) * voices) * (F(0.4) + F(0.6) * s.vel)) + F(0.5)))
        elif voices > F(0.01) and (mat == 0 or mat == 2):
            nsec = max(1, int(F(QN_SOLO[qual]) * voices + F(0.5)))
        sper = [F(0.0)] * NSEC
        base_c = cents - glp - ov
        for k in range(nsec):
            wander(s.sdrift, F(0.3) + F(0.8) * drift, rng, 2 * k)
            vv = s.svph[k] + (F(4.0) + F(0.37) * F(k) + F(2.0) * inst) * DT
            s.svph[k] = vv - F(np.floor(vv))
            if lock > F(0.0):
                dphi = s.vib_ph - s.svph[k]
                dphi -= F(np.floor(dphi + F(0.5)))
                s.svph[k] += dphi * lock * F(0.2)
            uk = (F(k) * recip(F(max(1, nsec - 1))) - F(0.5)) * F(2.0)
            sc = F(1.0); gk = F(0.0)
            if gest == 6:
                gp = t_note * recip(F(0.4) + (F(1.0) - speedk) * F(3.0))
                if distk == 0:
                    gk = s.gl_amt * F(100.0)
                elif distk == 1:
                    gk = gn * F(1200.0) * crv(gp * recip(F(1.0) + F(0.35) * uk), shape) * (F(1.0) + F(0.15) * uk)
                elif distk == 2:
                    gk = s.gl_amt * F(100.0) * ALTK[k] * (F(1.0) + F(0.75) * uk)
                else:
                    pp = crv(gp, shape)
                    sc = F(1.0) + gn * pp * F(3.0) if gn > F(0.0) else F(1.0) + gn * pp
            dr = s.sdrift[2 * k] * (F(1.0) - lock) + w[0] * lock
            c = s.soff[k] * sc + drift * F(60.0) * dr * (F(1.0) + loose) \
                + vibr * F(40.0) * s.vib_env * sinf(TWO_PI * s.svph[k]) + gk \
                + stress * F(30.0) * w[2] * SGNK[k]
            fk = s.f0 * exp2((c + base_c) * F(1.0 / 1200.0))
            sper[k] = mx(mn(FS * recip(mx(fk, F(25.0))), F(NSL - 4)), F(2.0))   # at least 2: a read never meets the write
        prate = F(5.0) + dens * dens * F(2500.0)
        sgn = rsq = recip(sqrtf(F(1.0) + (prate * (abs(s.bow) * F(6.0) + imp * F(40.0))
                                          + s.aval * F(30.0) * (dens + F(0.2)) * prate) * F(1.0 / 400.0)))
        # -- samples --
        bowc = gest in (0, 1, 6, 8, 9)
        hpchain = gest != 0 and gest != 6 and gest != 8
        prate_fs = prate * IFS
        for i in range(SUB):
            nz = rng.bi()
            y = F(0.0)
            pv = F(0.0)
            if s.p_i < s.p_n:
                pn = F(s.p_n)
                pv = s.p_a * sqrtf(F(8.0) * recip(pn)) * sinf(PI * (F(s.p_i) + F(0.5)) * recip(pn))
                if s.p_i < 24:
                    pv += nz * snap * F(0.4) * s.p_a
                s.p_i += 1
            exv = F(0.0)
            if mat == 0:
                a0 = rd(s.br, NBR, s.wb, db)
                a1 = rd(s.nk, NBR, s.wk, dn)
                s.lp += (a0 - s.lp) * lpc
                if stiff > F(0.0):
                    fy = fapc * s.lp + s.f_ax - fapc * s.f_ay
                    s.f_ax = s.lp
                    s.f_ay = fy
                    brr = -fy * lossm
                else:
                    brr = -s.lp * lossm
                nr = -a1
                sv = brr + nr
                s.bow += (tgt - s.bow) * (att if tgt != F(0.0) else rel)
                contact = F(1.0) if (tgt != F(0.0) or bowc) else mn(F(1.0), abs(s.bow) * F(60.0))
                dv = s.bow - sv
                bt = bow_k(dv, slope, offset)
                if breakup > F(0.0):
                    bt *= F(1.0) + breakup * F(0.6) * nz
                slip = F(1.0) - bt
                gz = nz
                if ghold > 1:
                    s.g_cnt -= 1
                    if s.g_cnt <= 0:
                        s.g_hold = nz
                        s.g_cnt = ghold
                    gz = s.g_hold * F(1.4)
                nv = (dv * bt + gz * scr * slip * F(0.06) * (F(0.4) + pr)) * contact
                if crk > F(0.0) and s.bow != F(0.0) and rng2.u() < crk * crk * F(0.004):
                    nv += rng2.bi() * F(0.35) * crk
                nv += pv * F(0.9)
                s.nk[s.wk] = clip(brr + nv, -2.0, 2.0)
                s.br[s.wb] = clip(nr + nv, -2.0, 2.0)
                s.wb = s.wb + 1 if s.wb + 1 < NBR else 0
                s.wk = s.wk + 1 if s.wk + 1 < NBR else 0
                y = a0
                if s.sq > F(0.01):
                    y = a0 * (F(1.0) - s.sq) + s.sq * F(0.8) * (a0 + rd(s.br, NBR, s.wb, half))
                if hpchain:
                    s.h1 = a_hp * (s.h1 + y - s.hx1); s.hx1 = y
                    s.h2 = a_hp * (s.h2 + s.h1 - s.hx2); s.hx2 = s.h1
                    s.h3 = a_hp * (s.h3 + s.h2 - s.hx3); s.hx3 = s.h2
                    s.h4 = a_hp * (s.h4 + s.h3 - s.hx4); s.hx4 = s.h3
                    y = s.h4
                exv = nv
                hn = nz - s.hp
                s.hp += (nz - s.hp) * F(0.25)
                y += hn * air * abs(s.bow) * F(0.3)
            elif mat == 2:
                s.bow += (tgt - s.bow) * (att if tgt != F(0.0) else rel)
                a = rd(s.br, NBR, s.wb, Lsk)
                s.sk_lp += (a - s.sk_lp) * a_lp
                xa = s.sk_lp
                ap = s.sk_ap
                for q in range(4):
                    apy = apc * xa + ap[2 * q] - apc * ap[2 * q + 1]
                    ap[2 * q] = xa
                    ap[2 * q + 1] = apy
                    xa = apy
                vv = tanh_r(xa * gsk * nlk) * inlk
                dcy = vv - s.sk_dx + F(0.995) * s.sk_dy
                s.sk_dx = vv
                s.sk_dy = dcy
                vv = dcy
                drive = pv * F(0.8)
                if s.bow != F(0.0):
                    dv = s.bow - vv * F(0.5)
                    bt = bow_k(dv, slope, offset)
                    reg = recip(F(1.0) + F(6.0) * mx(F(0.0), s.sk_E - (F(0.2) + F(0.5) * press)))
                    drive += (dv * bt * F(1.6) + nz * scr * (F(1.0) - bt) * F(0.03)) * reg
                if stress > F(0.3) and rng2.u() < stress * stress * stress * F(0.002):
                    drive += nz * F(0.2) * stress
                exv = drive
                if pv != F(0.0):
                    jx = s.wb - skd
                    if jx < 0:
                        jx += NBR
                    s.br[jx] -= pv * F(0.8)
                s.br[s.wb] = clip(vv + drive, -2.0, 2.0)
                s.wb = s.wb + 1 if s.wb + 1 < NBR else 0
                v3 = a - s.sk_s2
                v1 = b1 * s.sk_s1 + b2 * v3
                v2 = s.sk_s2 + b2 * s.sk_s1 + b3 * v3
                s.sk_s1 = F(2.0) * v1 - s.sk_s1
                s.sk_s2 = F(2.0) * v2 - s.sk_s2
                y = v2 * F(2.2) + nz * air * F(0.02) * (abs(s.bow) + abs(pv))
                e = abs(y) * F(2.5)
                s.sk_E += (e - s.sk_E) * (F(0.01) if e > s.sk_E else F(0.0006))
                if s.sk_E > F(1.0):
                    s.sk_E = F(1.0)
                s.sk_Es += (s.sk_E - s.sk_Es) * (F(0.00015) + F(0.0006) * (F(1.0) - mass))
            elif mat == 1:
                p_on = rng.u() < prate_fs * (abs(s.bow) * F(6.0) + imp * F(40.0) + s.aval * F(30.0) * (dens + F(0.2)))
                d = F(0.0)
                if p_on:
                    d = (F(0.3) + F(0.7) * rng.u()) * (F(1.0) + cohe * F(2.0) * s.burst) * F(0.012) * (F(0.4) + press) * sgn
                    s.aval = mn(F(1.5), s.aval + cohe * (F(0.25) + F(0.5) * stress) * (F(0.5) + F(0.5) * rosin))
                s.aval *= av_dec
                d += pv * F(0.08)
                exv = d
                acc = F(0.0)
                md = s.md
                pk = F(1.0)
                hpart = F(1.0) - part * F(0.5)
                for k in range(6):
                    re = mc[k] * md[k, 0] - ms[k] * md[k, 1]
                    if k < nm and d != F(0.0):       # a draw only when a grain lands (lean, 2026-11-17)
                        re += d * (F(0.4) + F(0.6) * rng.u()) * pk * wpos[k]
                    im = ms[k] * md[k, 0] + mc[k] * md[k, 1]
                    md[k, 0] = re
                    md[k, 1] = im
                    acc += im
                    pk *= hpart
                y = acc * F(0.5) * (F(1.0) - F(0.5) * morph) + nz * d * (grain * F(2.0) + morph * F(3.0))
                s.hp += (nz - s.hp) * F(0.3)
                y += s.hp * abs(s.bow) * (scrap * F(0.12) + air * F(0.06)) + nz * s.aval * air * F(0.01)
                s.bow += (tgt - s.bow) * (att if tgt != F(0.0) else rel)
            else:
                s.bow += (tgt - s.bow) * (att if tgt != F(0.0) else rel)
                a = rd(s.br, NBR, s.wb, fl_L)
                s.sk_lp += (a - s.sk_lp) * fl_a
                xa = s.sk_lp
                ap = s.sk_ap
                for q in range(4):
                    apy = fl_apc * xa + ap[2 * q] - fl_apc * ap[2 * q + 1]
                    ap[2 * q] = xa
                    ap[2 * q + 1] = apy
                    xa = apy
                vv = xa * gfl
                dcy = vv - s.sk_dx + F(0.995) * s.sk_dy
                s.sk_dx = vv
                s.sk_dy = dcy
                vv = dcy
                drive = pv * F(0.6)
                if s.bow != F(0.0):
                    dv = s.bow - vv * F(0.5)
                    bt = bow_k(dv, slope, offset)
                    reg = recip(F(1.0) + F(6.0) * mx(F(0.0), s.sk_E - (F(0.15) + F(0.4) * press)))
                    drive += dv * bt * F(1.2) * reg
                if (gate or t_note < F(2.0)) and rng2.u() < drate * (F(1.0) + s.aval * F(4.0)) * IFS:
                    j = int(rng2.u() * F(3.999))
                    uu = rng2.u()
                    kh = 1 + int(powf(uu, F(0.5) + pos * F(1.5)) * (F(1.0) + part * F(6.0)))
                    s.bub_f[j] = fl_f * F(kh) * (F(1.0) + F(0.004) * rng2.bi())
                    s.bub_a[j] = (F(0.3) + F(0.7) * rng2.u()) * (F(0.3) + press) * F(0.5)
                    s.bub_r[j] = F(0.0)
                    drive += s.bub_a[j] * F(0.15)
                    s.aval = mn(F(1.5), s.aval + cohe * F(0.5))
                s.aval *= av_dec
                drs = F(0.0)
                for j in range(4):
                    if s.bub_a[j] > F(1e-4):
                        s.bub_r[j] += IFS
                        fj = s.bub_f[j] * (F(1.0) + (F(1.0) - visc) * F(3.0) * mn(s.bub_r[j], F(0.03)))
                        bp = s.bub_p[j] + fj * IFS
                        s.bub_p[j] = bp - F(np.floor(bp))
                        drs += s.bub_a[j] * sinf(TWO_PI * s.bub_p[j])
                        s.bub_a[j] *= drp_dec
                exv = drive + drs * F(0.1)
                s.br[s.wb] = clip(vv + drive, -2.0, 2.0)
                s.wb = s.wb + 1 if s.wb + 1 < NBR else 0
                y = a * F(1.6) + drs * F(0.35)
                s.hp += (nz - s.hp) * F(0.08)
                y += s.hp * (abs(s.bow) + drs) * air * F(0.1)
                e = abs(a) * F(2.5)
                s.sk_E += (e - s.sk_E) * (F(0.01) if e > s.sk_E else F(0.0006))
                if s.sk_E > F(1.0):
                    s.sk_E = F(1.0)
            # filaments
            yprev = y
            if nsec > 0:
                sacc = F(0.0)
                for k in range(nsec):
                    sbk = s.sb[k]
                    a = rd(sbk, NSL, s.sw[k], sper[k])
                    s.slp[k] += (a - s.slp[k]) * lpc
                    if mode == 2:
                        v_s = -s.slp[k] * F(0.996)
                    else:
                        v_s = s.slp[k] * F(0.996) - s.sdx[k] + F(0.995) * s.sdy[k]
                        s.sdx[k] = s.slp[k] * F(0.996)
                        s.sdy[k] = v_s
                    if mode == 0:
                        nvk = yprev * F(0.03) * (F(0.4) + F(1.2) * cohe)
                    elif mat == 0 or mat == 1:
                        fac = F(1.0) + FACK[k] * (F(1.0) - lock) \
                            * (F(1.0) + F(2.0) * loose)
                        ent = clip(entry * F(nsec) - F(k), 0.0, 1.0) if gest == 8 else F(1.0)
                        s.sbow[k] += (tgt * fac * ent - s.sbow[k]) * (att if tgt != F(0.0) else rel)
                        dvk = s.sbow[k] - v_s
                        btk = bow_k(dvk, slope * F(1.1), offset)
                        ck = F(1.0) if (tgt != F(0.0) or bowc) else mn(F(1.0), abs(s.sbow[k]) * F(60.0))
                        nvk = (dvk * btk + nz * scr * (F(1.0) - btk) * F(0.05)) * ck
                        if imp_sub > F(0.0) and i < 6:
                            nvk += imp_sub * F(0.25) * IMPK[k] \
                                * (F(1.0) - F(i) * F(1.0 / 6.0))
                    else:
                        nvk = exv * F(0.3)
                    if s.simp > F(0.0) and mode >= 1 and s.scnt[k] < pw0:
                        s.scnt[k] += 1
                        if s.scnt[k] > 0:
                            nvk += s.simp * F(0.5) * sqrtf(F(8.0) * recip(F(pw0))) * sinf(PI * F(s.scnt[k]) * recip(F(pw0)))
                    sbk[s.sw[k]] = clip(v_s + nvk, -2.0, 2.0)
                    s.sw[k] = s.sw[k] + 1 if s.sw[k] + 1 < NSL else 0
                    sacc += a
                if mode == 0:
                    y = y + sacc * F(0.6) * voices
                else:
                    y = y * (F(0.55) if ens else F(0.8)) + sacc * F(1.6) * recip(sqrtf(F(nsec)) + F(1.0))
            if mode == 3:
                if rng.u() < prate_fs * (abs(s.bow) * F(8.0) + F(0.2)):
                    s.burst = mn(F(1.5), s.burst + F(0.5) * (F(0.3) + cohe))
                s.burst *= F(0.9995) - (F(1.0) - cohe) * F(0.002)
                s.hp += (nz - s.hp) * (F(0.05) + F(0.4) * part)
                y += s.hp * s.burst * F(0.12) * (F(0.3) + grain)
            if ens and dens > F(0.25):
                if rng2.u() < prate_fs * (abs(s.bow) * F(8.0) + F(0.1)):
                    s.cl_b = mn(F(1.5), s.cl_b + F(0.5) * (F(0.3) + cohe))
                s.cl_b *= F(0.9995) - (F(1.0) - cohe) * F(0.002)
                s.cl_hp += (nz - s.cl_hp) * (F(0.05) + F(0.4) * part)
                y += s.cl_hp * s.cl_b * F(0.12) * (F(0.3) + grain) * (dens - F(0.25)) * F(1.0 / 0.75)
            bo = F(0.0)
            body = s.body
            for k in range(4):
                re = bc[k] * body[k, 0] - bs[k] * body[k, 1] + y * BGN[k]
                im = bs[k] * body[k, 0] + bc[k] * body[k, 1]
                body[k, 0] = re
                body[k, 1] = im
                bo += im
            y = y + bodyk * bo * F(1.5)
            v3 = y - s.fm2
            v1 = fa1 * s.fm1 + fa2 * v3
            v2 = s.fm2 + fa2 * s.fm1 + fa3 * v3
            s.fm1 = F(2.0) * v1 - s.fm1
            s.fm2 = F(2.0) * v2 - s.fm2
            y = y * (F(1.0) - form * F(0.6)) + v1 * form * F(1.8)
            ee = mn(F(1.0), abs(exv) * F(4.0))
            s.env_e += (ee - s.env_e) * (F(0.02) if ee > s.env_e else F(0.0015))
            s.amp += ((F(1.0) if gate else F(0.0)) - s.amp) * (F(0.01) if gate else F(0.0004))
            out[i] = tanh_r(y * F(0.6)) * s.amp
        if not gate and s.amp < REST_AMP:     # released and under -80 dB: the voice rests
            s.rest = True
        return out


def knob_option(k, n):
    """a page 4 knob (0..127) as its option of N: (k N) >> 7"""
    return min((int(k) * n) >> 7, n - 1)


def eff_of(knobs) -> list:
    """the 32 knobs as the voice reads them: pages 1-3 as they are, page 4 as options"""
    out = [float(int(k)) for k in knobs[:24]]
    for j, name in enumerate(CONTROLS[24:]):
        out.append(float(knob_option(knobs[24 + j], len(CHOICES[name]))))
    return out


def option_knob(o, n):
    """the knob in the middle of option O's span (for tests and presets)"""
    ks = [k for k in range(128) if knob_option(k, n) == o]
    return (ks[0] + ks[-1]) // 2


def slot_seed(t: int) -> int:
    """the seed of slot T's voice (its noises): 0x2545F491 + t, odd"""
    return (0x2545F491 + t) | 1


class SlotVoice(Voice):
    """the voice as the DN2 drives it, a block at a time: the 32 knobs (0..127), the trig, its
    note (float) and velocity (0..127), the note-off (mask 36)"""

    def __init__(self, slot: int, bpm=120.0):
        super().__init__(slot_seed(slot), bpm)
        self.slot = slot
        self.become()                          # the DSP's first block: a state it never wrote

    def dsp_block(self, knobs, trig: bool, note: float, vel: int, off: bool) -> np.ndarray:
        P = eff_of(knobs)
        if trig:
            self.note(P, note, F(min(int(vel), 127)) * INV127)
        return self.block(P, off=off)


def render(P, notes, secs, seed=0x2545F491, bpm=120.0):
    """the audition model's play(): P one panel (a list of 32, page 4 as options), notes
    (t s, note, vel 0..1, gate s); the gate's end is a note-off in the block where the model's
    gate count runs out (a later note voids an earlier note's off, as the model's count resets)"""
    v = Voice(seed, bpm)
    nblk = int(secs * 48000) // SUB
    ev = sorted((int(t * 48000), n, vel, int(g * 48000)) for t, n, vel, g in notes)
    on_blk = {}
    for e in ev:                               # the block each note lands in (the model's test)
        b = 0
        while not e[0] < b * SUB + SUB:
            b += 1
        on_blk.setdefault(b, []).append(e)
    offs = set()
    starts = sorted(on_blk)
    for i, b in enumerate(starts):
        g = on_blk[b][-1][3]
        ob = b + max(1, -(-g // SUB)) - 1
        if i + 1 < len(starts) and starts[i + 1] <= ob:
            continue
        offs.add(ob)
    out = np.zeros(nblk * SUB, F)
    for b in range(nblk):
        for e in on_blk.get(b, ()):
            v.note(P, e[1], e[2])
        v.block(P, out[b * SUB:(b + 1) * SUB], off=b in offs)
    return out
