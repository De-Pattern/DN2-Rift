"""SILT audition model (the sound the owner approved, 2026-11; numba, float64). live.py is this on the DSP's arithmetic. (RIFT's third machine): material synthesis, after the owner's design doc.

A voice = a primary material voice (FIBER's bowed waveguide, after Ravel's RESIN; SKIN's elastic
modes; SILT's particles; FLUID's droplets) + up to 8 secondary filaments (MASS) + a particle
cloud (SWARM), all driven by one gesture program (BOW, SCRAPE, STACC, TREMO, SPICC, LEGNO, GLISS,
FRACT). 48 kHz, controls read every 32-sample block, as the DN2 would. Sound design first: the
SHARC port follows once the owner has heard WRAITH, RUBBER STUDY and POLYMORPHIA.

Controls (0..127; page 4 choices as option numbers):
  SYN1 MATTER:    PART TENS MASS COHE VISC GRAIN DENS BODY
  SYN2 CONTACT:   PRESS SPEED POS ROSIN SCRAP SNAP AIR INST
  SYN3 STRUCTURE: SPREAD VOICES DRIFT VIBR GLISS FORM ROUGH MORPH
  SYN4 CONFIG:    MAT GEST MODE DIST LOOP SHAPE TUNE QUAL
"""
from __future__ import annotations

import numpy as np
from numba import njit

FS = 48000.0
SUB = 32
CONTROLS = ("PART", "TENS", "MASS", "COHE", "VISC", "GRAIN", "DENS", "BODY",
            "PRESS", "SPEED", "POS", "ROSIN", "SCRAP", "SNAP", "AIR", "INST",
            "SPREAD", "VOICES", "DRIFT", "VIBR", "GLISS", "FORM", "ROUGH", "MORPH",
            "MAT", "GEST", "MODE", "DIST", "LOOP", "SHAPE", "TUNE", "QUAL")
MATS = ("FIBER", "SILT", "SKIN", "FLUID")
GESTS = ("BOW", "SCRAPE", "STACC", "TREMO", "SPICC", "LEGNO", "GLISS", "FRACT", "SWELL", "QUAKE")
MODES = ("SOLO", "MASS", "MASS-8", "SWARM")      # MASS in pitch; MASS-8 an octave below (v1's mass)
DISTS = ("NARROW", "WIDE", "BIMODAL", "ASYM")
LOOPS = ("OFF", "1/16", "1/8", "1/4", "FREE")
SHAPES = ("SOFT", "LINEAR", "EXP", "CHAOTIC")
TUNES = ("FREE", "SCALE", "MICRO", "HARM")
QUALS = ("ECO", "NORMAL", "DEEP")
DEFAULTS = dict(PART=42, TENS=66, MASS=53, COHE=70, VISC=43, GRAIN=55, DENS=28, BODY=74,
                PRESS=60, SPEED=64, POS=30, ROSIN=64, SCRAP=10, SNAP=40, AIR=10, INST=20,
                SPREAD=0, VOICES=64, DRIFT=20, VIBR=30, GLISS=64, FORM=40, ROUGH=10, MORPH=0,
                MAT=0, GEST=0, MODE=0, DIST=0, LOOP=0, SHAPE=1, TUNE=0, QUAL=1)

NBR = 2048          # waveguide segments (bridge, nut): down to about 24 Hz
NSEC = 8            # secondary filaments
NSL = 1024          # a filament's loop


@njit(cache=False)
def xs(s):
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF
    return s & 0xFFFFFFFF


@njit(cache=False)
def bi(st):
    st[0] = xs(st[0])
    v = st[0]
    if v >= 0x80000000:
        v -= 0x100000000
    return v / 2147483648.0


@njit(cache=False)
def rd(buf, n, w, d):
    di = int(d)
    fr = d - di
    r0 = w - di
    if r0 < 0:
        r0 += n
    r1 = r0 - 1
    if r1 < 0:
        r1 += n
    return buf[r0] + (buf[r1] - buf[r0]) * fr


@njit(cache=False)
def wander(x, k, dt, st, slot):
    # a value about +-1 leaking toward fresh noise at rate k / s (RESIN's rs_wander)
    a = min(1.0, k * dt * 2.0)
    x[slot + 1] += (bi(st) * 1.7 - x[slot + 1]) * a
    x[slot] += (x[slot + 1] - x[slot]) * min(1.0, k * dt)


@njit(cache=False)
def crv(x, shape):
    # SHAPE: a gesture's contour (SOFT, LINEAR, EXP, CHAOTIC=LINEAR plus a wander applied elsewhere)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if shape == 0:
        return x * x * (3.0 - 2.0 * x)
    if shape == 2:
        return x ** 2.5
    return x


@njit(cache=False)
def render(PK, events, nsamp, seed, bpm):
    """PK: keyframes (rows of 32 controls, spread evenly over the render; one row = static);
    events: rows (sample, note, vel, gate_len_samples).
    -> mono float32 of nsamp samples (with a simple AMP: the gate, then a release)"""
    out = np.zeros(nsamp, np.float32)
    st = np.array([seed | 1], np.int64)
    nkf = PK.shape[0]
    P = PK[0].copy()
    L4 = PK[0, 24:32].copy()
    sdx = np.zeros(NSEC); sdy = np.zeros(NSEC)
    sdel = np.zeros(NSEC); scnt = np.zeros(NSEC, np.int64); simp = 0.0
    sk_dx = 0.0; sk_dy = 0.0; sk_Es = 0.0
    sk_ap = np.zeros(8)
    sk_lp = 0.0; sk_E = 0.0; sk_s1 = 0.0; sk_s2 = 0.0
    p_n = 0; p_i = 0; p_a = 0.0
    aval = 0.0; prev_tgt = 0.0; loop_t = 0.0; loop_per = 1.0; yprev = 0.0; qph = 0.0
    cl_hp = 0.0; cl_b = 0.0; mo_c = 0.0
    h1 = 0.0; h2 = 0.0; hx1 = 0.0; hx2 = 0.0; h3 = 0.0; h4 = 0.0; hx3 = 0.0; hx4 = 0.0
    f_ax = 0.0; f_ay = 0.0; g_hold = 0.0; g_cnt = 0
    st2 = np.array([(seed * 7) | 1], np.int64)      # the new randomness, apart from v1's stream
    # --- state ---
    br = np.zeros(NBR); nk = np.zeros(NBR); wb = 0; wk = 0
    lp = 0.0; bow = 0.0; hp = 0.0
    body = np.zeros((4, 2))
    sb = np.zeros((NSEC, NSL)); sw = np.zeros(NSEC, np.int64); slp = np.zeros(NSEC); sbow = np.zeros(NSEC)
    soff = np.zeros(NSEC); sdrift = np.zeros(2 * NSEC); svph = np.zeros(NSEC); sgl = np.zeros(NSEC)
    md = np.zeros((6, 2))            # SKIN's / SILT's modes (re, im)
    bub_f = np.zeros(4); bub_a = np.zeros(4); bub_p = np.zeros(4); bub_r = np.zeros(4)
    wnd = np.zeros(16)               # wanderers: drift, quiver, jitter, scrape-speed, gliss, spare
    fm1 = 0.0; fm2 = 0.0             # FORM's band-pass
    skf = 0.0; skf2 = 0.0            # SKIN's tracking low-pass
    env_e = 0.0                      # excitation energy follower
    amp = 0.0
    # gesture state
    t_note = 0.0; f0 = 110.0; vel = 1.0; gate = 0; gate_left = 0; ev = 0; nev = events.shape[0]
    part_t = 0.0; burst = 0.0; strike = 0.0; sq = 0.0; vib_ph = 0.0; vib_env = 0.0
    gl_amt = 0.0
    nblk = nsamp // SUB
    for b in range(nblk):
        n0 = b * SUB
        if nkf > 1:
            xk = b * (nkf - 1) / max(1, nblk - 1)
            jk = int(xk)
            if jk > nkf - 2:
                jk = nkf - 2
            fk_ = xk - jk
            for c in range(24):
                P[c] = PK[jk, c] + (PK[jk + 1, c] - PK[jk, c]) * fk_
            for c in range(24, 32):
                P[c] = PK[jk, c] if fk_ < 0.5 else PK[jk + 1, c]
        # ---- notes (a trig: the gesture starts again) ----
        while ev < nev and events[ev, 0] < n0 + SUB:
            f0 = 440.0 * 2.0 ** ((events[ev, 1] - 69.0) / 12.0)
            vel = events[ev, 2]
            gate = 1
            gate_left = int(events[ev, 3])
            t_note = 0.0
            strike = 1.0
            burst = 0.0
            vib_env = 0.0
            gl_amt = 0.0
            # cluster offsets (cents), by DIST and TUNE, scaled by SPREAD
            for c in range(8):
                L4[c] = P[24 + c]
            dist = int(L4[3]); tune = int(L4[6])
            for k in range(NSEC):
                u = bi(st)
                if dist == 0:
                    c = u * 0.5
                elif dist == 1:
                    c = u
                elif dist == 2:
                    c = (0.6 + 0.4 * abs(u)) * (1.0 if k % 2 == 0 else -1.0)
                else:
                    c = abs(u) ** 0.7
                cents = c * (5.0 + P[16] * (195.0 / 127.0))     # up to about a whole tone, 2 semitones
                if tune == 1:                                   # SCALE: to the nearest semitone of the spread
                    cents = np.floor(cents / 100.0 + 0.5) * 100.0 if P[16] > 70 else cents
                elif tune == 2:                                 # MICRO: quarter tones
                    cents = np.floor(cents / 50.0 + 0.5) * 50.0
                elif tune == 3:                                 # HARM: toward partials 1, 2, 3/2
                    h = (0.0, 1200.0, 702.0, 1902.0, 2400.0, 386.0 + 1200.0, 969.0, 1200.0 + 702.0)[k]
                    cents = cents * 0.2 + h * min(1.0, P[16] / 64.0)
                soff[k] = cents
                sbow[k] = 0.0
                # the ensemble's strikes land unevenly: ROUGH and a loose COHE spread them
                sdel[k] = (0.002 + P[22] / 127.0 * 0.035 + (1.0 - P[3] / 127.0) * 0.02) * (bi(st2) * 0.5 + 0.5)
                scnt[k] = -int(sdel[k] * FS)
            g_ = int(L4[1])
            simp = (0.6 + 0.4 * vel) if (g_ == 5 or g_ == 7 or (int(L4[0]) == 2 and (g_ == 2 or g_ == 4))) else 0.0
            loop_t = 0.0
            loop_per = (0.04 + (1.0 - P[9] / 127.0) * 0.5) * (1.0 + (P[12] + P[22]) / 254.0 * 0.8 * bi(st2))
            ev += 1
        dt = SUB / FS
        t_note += dt
        if gate:
            gate_left -= SUB
            if gate_left <= 0:
                gate = 0
        loopk = int(L4[4])
        if gate and loopk > 0 and t_note > dt:
            if loopk < 4:
                loop_per = 60.0 / bpm * (0.25, 0.5, 1.0)[loopk - 1]
            loop_t += dt
            if loop_t >= loop_per:
                loop_t -= loop_per
                t_note = dt
                strike = 1.0
                for k in range(NSEC):
                    scnt[k] = -int(sdel[k] * FS)
                if loopk == 4:        # FREE: SPEED sets the rate, SCRAP and ROUGH unsettle it
                    loop_per = (0.04 + (1.0 - P[9] / 127.0) * 0.5) * (1.0 + (P[12] + P[22]) / 254.0 * 0.8 * bi(st2))
        # ---- controls ----
        part = P[0] / 127.0; tens = P[1] / 127.0; mass = P[2] / 127.0; cohe = P[3] / 127.0
        visc = P[4] / 127.0; grain = P[5] / 127.0; dens = P[6] / 127.0; bodyk = P[7] / 127.0
        press = P[8] / 127.0; speedk = P[9] / 127.0; pos = P[10] / 127.0; rosin = P[11] / 127.0
        scrap = P[12] / 127.0; snap = P[13] / 127.0; air = P[14] / 127.0; inst = P[15] / 127.0
        spread = P[16] / 127.0; voices = P[17] / 127.0; drift = P[18] / 127.0; vibr = P[19] / 127.0
        glissk = P[20] / 127.0; form = P[21] / 127.0; rough = P[22] / 127.0; morph = P[23] / 127.0
        mat = int(L4[0]); gest = int(L4[1]); mode = int(L4[2]); shape = int(L4[5]); qual = int(L4[7])
        distk = int(L4[3])
        ens = mode == 1 or mode == 2
        # COHE about 70 is a natural ensemble: below it the players come apart, above it they lock
        lock = (cohe - 0.55) / 0.45 if cohe > 0.55 else 0.0
        loose = (0.55 - cohe) / 0.55 if cohe < 0.55 else 0.0
        sadd = 0.0; entry = 1.0
        # ---- the gesture: bow speed (target), pressure push, impulses, damping ----
        tgt = 0.0; ppush = 0.0; imp = 0.0; damp_x = 1.0; noisy = 0.0; gn = 0.0
        atk = (0.004 + (1.0 - snap) ** 2 * 0.6) * (3.0 if shape == 0 else (0.3 if shape == 2 else 1.0))
        spd = (0.04 + speedk * 0.28) * (0.6 + 0.4 * vel)
        stlen = 0.03 + grain * 0.25                               # a stroke's length (STACC, SPICC)
        if gest == 0:                                             # BOW
            tgt = spd if gate or t_note < 0.05 else 0.0
        elif gest == 1:                                           # SCRAPE: heavy, uneven
            wander(wnd, 9.0, dt, st, 6)
            tgt = (spd * (0.7 + 0.6 * wnd[6])) if gate or t_note < 0.05 else 0.0
            ppush = 0.35 + 0.2 * wnd[6]
            noisy = 0.25
        elif gest == 2:                                           # STACC: contact, impact, damp, residual
            tgt = spd * 1.3 if t_note < stlen else 0.0
            ppush = 0.15
            if t_note >= stlen:
                damp_x = 1.0 + (1.0 - visc) * 0.0 + 6.0 * (1.0 - min(1.0, (t_note - stlen) / 0.08))
        elif gest == 3:                                           # TREMO: bow reversals
            rate = 6.0 + speedk * 14.0
            ph = (t_note * rate) % 1.0
            tgt = (spd if ph < 0.5 else -spd) if gate or t_note < 0.1 else 0.0
        elif gest == 4:                                           # SPICC: bouncing strokes
            k_b = 0
            tt = t_note
            per = 0.09 + (1.0 - speedk) * 0.12
            while tt > per and k_b < 12:
                tt -= per
                per *= 0.82
                k_b += 1
            amp_b = 0.85 ** k_b
            tgt = spd * 1.4 * amp_b if tt < stlen * 0.6 and k_b < 12 else 0.0
        elif gest == 5:                                           # LEGNO: the wood strikes
            imp = strike * (0.6 + 0.4 * vel)
        elif gest == 6:                                           # GLISS: GLISS is where to (centre: stay)
            tgt = spd if gate or t_note < 0.05 else 0.0
            gn = min(1.0, max(-1.0, (P[20] - 64.0) / 63.0))
            gl_amt = gn * 12.0 * crv(t_note / (0.4 + (1.0 - speedk) * 3.0), shape)
        elif gest == 8:                                           # SWELL: the excitation gathers
            ramp = crv(t_note / (0.3 + (1.0 - speedk) * 4.0), shape)
            tgt = spd * (0.15 + 0.85 * ramp) if gate or t_note < 0.05 else 0.0
            ppush = 0.3 * ramp
            sadd = 0.35 * ramp
            entry = ramp
        elif gest == 9:                                           # QUAKE: the instability grows
            ramp = crv(t_note / (0.5 + (1.0 - speedk) * 4.0), shape)
            qph = (qph + (3.0 + 17.0 * ramp) * dt) % 1.0
            wander(wnd, 6.0 + 20.0 * ramp, dt, st, 10)
            tgt = spd * (1.0 + 0.5 * ramp * np.sin(6.2831853 * qph)) if gate or t_note < 0.05 else 0.0
            ppush = 0.3 * ramp * (0.5 + 0.5 * wnd[10])
            sadd = 0.7 * ramp
        else:                                                     # FRACT: an impact breaking into smaller ones
            imp = strike
            if t_note < 0.05 + grain * 0.8 and bi(st) * 0.5 + 0.5 < (0.15 + dens * 0.8) * (1.0 - t_note):
                imp += 0.5 * (0.5 + 0.5 * bi(st)) * (1.0 - min(1.0, t_note * 1.5))
        imp_sub = imp - strike if gest == 7 else 0.0
        strike = 0.0
        if gest != 6 and abs(P[20] - 64.0) > 0.5:                 # GLISS elsewhere: the note scoops in from there
            gn = min(1.0, max(-1.0, (P[20] - 64.0) / 63.0))
            gl_amt = gn * 12.0 * (1.0 - crv(t_note / (0.03 + (1.0 - speedk) * 0.6), shape))
        if loose > 0.0 and tgt != 0.0:                            # COHE below 70: an unsteady bow arm
            wander(wnd, 2.5, dt, st2, 12)
            tgt *= 1.0 + loose * 0.45 * wnd[12]
        if shape == 2 and t_note < 0.15:                          # EXP: an accent, the push dies away
            ppush += 0.3 * np.exp(-t_note / 0.05)
        # STRESS: how near the material is to losing stable vibration
        stress = min(1.0, 0.45 * press * press + 0.25 * rosin * inst + 0.5 * inst * inst + 0.3 * rough + 0.25 * scrap + sadd)
        if stress > 0.6:                                          # the extremes stay musical: a soft ceiling
            stress = 0.6 + 0.25 * np.tanh((stress - 0.6) / 0.25)
        # MORPH on a struck material: the one hit splinters into particles
        if morph > 0.01 and gest in (2, 4, 5, 7) and tgt == 0.0 and t_note < 0.05 + 0.6 * morph and (bi(st2) * 0.5 + 0.5) < morph * (0.1 + dens * 0.6):
            imp += morph * 0.5 * (0.5 + 0.5 * bi(st2))
        if mat == 2 and P[6] > 32.0 and t_note < 0.05 + grain * 0.4 and (bi(st2) * 0.5 + 0.5) < (P[6] - 32.0) / 95.0 * 0.25:
            imp += 0.25 * (0.4 + 0.6 * (bi(st2) * 0.5 + 0.5))      # SKIN, DENS: the surface flutters, re-strikes
        # the strike pulse: its width by SNAP (hard and narrow .. soft and wide)
        if imp > 0.0:
            p_n = max(4, int((0.00015 + (1.0 - snap) ** 2 * 0.004) * FS))
            p_i = 0
            p_a = imp
        # SKIN's strokes snap as they start
        if mat == 2 and tgt != 0.0 and prev_tgt == 0.0 and gest in (2, 3, 4):
            p_n = max(4, int((0.0002 + (1.0 - snap) ** 2 * 0.003) * FS))
            p_i = 0
            p_a = 0.3 + 0.5 * snap
        prev_tgt = tgt
        if shape == 3:                                            # CHAOTIC: the stroke wavers
            wander(wnd, 5.0, dt, st, 8)
            tgt *= 1.0 + 0.5 * wnd[8]
        # MORPH: the continuous contact turns into particles (the same energy, intermittent)
        if morph > 0.01 and tgt != 0.0:
            part_t -= dt
            if part_t <= 0.0:
                part_t = (0.002 + (1.0 - dens) * 0.08) * (0.5 + (bi(st) * 0.5 + 0.5))
                burst = 1.0 if (bi(st) * 0.5 + 0.5) < (0.3 + 0.7 * cohe) else 0.3
                mo_c = morph * morph * 350.0 * bi(st2)          # each fragment at its own pitch
            tgt = tgt * (1.0 - morph) + tgt * morph * burst * (2.0 if part_t > (0.002 + (1.0 - dens) * 0.08) * 0.6 else 0.0)
            imp += morph * 0.25 * burst * (1.0 if part_t > 0.0 else 0.0) * 0.0
        # ---- pitch: vibrato (with an onset), drift, quiver, gliss ----
        vib_env = min(1.0, vib_env + dt / 0.6)
        vib_ph = (vib_ph + (4.5 + 2.0 * inst) * dt) % 1.0
        wander(wnd, 0.6, dt, st, 0)          # drift
        wander(wnd, 11.0, dt, st, 2)         # quiver
        wander(wnd, 7.0, dt, st, 4)          # jitter
        cents = vibr * 45.0 * vib_env * np.sin(6.2831853 * vib_ph) + drift * 25.0 * wnd[0] + stress * stress * 25.0 * wnd[2]
        glp = gl_amt * 100.0 if distk != 3 else 0.0
        cents += glp
        if morph > 0.01:
            cents += mo_c
        # elastic overshoot (SKIN, FIBER's strikes): the pitch stretches and settles with the energy
        alpha = (0.15 + 0.6 * press) * snap * (0.0 if mat == 2 else 0.25)
        tau = 0.01 + mass * 0.12
        cents += 1200.0 * np.log2(1.0 + alpha * np.exp(-t_note / tau))
        sq *= np.exp(-dt / 0.08)
        if mat == 0 and stress > 0.35 and tgt != 0.0 and (bi(st) * 0.5 + 0.5) < stress ** 3 * dt * 6.0:
            sq = 0.6 + 0.4 * stress
        f = f0 * 2.0 ** (cents / 1200.0)
        # ---- per-block coefficients ----
        per = FS / max(f, 25.0)
        lpc = (0.32 + 0.55 * (1.0 - visc * 0.8) * (0.55 + 0.45 * tens)) * (1.0 - 0.3 * mass)
        lpc = min(0.95, max(0.08, lpc / damp_x ** 0.5))
        lpd = (1.0 - lpc) / lpc
        tot = min(per - lpd, NBR - 4.0)
        beta = 0.04 + pos * 0.4
        db = min(max(tot * beta, 1.5), NBR - 4.0)
        dn = min(max(tot - db, 1.5), NBR - 4.0)
        half = min(max(db + per * 0.5, 2.0), NBR - 4.0)
        a_hp = 1.0 / (1.0 + 6.2831853 * 0.45 * f / FS)
        lossm = 0.995 - 0.4 * morph * morph if morph > 0.0 else 0.995    # MORPH: the string stops ringing through
        stiff = (P[0] - 42.0) / 85.0 if P[0] > 42.0 else 0.0
        fapc = -0.9 * stiff
        if stiff > 0.0:
            fad = (1.0 - fapc) / (1.0 + fapc)
            if fad > tot * 0.25:
                fad = tot * 0.25
                fapc = (1.0 - fad) / (1.0 + fad)
            db = min(max(db - fad, 1.5), NBR - 4.0)
        ghold = 1 + int(((P[5] - 55.0) / 72.0) ** 2 * 60.0) if P[5] > 55.0 else 1
        crk = (P[6] - 32.0) / 95.0 if P[6] > 32.0 else 0.0
        pr = min(1.0, press * 0.85 + ppush + 0.3 * stress * wnd[4])
        slope = 5.5 - pr * 4.2
        offset = 0.92 - rosin * 0.3
        breakup = (pr - 0.7) * 1.6 if pr > 0.7 else 0.0
        att = 1.0 - np.exp(-1.0 / (atk * FS))
        rel = 1.0 - np.exp(-1.0 / (0.03 * FS))
        scr = min(1.0, 0.5 * scrap + noisy + stress * 0.15)
        if scr > 0.3:
            scr = 0.3 + (scr - 0.3) * 0.5
        # the body: four modes, MASS scales them down (violin -> cello -> bass)
        fs_b = 2.0 ** (-mass * 1.9)
        bfr = (290.0 * fs_b, 470.0 * fs_b, 1150.0 * fs_b, 2600.0 * fs_b)
        bgn = (1.0, 0.7, 0.45, 0.25)
        bc = np.zeros(4); bs = np.zeros(4)
        rr = np.exp(-1.0 / ((0.02 + 0.03 * (1.0 - visc)) * FS))
        for k in range(4):
            bc[k] = rr * np.cos(6.2831853 * bfr[k] / FS)
            bs[k] = rr * np.sin(6.2831853 * bfr[k] / FS)
        # FORM: a band-pass that moves with the excitation
        fcen = 300.0 * 2.0 ** (form * 4.5 + env_e * 2.0 * form)
        g_f = np.tan(np.pi * min(fcen, 16000.0) / FS)
        kq = 1.0 / 3.0
        fa1 = 1.0 / (1.0 + g_f * (g_f + kq)); fa2 = g_f * fa1; fa3 = g_f * fa2
        # SKIN: the modes (TENS from membrane-like to harmonic), the tracking low-pass
        sk_r = np.zeros(6)
        mr = np.zeros(6); mc = np.zeros(6); ms = np.zeros(6)
        for k in range(6):
            mem = (1.0, 1.59, 2.14, 2.30, 2.65, 2.92)[k]
            har = float(k + 1)
            mr[k] = (mem + (har - mem) * tens) ** (1.0 + part)     # PART: the upper modes stretched apart
            fk = f * mr[k] * (1.0 + inst * 0.02 * env_e * (k + 1))
            if mat == 1 or mat == 3:
                fk *= 2.0 ** (soff[k] * spread * 3.0 / 1200.0)
            if fk > 20000.0:
                fk = 20000.0
            dec = (0.04 + (1.0 - visc) * 0.9) * (1.0 + mass) / (1.0 + 0.6 * k) / damp_x
            if mat == 1 or mat == 3:
                dec *= 1.0 - 0.85 * morph
            r = np.exp(-1.0 / (dec * FS))
            mc[k] = r * np.cos(6.2831853 * fk / FS)
            ms[k] = r * np.sin(6.2831853 * fk / FS)
        # SKIN: one elastic loop; its pitch and its cut-off follow its own energy
        el = 0.03 + (1.0 - tens) * 0.15 + press * 0.08
        sk_cut = min(16000.0, (f * (1.0 + 3.0 * tens + 30.0 * sk_E * (0.3 + press)) + 2500.0 * snap * sk_E) * (1.0 - 0.4 * visc))
        cut_l = min(18000.0, f * (3.0 + 25.0 * tens) * (1.0 + 0.5 * sk_E) * (1.0 - 0.5 * visc))
        a_lp = 1.0 - np.exp(-6.2831853 * cut_l / FS)
        fsk = f * (1.0 + el * 2.5 * max(0.0, sk_E - sk_Es))      # it stretches as the energy arrives, then settles
        # PART: three all-passes stretch the partials apart (rubber -> wood -> wire); at most a third of the loop
        dmax = (FS / fsk) / 16.0
        apc = -0.95 * part ** 0.7
        if (1.0 - apc) / (1.0 + apc) > dmax:
            apc = (1.0 - dmax) / (1.0 + dmax)
        Lsk = min(max(FS / fsk - (1.0 - a_lp) / a_lp - 4.0 * (1.0 - apc) / (1.0 + apc), 2.0), NBR - 4.0)
        dsk = (0.05 + (1.0 - visc) ** 1.5 * 2.5) * (0.5 + mass) / damp_x * (1.0 - 0.8 * morph)
        gsk = 10.0 ** (-3.0 / (dsk * fsk))
        nlk = 1.0 + 2.0 * inst + 1.5 * stress
        g2 = np.tan(np.pi * min(sk_cut, 18000.0) / FS)
        k2 = 1.0 / (0.6 + inst * 2.5)
        b1 = 1.0 / (1.0 + g2 * (g2 + k2)); b2 = g2 * b1; b3 = g2 * b2
        # FLUID: it melts over the note (VISC: water .. honey); the pitch slumps, the partials warp and soften
        melt = crv(t_note / ((0.4 + visc * 4.0) * (0.5 + (1.0 - speedk))), shape)
        wander(wnd, 0.8 + 3.0 * (1.0 - visc), dt, st2, 14)
        fl_f = f * 2.0 ** (-(1.0 - tens) * 160.0 * melt / 1200.0)
        fl_cut = min(16000.0, fl_f * (2.0 + 22.0 * tens * (1.0 - 0.7 * melt)) * (1.0 - 0.5 * visc))
        fl_a = 1.0 - np.exp(-6.2831853 * fl_cut / FS)
        fl_apc = -0.5 * part - 0.3 * melt * (0.5 + 0.5 * wnd[14])
        dmx = (FS / fl_f) / 16.0
        if (1.0 - fl_apc) / (1.0 + fl_apc) > dmx:
            fl_apc = (1.0 - dmx) / (1.0 + dmx)
        fl_L = min(max(FS / fl_f - (1.0 - fl_a) / fl_a - 4.0 * (1.0 - fl_apc) / (1.0 + fl_apc), 2.0), NBR - 4.0)
        dfl = (0.3 + 2.0 * (1.0 - visc)) * (0.5 + mass) * (1.0 - 0.5 * melt) / damp_x * (1.0 - 0.8 * morph)
        gfl = 10.0 ** (-3.0 / (dfl * fl_f))
        drate = (0.5 + dens * dens * 30.0) * (0.3 + 0.7 * melt) * (1.0 + 2.0 * stress)
        drp_dec = np.exp(-1.0 / ((0.01 + 0.05 * (1.0 - visc) + 0.03 * grain) * FS))
        pw0 = max(4, int((0.00015 + (1.0 - snap) ** 2 * 0.004) * FS))
        av_dec = np.exp(-1.0 / ((0.01 + grain * 0.08) * FS))
        wpos = np.zeros(6)
        for k in range(6):
            wpos[k] = 0.25 + 0.75 * abs(np.sin(np.pi * (k + 1) * (0.03 + 0.47 * pos)))   # POS: edge .. middle
        nm = 2 + int(4.0 * voices + 0.5)                          # SILT, FLUID: VOICES = how many resonances
        skd = max(1, int(Lsk * (0.03 + 0.47 * pos)))
        # secondary filaments (MASS): how many (QUAL, VOICES), their drift, vibrato, glide
        nsec = 0
        if mode >= 1:
            nsec = (2, 4, 8)[qual]
            nsec = max(1, int(round(nsec * (0.25 + 0.75 * voices) * (0.4 + 0.6 * vel))))
        elif voices > 0.01 and (mat == 0 or mat == 2):           # SOLO: sympathetic strands
            nsec = max(1, int(round((1, 2, 4)[qual] * voices)))
        sper = np.zeros(NSEC)
        for k in range(nsec):
            wander(sdrift, 0.3 + 0.8 * drift, dt, st, 2 * k)
            svph[k] = (svph[k] + (4.0 + 0.37 * k + 2.0 * inst) * dt) % 1.0
            if lock > 0.0:                                        # COHE: the vibratos fall into step
                dphi = vib_ph - svph[k]
                dphi -= np.floor(dphi + 0.5)
                svph[k] += dphi * lock * 0.2
            # GLISS's coordination by DIST: together, in parallel, shearing, opening / closing
            uk = (k / max(1, nsec - 1) - 0.5) * 2.0
            sc = 1.0
            gk = 0.0
            if gest == 6:
                gp = t_note / (0.4 + (1.0 - speedk) * 3.0)
                if distk == 0:
                    gk = gl_amt * 100.0
                elif distk == 1:
                    gk = gn * 1200.0 * crv(gp / (1.0 + 0.35 * uk), shape) * (1.0 + 0.15 * uk)
                elif distk == 2:
                    gk = gl_amt * 100.0 * (1.0 if k % 2 == 0 else -1.0) * (1.0 + 0.75 * uk)
                else:
                    pp = crv(gp, shape)
                    sc = 1.0 + gn * pp * 3.0 if gn > 0.0 else 1.0 + gn * pp
            dr = sdrift[2 * k] * (1.0 - lock) + wnd[0] * lock
            c = soff[k] * sc + drift * 60.0 * dr * (1.0 + loose) + vibr * 40.0 * vib_env * np.sin(6.2831853 * svph[k]) \
                + gk + stress * 30.0 * wnd[2] * (1.0 if k % 2 else -1.0)
            fk = f0 * 2.0 ** ((c + (cents - glp - 1200.0 * np.log2(1.0 + alpha * np.exp(-t_note / tau)))) / 1200.0)
            sper[k] = min(FS / max(fk, 25.0), NSL - 4.0)
        # particles / droplets (SILT, FLUID, SWARM): their rate this block
        prate = (5.0 + dens * dens * 2500.0)
        sgn = 1.0 / np.sqrt(1.0 + (prate * (abs(bow) * 6.0 + imp * 40.0) + aval * 30.0 * (dens + 0.2) * prate) / 400.0)
        # ---- samples ----
        for i in range(SUB):
            nz = bi(st)
            y = 0.0
            pv = 0.0
            if p_i < p_n:
                pv = p_a * (8.0 / p_n) ** 0.5 * np.sin(np.pi * (p_i + 0.5) / p_n)
                if p_i < 24:
                    pv += nz * snap * 0.4 * p_a
                p_i += 1
            ex = 0.0                                  # the excitation the secondaries and particles share
            if mat == 0 or (mat != 0 and False):
                # FIBER: RESIN's bowed string (two segments meet at the bow)
                a0 = rd(br, NBR, wb, db)
                a1 = rd(nk, NBR, wk, dn)
                lp += (a0 - lp) * lpc
                if stiff > 0.0:
                    fy = fapc * lp + f_ax - fapc * f_ay
                    f_ax = lp
                    f_ay = fy
                    brr = -fy * lossm
                else:
                    brr = -lp * lossm
                nr = -a1
                sv = brr + nr
                bow += (tgt - bow) * (att if tgt != 0.0 else rel)
                contact = 1.0 if (tgt != 0.0 or gest in (0, 1, 6, 8, 9)) else min(1.0, abs(bow) * 60.0)
                dv = bow - sv
                bt = abs(dv * slope) + offset
                bt = 1.0 / (bt * bt * bt * bt)
                if bt > 1.0:
                    bt = 1.0
                if breakup > 0.0:
                    bt *= 1.0 + breakup * 0.6 * nz
                slip = 1.0 - bt
                gz = nz
                if ghold > 1:
                    g_cnt -= 1
                    if g_cnt <= 0:
                        g_hold = nz
                        g_cnt = ghold
                    gz = g_hold * 1.4
                nv = (dv * bt + gz * scr * slip * 0.06 * (0.4 + pr)) * contact
                if crk > 0.0 and bow != 0.0 and (bi(st2) * 0.5 + 0.5) < crk * crk * 0.004:
                    nv += bi(st2) * 0.35 * crk          # rosin dust: the bow crackles
                nv += pv * 0.9                        # a strike (LEGNO, FRACT): the wood hits the string
                nk[wk] = max(-2.0, min(2.0, brr + nv))
                br[wb] = max(-2.0, min(2.0, nr + nv))
                wb = wb + 1 if wb + 1 < NBR else 0
                wk = wk + 1 if wk + 1 < NBR else 0
                y = a0
                if sq > 0.01:                         # squeals: the string jumps to its octave's flageolet
                    y = a0 * (1.0 - sq) + sq * 0.5 * (a0 + rd(br, NBR, wb, half)) * 1.6
                # the bridge passes the string, not the bow's own motion: a high-pass under the note
                if gest != 0 and gest != 6 and gest != 8:   # only where the bow turns back and forth
                    h1 = a_hp * (h1 + y - hx1)
                    hx1 = y
                    h2 = a_hp * (h2 + h1 - hx2)
                    hx2 = h1
                    h3 = a_hp * (h3 + h2 - hx3)
                    hx3 = h2
                    h4 = a_hp * (h4 + h3 - hx4)
                    hx4 = h3
                    y = h4
                ex = nv
                hn = nz - hp
                hp += (nz - hp) * 0.25
                y += hn * air * abs(bow) * 0.3
            elif mat == 2:
                # SKIN: an elastic loop, struck or rubbed; it stiffens and brightens with its energy
                bow += (tgt - bow) * (att if tgt != 0.0 else rel)
                a = rd(br, NBR, wb, Lsk)
                sk_lp += (a - sk_lp) * a_lp
                xa = sk_lp
                for q in range(4):
                    apy = apc * xa + sk_ap[2 * q] - apc * sk_ap[2 * q + 1]
                    sk_ap[2 * q] = xa
                    sk_ap[2 * q + 1] = apy
                    xa = apy
                v = np.tanh(apy * gsk * nlk) / nlk
                dcy = v - sk_dx + 0.995 * sk_dy        # the loop holds no DC
                sk_dx = v
                sk_dy = dcy
                v = dcy
                drive = pv * 0.8
                if bow != 0.0:
                    dv = bow - v * 0.5
                    bt = abs(dv * slope) + offset
                    bt = 1.0 / (bt * bt * bt * bt)
                    if bt > 1.0:
                        bt = 1.0
                    reg = 1.0 / (1.0 + 6.0 * max(0.0, sk_E - (0.2 + 0.5 * press)))   # PRESS sets where it settles
                    drive += (dv * bt * 1.6 + nz * scr * (1.0 - bt) * 0.03) * reg
                if stress > 0.3 and (bi(st2) * 0.5 + 0.5) < stress ** 3 * 0.002:
                    drive += nz * 0.2 * stress        # stressed rubber: it catches and jumps
                ex = drive
                if pv != 0.0:                         # POS: where the strike lands (the reflection, inverted)
                    jx = wb - skd
                    if jx < 0:
                        jx += NBR
                    br[jx] -= pv * 0.8
                br[wb] = max(-2.0, min(2.0, v + drive))
                wb = wb + 1 if wb + 1 < NBR else 0
                v3 = a - sk_s2
                v1 = b1 * sk_s1 + b2 * v3
                v2 = sk_s2 + b2 * sk_s1 + b3 * v3
                sk_s1 = 2.0 * v1 - sk_s1
                sk_s2 = 2.0 * v2 - sk_s2
                y = v2 * 2.2 + nz * air * 0.02 * (abs(bow) + abs(pv))
                e = abs(y) * 2.5
                sk_E += (e - sk_E) * (0.01 if e > sk_E else 0.0006)
                if sk_E > 1.0:
                    sk_E = 1.0
                sk_Es += (sk_E - sk_Es) * (0.00015 + 0.0006 * (1.0 - mass))
            elif mat == 1:
                # SILT: particles, single impacts to dense rubbing; cohesion makes bursts
                # COHE: one particle sets off others (an avalanche), more so under STRESS and ROSIN
                p_on = (bi(st) * 0.5 + 0.5) < prate * (1.0 / FS) * (abs(bow) * 6.0 + imp * 40.0 + aval * 30.0 * (dens + 0.2))
                d = 0.0
                if p_on:
                    d = (0.3 + 0.7 * (bi(st) * 0.5 + 0.5)) * (1.0 + cohe * 2.0 * burst) * 0.012 * (0.4 + press) * sgn
                    aval = min(1.5, aval + cohe * (0.25 + 0.5 * stress) * (0.5 + 0.5 * rosin))
                aval *= av_dec
                d += pv * 0.08
                ex = d
                acc = 0.0
                for k in range(6):
                    re = mc[k] * md[k, 0] - ms[k] * md[k, 1] + (d * (0.4 + 0.6 * (bi(st) * 0.5 + 0.5)) * (1.0 - part * 0.5) ** k * wpos[k] if k < nm else 0.0)
                    im = ms[k] * md[k, 0] + mc[k] * md[k, 1]
                    md[k, 0] = re
                    md[k, 1] = im
                    acc += im
                y = acc * 0.5 * (1.0 - 0.5 * morph) + nz * d * (grain * 2.0 + morph * 3.0)
                hp += (nz - hp) * 0.3
                y += hp * abs(bow) * (scrap * 0.12 + air * 0.06) + nz * aval * air * 0.01   # rubbing grit, the dust's air
                bow += (tgt - bow) * (att if tgt != 0.0 else rel)
            else:
                # FLUID: a molten body (SKIN's loop, softening and sagging as it melts), drips falling from it
                bow += (tgt - bow) * (att if tgt != 0.0 else rel)
                a = rd(br, NBR, wb, fl_L)
                sk_lp += (a - sk_lp) * fl_a
                xa = sk_lp
                for q in range(4):
                    apy = fl_apc * xa + sk_ap[2 * q] - fl_apc * sk_ap[2 * q + 1]
                    sk_ap[2 * q] = xa
                    sk_ap[2 * q + 1] = apy
                    xa = apy
                v = xa * gfl
                dcy = v - sk_dx + 0.995 * sk_dy
                sk_dx = v
                sk_dy = dcy
                v = dcy
                drive = pv * 0.6
                if bow != 0.0:
                    dv = bow - v * 0.5
                    bt = abs(dv * slope) + offset
                    bt = 1.0 / (bt * bt * bt * bt)
                    if bt > 1.0:
                        bt = 1.0
                    reg = 1.0 / (1.0 + 6.0 * max(0.0, sk_E - (0.15 + 0.4 * press)))
                    drive += dv * bt * 1.2 * reg
                # drips: tuned plinks (a bubble's rising chirp) at the body's harmonics; each one strikes the body
                if (gate or t_note < 2.0) and (bi(st2) * 0.5 + 0.5) < drate * (1.0 + aval * 4.0) / FS:
                    j = int((bi(st2) * 0.5 + 0.5) * 3.999)
                    u = bi(st2) * 0.5 + 0.5
                    kh = 1 + int((u ** (0.5 + pos * 1.5)) * (1.0 + part * 6.0))
                    bub_f[j] = fl_f * kh * (1.0 + 0.004 * bi(st2))
                    bub_a[j] = (0.3 + 0.7 * (bi(st2) * 0.5 + 0.5)) * (0.3 + press) * 0.5
                    bub_r[j] = 0.0
                    drive += bub_a[j] * 0.15
                    aval = min(1.5, aval + cohe * 0.5)
                aval *= av_dec
                dr = 0.0
                for j in range(4):
                    if bub_a[j] > 1e-4:
                        bub_r[j] += 1.0 / FS
                        fj = bub_f[j] * (1.0 + (1.0 - visc) * 3.0 * min(bub_r[j], 0.03))
                        bub_p[j] = (bub_p[j] + fj / FS) % 1.0
                        dr += bub_a[j] * np.sin(6.2831853 * bub_p[j])
                        bub_a[j] *= drp_dec
                ex = drive + dr * 0.1
                br[wb] = max(-2.0, min(2.0, v + drive))
                wb = wb + 1 if wb + 1 < NBR else 0
                y = a * 1.6 + dr * 0.35
                hp += (nz - hp) * 0.08
                y += hp * (abs(bow) + dr) * air * 0.1
                e = abs(a) * 2.5
                sk_E += (e - sk_E) * (0.01 if e > sk_E else 0.0006)
                if sk_E > 1.0:
                    sk_E = 1.0
            # secondaries (MASS): cheap bowed filaments, each its own bow table, the cluster's pitches
            yprev = y
            if nsec > 0:
                sacc = 0.0
                for k in range(nsec):
                    a = rd(sb[k], NSL, sw[k], sper[k])
                    slp[k] += (a - slp[k]) * lpc
                    if mode == 2:
                        v_s = -slp[k] * 0.996                 # MASS-8: the inverted filament, an octave below
                    else:                                     # in pitch: upright, its DC drained
                        v_s = slp[k] * 0.996 - sdx[k] + 0.995 * sdy[k]
                        sdx[k] = slp[k] * 0.996
                        sdy[k] = v_s
                    if mode == 0:                         # a sympathetic strand: the primary rings it
                        nvk = yprev * 0.03 * (0.4 + 1.2 * cohe)
                    elif mat == 0 or mat == 1:
                        fac = 1.0 + (0.85 + 0.3 * ((k * 7) % 5) / 4.0 - 1.0) * (1.0 - lock) * (1.0 + 2.0 * loose)
                        ent = min(1.0, max(0.0, entry * nsec - k)) if gest == 8 else 1.0
                        sbow[k] += (tgt * fac * ent - sbow[k]) * (att if tgt != 0.0 else rel)
                        dvk = sbow[k] - v_s
                        btk = abs(dvk * slope * 1.1) + offset
                        btk = 1.0 / (btk * btk * btk * btk)
                        if btk > 1.0:
                            btk = 1.0
                        ck = 1.0 if (tgt != 0.0 or gest in (0, 1, 6, 8, 9)) else min(1.0, abs(sbow[k]) * 60.0)
                        nvk = (dvk * btk + nz * scr * (1.0 - btk) * 0.05) * ck
                        if imp_sub > 0.0 and i < 6:
                            nvk += imp_sub * 0.25 * (0.6 + 0.4 * ((k * 3) % 4) / 3.0) * (1.0 - i / 6.0) if i < 6 else 0.0
                    else:
                        nvk = ex * 0.3
                    if simp > 0.0 and mode >= 1 and scnt[k] < pw0:   # the ensemble's own, uneven strikes
                        scnt[k] += 1
                        if scnt[k] > 0:
                            nvk += simp * 0.5 * (8.0 / pw0) ** 0.5 * np.sin(np.pi * scnt[k] / pw0)
                    sb[k, sw[k]] = max(-2.0, min(2.0, v_s + nvk))
                    sw[k] = sw[k] + 1 if sw[k] + 1 < NSL else 0
                    sacc += a
                if mode == 0:
                    y = y + sacc * 0.6 * voices
                else:
                    y = y * (0.55 if ens else 0.8) + sacc * (1.6 / (nsec ** 0.5 + 1.0))
            # SWARM: a particle cloud over the material, its rate by DENS, gathered by COHE
            if mode == 3:
                if (bi(st) * 0.5 + 0.5) < prate * (1.0 / FS) * (abs(bow) * 8.0 + 0.2):
                    burst = min(1.5, burst + 0.5 * (0.3 + cohe))
                burst *= 0.9995 - (1.0 - cohe) * 0.002
                hp += (nz - hp) * (0.05 + 0.4 * part)
                y += hp * burst * 0.12 * (0.3 + grain)
            # MASS: DENS above about 30 adds the statistical players, a particle cloud
            if ens and dens > 0.25:
                if (bi(st2) * 0.5 + 0.5) < prate * (1.0 / FS) * (abs(bow) * 8.0 + 0.1):
                    cl_b = min(1.5, cl_b + 0.5 * (0.3 + cohe))
                cl_b *= 0.9995 - (1.0 - cohe) * 0.002
                cl_hp += (nz - cl_hp) * (0.05 + 0.4 * part)
                y += cl_hp * cl_b * 0.12 * (0.3 + grain) * (dens - 0.25) / 0.75
            # body, FORM, the energy follower, the AMP
            bo = 0.0
            for k in range(4):
                re = bc[k] * body[k, 0] - bs[k] * body[k, 1] + y * bgn[k] * 0.012
                im = bs[k] * body[k, 0] + bc[k] * body[k, 1]
                body[k, 0] = re
                body[k, 1] = im
                bo += im
            y = y + bodyk * bo * 1.5
            v3 = y - fm2
            v1 = fa1 * fm1 + fa2 * v3
            v2 = fm2 + fa2 * fm1 + fa3 * v3
            fm1 = 2.0 * v1 - fm1
            fm2 = 2.0 * v2 - fm2
            y = y * (1.0 - form * 0.6) + v1 * form * 1.8
            env_e += (min(1.0, abs(ex) * 4.0) - env_e) * (0.02 if abs(ex) * 4.0 > env_e else 0.0015)
            amp += ((1.0 if gate else 0.0) - amp) * (0.01 if gate else 0.0004)
            out[n0 + i] = np.float32(np.tanh(y * 0.6) * amp)
    return out


def panel(**kw):
    p = dict(DEFAULTS)
    for k, v in kw.items():
        if k in ("MAT", "GEST", "MODE", "DIST", "LOOP", "SHAPE", "TUNE", "QUAL") and isinstance(v, str):
            v = {"MAT": MATS, "GEST": GESTS, "MODE": MODES, "DIST": DISTS, "LOOP": LOOPS,
                 "SHAPE": SHAPES, "TUNE": TUNES, "QUAL": QUALS}[k].index(v)
        p[k] = v
    return np.array([float(p[c]) for c in CONTROLS])


def play(P, notes, secs, seed=0x2545F491, bpm=120.0):
    """P: one panel or a list of panels (keyframes over the render); notes: (time s, midi note, velocity 0..1, gate s)"""
    PK = np.atleast_2d(np.array(P, dtype=np.float64))
    ev = np.array([[int(t * FS), n, v, int(g * FS)] for t, n, v, g in notes], dtype=np.float64).reshape(-1, 4)
    return render(PK, ev, int(secs * FS) // SUB * SUB, seed, bpm)
