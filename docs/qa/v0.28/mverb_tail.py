"""The release review of v0.28: the master reverb's tail with v0.27's decay constants (0.88, 0.98) and v0.28's
(0.87, 0.97), from the model (dnfw.mverb.live) alone: a 50 ms noise burst, PRE 0, FREQ 64, GAIN 64.

    PYTHONPATH=src python3 docs/qa/v0.28/mverb_tail.py OUTDIR SECONDS DEC [DEC...]

Writes OUTDIR/mverb_DEC<n>_v027.wav and _v028.wav and prints each tail's length: the slope of the level in
100 ms windows from 0.5 s to the render's end (above -75 dB), as seconds to fall 60 dB. (The first figure
printed, from the integrated energy, reads short when the render is shorter than the tail.)"""
import sys, time, wave, numpy as np
from dnfw.mverb import live as L
F = L.F
out = sys.argv[1]; secs = float(sys.argv[2])
print("FS", L.FS, "SUB", L.SUB, "TOTAL", L.TOTAL, "CHUNK", L.CHUNK, flush=True)
fs = float(L.FS)
def render(span, mx, dec, secs):
    L.GDEC_SPAN, L.GDEC_MAX = F(span), F(mx)
    v = L.Verb()
    while v.clr < L.TOTAL:
        v.block((0, dec << 8, 0x4000, 0x4000), np.zeros(L.SUB, np.float32))
    rng = np.random.default_rng(1)
    n = int(secs * fs) // L.SUB
    burst = int(0.05 * fs)
    ls = []; rs = []
    for b in range(n):
        i0 = b * L.SUB
        x = np.zeros(L.SUB, np.float32)
        if i0 < burst:
            x[:] = (rng.standard_normal(L.SUB) * 0.25).astype(np.float32)
        l, r = v.block((0, dec << 8, 0x4000, 0x4000), x)
        ls.append(l.copy()); rs.append(r.copy())
    return np.concatenate(ls), np.concatenate(rs)
def rt(l, r):
    e = (l.astype(np.float64) ** 2 + r.astype(np.float64) ** 2)
    sch = np.cumsum(e[::-1])[::-1]
    db = 10 * np.log10(sch / sch[0] + 1e-30)
    def t(a):
        i = np.argmax(db <= a); return i / fs if db[i] <= a else float("nan")
    t5, t35 = t(-5), t(-35)
    return 2.0 * (t35 - t5), 20 * np.log10(np.sqrt(e.mean() / 2) + 1e-30)
for dec in (int(a) for a in sys.argv[3:]):
    res = {}
    for name, (sp, mx) in (("v027", (0.88, 0.98)), ("v028", (0.87, 0.97))):
        t0 = time.time()
        l, r = render(sp, mx, dec, secs)
        res[name] = rt(l, r)
        pk = max(np.abs(l).max(), np.abs(r).max())
        w = wave.open(f"{out}/mverb_DEC{dec}_{name}.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(int(fs))
        st = np.stack([l, r], 1); w.writeframes((np.clip(st / 1.0, -1, 1) * 32767).astype("<i2").tobytes()); w.close()
        print(f"DEC {dec} {name}: RT60 (T30, -5..-35 dB) {res[name][0]:.2f} s, rms {res[name][1]:.1f} dBFS, peak {pk:.3f}, {time.time()-t0:.0f}s", flush=True)
    print(f"DEC {dec}: ratio new/old {res['v028'][0] / res['v027'][0]:.3f}", flush=True)


def slope(path, t1):
    w = wave.open(path)
    x = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32767
    n = 4800
    e = (x ** 2).sum(1)
    m = len(e) // n
    db = 10 * np.log10(e[:m * n].reshape(m, n).mean(1) + 1e-20)
    t = (np.arange(m) + .5) * n / 48000
    sel = (t > 0.5) & (t < t1) & (db > -75)
    return -60 / np.polyfit(t[sel], db[sel], 1)[0]


for dec in (int(a) for a in sys.argv[3:]):
    a, b = (slope(f"{out}/mverb_DEC{dec}_{v}.wav", secs - 0.5) for v in ("v027", "v028"))
    print(f"DEC {dec}: by slope, v0.27 {a:.2f} s, v0.28 {b:.2f} s, new/old {b / a:.3f}")
