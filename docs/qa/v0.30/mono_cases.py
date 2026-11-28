"""The review of v0.30: SMEAR's mono rule on state (dnfw.smear.stage._mono, QA v0.29's B1 as taken) run as
the DSP's program in the DSL's run mode over a small memory, as docs/qa/v0.29/mono_cases.py did: which
voices get a FADE bit, and how many of the DSL's steps the scan takes on a block (the DSL's steps count
constant loads: they are not the unit's instructions or cycles).

    PYTHONPATH=src MD_OS_BIN=... DT2_SECTION7=... python3 docs/qa/v0.30/mono_cases.py
"""
from dnfw.perc.dsl import Mem, Prog
from dnfw.sampler import machines as SM
from dnfw.smear import stage as SG
from dnfw.waverider import dsp


def fade(mail: dict, route: dict) -> tuple[int, int]:
    """MAIL = {voice: (trig, frames)} for the mailboxes smp.asm wrote this block; ROUTE = {voice: track}.
    -> FADE, the program's steps"""
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
    n0 = p.steps
    SG._mono(p, S)
    return mem.get(S.FADE), p.steps - n0


OWN = {v: v for v in range(16)}                # voice v plays track v (the runner's _route_identity)
CASES = (
    # the rule
    ("a second note on another voice of the track", {0: (0, 1000), 1: (1, 1000)}, {}),
    ("control: the two voices on two tracks", {0: (0, 1000), 1: (1, 1000)}, {1: 1}),
    ("a chord of four on one block", {v: (1, 1000) for v in range(4)}, {}),
    ("the old note on voice 5, the new one (triggered) on voice 2", {5: (0, 1000), 2: (1, 1000)}, {}),
    ("... its fade skipped by the guard, the block after: both on, neither triggered", {5: (0, 1000), 2: (0, 1000)}, {}),
    ("the old note on voice 2, the new one on voice 5, the block after a skipped fade", {2: (0, 1000), 5: (0, 1000)}, {}),
    # the scan's size on a block with no note
    ("steps: no SMEAR voice", {}, OWN),
    ("steps: one SMEAR track sounding, no note", {0: (0, 1000)}, OWN),
    ("steps: four SMEAR tracks sounding, no note", {v: (0, 1000) for v in range(4)}, OWN),
    ("steps: sixteen SMEAR tracks sounding, no note", {v: (0, 1000) for v in range(16)}, OWN),
    ("steps: sixteen SMEAR tracks, all triggered together", {v: (1, 1000) for v in range(16)}, OWN),
)

if __name__ == "__main__":
    assert SG.MONO
    for name, mail, route in CASES:
        got, steps = fade(mail, route)
        left = [v for v in sorted(mail) if not got >> v & 1]
        print(f"{name}: FADE {got:#018b}; still running: {left}; {steps} steps")
