"""Addresses that are either fixed (an int, emitted as an immediate) or a base read from a
word plus an offset (`At`), so one copy of SMEAR's code serves both VOC lanes, each lane's
buffers found from its base word."""

from __future__ import annotations

from dataclasses import dataclass

from ..perc.dsl import Prog


@dataclass(frozen=True)
class At:
    word: int                     # the word holding the base (a byte address)
    off: int = 0

    def __add__(self, k: int) -> "At":
        return At(self.word, self.off + k)


def at_reg(p: Prog, d: int, a, t: int = 12) -> None:
    """Rd = the address A. For an At: the base word, plus the offset through Rt (R8..R15,
    not d)."""
    if isinstance(a, int):
        p.iconst(d, a)
        return
    assert 8 <= t <= 15 and t != d
    p.ld(d, a.word)
    if a.off:
        p.iconst(t, a.off)
        p.iop(d, t, "+", d)


def ldw(p: Prog, d: int, a) -> None:
    """Rd = the word at A (an At: through R12, R13 and I3)."""
    if isinstance(a, int):
        p.ld(d, a)
        return
    at_reg(p, 12, a, 13)
    p.seti(3, 12)
    p.ldi(d, 0, 3)


def stw(p: Prog, a, s: int) -> None:
    """The word at A = Rs (an At: through R12, R13 and I3; s is not R12 or R13)."""
    if isinstance(a, int):
        p.st(a, s)
        return
    assert s not in (12, 13)
    at_reg(p, 12, a, 13)
    p.seti(3, 12)
    p.sti(0, 3, s)
