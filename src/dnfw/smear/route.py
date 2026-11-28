"""RIFT v0.30: the track a DSP voice plays (TRK_ROUTE), as an emitter, without numpy: smear.stage and the
sampler's one_voice (SLICE and GRID, one voice a track) both use it, and the ColdFire emulator's steps that
build the sampler's program (emu_slides.py, under digikit's venv) have no numpy."""
from __future__ import annotations

from ..perc.dsl import Prog


def _route(p: Prog, d: int, v: int) -> None:
    """Rd = the track DSP voice Rv plays (the s16 at TRK_ROUTE + 2v; its low 16 bits). d, v in R8..R15;
    clobbers R11..R13, I1"""
    from ..sampler import machines as SM
    p.lsh(12, v, 1)
    p.iconst(11, SM.TRK_ROUTE)
    p.iop(12, 11, "+", 12)
    p.iconst(11, 2)
    p.iop(13, 12, "AND", 11)
    p.iconst(11, -4)
    p.iop(12, 12, "AND", 11)
    p.seti(1, 12)
    p.ldi(d, 0, 1)
    p.ifz(13, "NE", lambda: p.lsh(d, d, -16))
    p.iconst(11, 0xFFFF)
    p.iop(d, d, "AND", 11)
