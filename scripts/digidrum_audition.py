"""DIGIDRUM auditions: each type alone, its controls swept, and a groove that p-locks TYPE."""
import pathlib, sys, wave
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from dnfw.digidrum import model as M
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out/digidrum")
OUT.mkdir(parents=True, exist_ok=True)
def save(name, y):
    y = np.clip(y, -1, 1)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(M.FS)
        w.writeframes((y * 32767).astype("<i2").tobytes())
def seq(hits, secs):
    out = np.zeros(int(secs * M.FS))
    for at, ty, kn in hits:
        y = M.render(ty, secs=1.0, **kn)
        i = int(at * M.FS); out[i:i + len(y)] += y[:len(out) - i] * 0.6
    return out
step = 60 / 120 / 4
for k, ty in enumerate(M.TYPES):
    own = M.OWN[ty]
    hits = [(j * 0.5, ty, {own[0]: 10 + 25 * j, "DEC": 50}) for j in range(4)]
    hits += [(2 + j * 0.5, ty, {own[1]: 10 + 25 * j, own[2]: 10 + 25 * j, "DEC": 50}) for j in range(4)]
    save(f"{k + 1:02d}_{ty.replace(' ', '_').lower()}", seq(hits, 4.5))
groove = []
pat = ["BD MODERN", None, "CY ALLOY", None, "SD BASIC", None, "CY ALLOY", "PC CARBON",
       "BD MODERN", "BD MODERN", "CY ALLOY", None, "CP VINTAGE", None, "SD VINTAGE", "CY ALLOY"]
for bar in range(4):
    for s, ty in enumerate(pat):
        if ty:
            groove.append((bar * 16 * step + s * step, ty, {"DEC": 40 if ty != "CY ALLOY" else 25, "PNCH": 50}))
save("07_one_track_type_locked_groove", seq(groove, 4 * 16 * step + 1))
print("wrote", OUT)
