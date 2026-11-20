"""THOLET's design model (src/dnfw/tholet/model.py) played, for the owner's ear.
    python3 scripts/tholet_audition.py OUTDIR
Needs VCSL's Kawai grand (CC0) at model.VCSL for the strikes."""
import pathlib
import sys
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from dnfw.tholet import model as M  # noqa: E402

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)


def save(name, y):
    y = y / (np.abs(y).max() + 1e-9) * 0.89
    with wave.open(str(out / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes((y * 32767).astype("<i2").tobytes())


def seq(notes, secs, **kn):
    o = np.zeros(int(secs * 48000))
    for at, nt, vel, dur, extra in notes:
        kk = dict(kn)
        kk.update(extra)
        y = M.render(nt, secs=min(secs - at, 4.5), vel=vel, gate=dur, **kk)
        i = int(at * 48000)
        o[i:i + len(y)] += y[:len(o) - i]
    return o


phrase = [(0, 48, 0.8, 1.6, {}), (0, 55, 0.7, 1.6, {}), (0, 64, 0.75, 1.6, {}), (1.0, 67, 0.6, 0.8, {}),
          (1.5, 72, 0.7, 1.5, {}), (2.2, 62, 0.5, 1.2, {}), (3.0, 60, 0.9, 2.5, {})]
save("01_grand_default_phrase", seq(phrase, 6))
save("02_felt_frahm", seq(phrase, 6, FELT=110, TONE=30, DEC=95))
save("03_ep_rhodes", seq(phrase, 6, EP=127, DEC=90))
save("04_halfway_piano_ep", seq(phrase, 6, EP=64))
save("05_hammers_each", seq([(j * 0.8, 60, 0.85, 0.7, {"HAMR": int(j * 128 / 6) + 5}) for j in range(6)], 5.5))
save("06_grain_cloud_billow", seq([(0, 48, 0.8, 4, {}), (0, 60, 0.8, 4, {}), (0, 67, 0.7, 4, {})], 6,
                                  GRAN=110, GDEN=80, GSIZ=40, GFM=25, GSPR=70, DEC=100))
save("07_grain_fm_shards", seq([(0, 57, 0.9, 3, {}), (1.8, 64, 0.8, 3, {})], 5.5,
                               GRAN=127, GDEN=100, GSIZ=20, GFM=110, GSPR=40))
save("08_felt_plus_cloud", seq(phrase, 6.5, FELT=100, GRAN=90, GDEN=50, GSIZ=60, GFM=15, GSPR=90, DEC=100))
