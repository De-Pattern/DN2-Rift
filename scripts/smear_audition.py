"""Audition WAVs for SMEAR's reference model (src/dnfw/smear/model.py), for the owner's ear.

    python3 scripts/smear_audition.py OUTDIR [SOURCE.wav]

Without a source, a 4-second phrase is synthesized (arpeggiated saw chords, a kick, hats),
so nothing copyrighted is used. Each file is normalised to -1 dBFS peak and is stereo-
duplicated mono, 48 kHz, 16-bit."""

from __future__ import annotations

import math
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dnfw.smear import model as M  # noqa: E402

SR = M.SR


def synth_phrase(sec=4.0) -> np.ndarray:
    n = int(sec * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    rng = np.random.default_rng(7)
    chords = [(57, 60, 64, 67), (53, 57, 60, 64), (55, 59, 62, 67), (52, 55, 59, 64)]
    step = 0.125
    for k in range(int(sec / step)):
        ch = chords[(k // 8) % 4]
        note = ch[k % 4] + (12 if (k // 4) % 2 else 0)
        f = 440 * 2 ** ((note - 69) / 12)
        s0 = int(k * step * SR)
        m = int(0.4 * SR)
        tt = np.arange(m) / SR
        ph = (f * tt) % 1.0
        saw = 2 * ph - 1 + 0.5 * (2 * ((f * 1.004 * tt) % 1.0) - 1)
        env = np.exp(-tt * 9)
        seg = saw * env * 0.25
        # a one-pole low-pass that closes with the envelope
        a = 0.08 + 0.5 * env
        lp = np.empty(m)
        z = 0.0
        for i in range(m):
            z += a[i] * (seg[i] - z)
            lp[i] = z
        e = min(n, s0 + m)
        y[s0:e] += lp[:e - s0]
    for k in range(int(sec / 0.5)):
        s0 = int(k * 0.5 * SR)
        m = int(0.35 * SR)
        tt = np.arange(m) / SR
        f = 45 + 110 * np.exp(-tt * 30)
        kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) * 0.8
        e = min(n, s0 + m)
        y[s0:e] += kick[:e - s0]
    for k in range(int(sec / 0.125)):
        if k % 2 == 0:
            continue
        s0 = int(k * 0.125 * SR)
        m = int(0.05 * SR)
        h = rng.standard_normal(m)
        h = np.diff(np.concatenate([[0], h])) * np.exp(-np.arange(m) / SR * 80) * 0.15
        e = min(n, s0 + m)
        y[s0:e] += h[:e - s0]
    return y / np.max(np.abs(y)) * 0.8


def load(path: str) -> np.ndarray:
    with wave.open(path) as w:
        ch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    a = np.frombuffer(raw, {2: np.int16, 4: np.int32}[sw]).astype(float)
    a = a.reshape(-1, ch).mean(axis=1) / (2 ** (8 * sw - 1))
    if sr != SR:
        x = np.arange(0, len(a) - 1, sr / SR)
        a = np.interp(x, np.arange(len(a)), a)
    return a


def save(path: Path, y: np.ndarray):
    y = y / (np.max(np.abs(y)) + 1e-12) * 10 ** (-1 / 20)
    s = (np.clip(y, -1, 1) * 32767).astype(np.int16)
    st = np.repeat(s[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


def semis(x):
    return 2 ** (x / 12)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    src = load(sys.argv[2]) if len(sys.argv) > 2 else synth_phrase()
    save(out / "00_source.wav", src)
    sk = M.speed_knob
    jobs = [
        ("01_voc_stretch_quarter", 12, dict(speed=sk(0.25), blend=0.0)),
        ("02_voc_crawl_freeze", 12, dict(speed=sk(0.03), blend=0.0, start=0.25, size=0.5)),
        ("03_voc_pitch_up5_same_speed", 8, dict(speed=sk(1), pitch=semis(5), blend=0.0)),
        ("04_voc_octave_down_half_speed", 12, dict(speed=sk(0.5), pitch=semis(-12), blend=0.0)),
        ("05_voc_reverse_half", 12, dict(speed=sk(-0.5), blend=0.0)),
        ("06_grn_cloud", 12, dict(speed=sk(0.25), blend=1.0, density=0.62, overlap=0.85,
                                  spray=0.35, window="GAUS")),
        ("07_grn_sparse_expodec", 12, dict(speed=sk(0.5), blend=1.0, density=0.35,
                                           overlap=0.35, spray=0.6, prand=0.5, window="EXPO")),
        ("08_grn_shimmer_octave", 12, dict(speed=sk(0.15), pitch=2.0, blend=1.0, density=0.7,
                                           overlap=0.9, spray=0.2, prand=0.3, window="BHAR")),
        ("09_play_tape_half", 8, dict(speed=sk(0.5), blend=0.5)),
    ]
    for name, sec, kw in jobs:
        v = M.Voice(src)
        save(out / f"{name}.wav", v.render(sec, **kw))
        print(name)
    # 10: BLEND swept VOC -> PLAY -> GRN over 16 s at a quarter speed
    v = M.Voice(src)
    save(out / "10_blend_sweep_voc_play_grn.wav",
         v.render(16, speed=sk(0.25), density=0.6, overlap=0.8, spray=0.25,
                  ctl=lambda t: dict(blend=min(t / 16, 1.0))))
    print("10")
    # 11: played chromatically: a frozen spot, a trig each half second, notes of a chord
    notes = [0, 3, 7, 10, 12, 7, 3, -5]
    seq = []
    for k, nt in enumerate(notes * 2):
        v = M.Voice(src)
        seq.append(v.render(0.5, speed=sk(0.04), start=0.3, size=0.3, pitch=semis(nt),
                            blend=0.0) * np.minimum(1, np.arange(int(0.5 * SR))[::-1] / 480))
    save(out / "11_voc_played_chromatic.wav", np.concatenate(seq))
    print("11")
    # 12: speed swept -1 .. +1 through freeze (a scrub) with the grains
    v = M.Voice(src)
    save(out / "12_grn_scrub.wav",
         v.render(12, blend=0.8, density=0.55, overlap=0.7, spray=0.1,
                  ctl=lambda t: dict(speed=sk(math.sin(2 * math.pi * t / 12) * 1.0))))
    print("12")


if __name__ == "__main__":
    main()
