"""MACHINE SEL's logos (RIFT v0.16): csrc/waverider/logos.h is what scripts/gen_logos.py makes of the PNGs,
and each logo fits the picture's room (46 x 32, 1 bit)."""
import pathlib
import subprocess
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gen_logos as GL  # noqa: E402


def test_header_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/gen_logos.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


def test_each_logo_fits_and_draws():
    for n in GL.ORDER:
        im = Image.open(GL.SRC / f"{n}.png").convert("1")
        assert im.size == (GL.W, GL.H), n
        assert 60 < sum(1 for p in im.getdata() if p) < GL.W * GL.H // 2, n


def test_label_letters():
    for w in GL.LABELS:
        for ch in w:
            g = GL.GLYPHS[ch]
            assert len(g) == 8 and all(len(r) == 5 for r in g), ch
