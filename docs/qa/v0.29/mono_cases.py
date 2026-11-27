"""The review of v0.29: SMEAR's mono rule (dnfw.smear.stage._mono) run as the DSP's program in the DSL's run
mode over a small memory: which voices get a FADE bit, case by case. No runner, no SHARC: the same Python the
assembly is generated from.

    PYTHONPATH=src MD_OS_BIN=... DT2_SECTION7=... python3 docs/qa/v0.29/mono_cases.py
"""
from dnfw.perc.dsl import Mem, Prog
from dnfw.sampler import machines as SM
from dnfw.smear import stage as SG
from dnfw.waverider import dsp


def fade(mail: dict, route: dict) -> int:
    """MAIL = {voice: (trig, frames)} for the mailboxes smp.asm wrote this block; ROUTE = {voice: track}"""
    S = dsp.smear_layout()
    mem = Mem()
    for v in range(16):
        a = SM.TRK_ROUTE + 2 * v
        w = mem.get(a & ~3)
        k = route.get(v, 0) & 0xFFFF
        mem.put(a & ~3, (w & 0xFFFF) | k << 16 if a & 2 else (w & 0xFFFF0000) | k)
    for v, (trig, frames) in mail.items():
        mem.put(S.mb(v, SG.MB_ON), SG.MB_MAGIC)
        mem.put(S.mb(v, SG.MB_TRIG), trig)
        mem.put(S.mb(v, SG.MB_FRAMES), frames)
    p = Prog("run", mem)
    p.iconst(0, 0)
    p.st(S.FADE, 0)
    SG._mono(p, S)
    return mem.get(S.FADE)


CASES = (
    ("a second note on another voice of the track (the runner's case)", {0: (0, 1000), 1: (1, 1000)}, {}, 0b01),
    ("control: the two voices on two tracks", {0: (0, 1000), 1: (1, 1000)}, {1: 1}, 0),
    ("a chord: two notes of one track on the same block", {0: (1, 1000), 1: (1, 1000)}, {}, None),
    ("a chord of four on the same block", {v: (1, 1000) for v in range(4)}, {}, None),
    ("the same chord struck again on the same voices", {v: (1, 1000) for v in range(4)}, {}, None),
    ("a single note after that chord, on a fifth voice", {**{v: (0, 1000) for v in range(4)}, 4: (1, 1000)}, {}, 0b1111),
    ("the old voice's glue left out by the guard on the new note's block (no mailbox)", {1: (1, 1000)}, {}, None),
    ("... and the block after: both voices on, neither triggered", {0: (0, 1000), 1: (0, 1000)}, {}, None),
)

if __name__ == "__main__":
    assert SG.MONO
    for name, mail, route, want in CASES:
        got = fade(mail, route)
        on = sorted(mail)
        left = [v for v in on if not got >> v & 1]
        print(f"{name}: FADE {got:#06b}; voices of the track still running after the block: {left}"
              + ("" if want is None else f"  (expected {want:#06b}: {'ok' if got == want else 'DIFFERS'})"))
