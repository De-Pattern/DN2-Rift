"""ship_gate's SHARC runner step, on its own (v0.28).

The step's verdict reads only this file and the runner's own run: the command below, its
exit code and its log. Its reuse record (gate_cache) holds what the runner read (traced:
its scripts, the repository modules it imported, the committed SHARC objects, digikit)
plus this file, gate_cache.py and the tracer -- not ship_gate.py and not the ColdFire's
build artefacts, which the runner never reads. So a change to a ColdFire test or to the
ColdFire code no longer throws away an unchanged DSP's pass (owner, 2026-10-27), while any
change to anything the runner reads still makes it run again. DSP identity (ship_gate,
never reused) ties the pass to the build: the build's section 7 must be exactly
dnfw.waverider.dsp.section7(stock), the image the runner ran.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def default_steps() -> list[str]:
    """the runner's own default step list, read from its source (so no step is ever left out)"""
    import re
    src = (HERE / "sharc_waverider_m5.py").read_text(encoding="utf-8")
    m = re.search(r'add_argument\("--steps", default="([^"]+)"', src)
    return m.group(1).split(",")


# v0.28: the runner in parts, each a step of its own with its own reuse record, so a gate cut
# off by a time limit keeps the parts that passed (the whole runner took more than two hours
# beside the ColdFire steps). The parts together are exactly the runner's default steps.
# v0.38: quickest first (v0.37's times: wipe 3 min, stock/ping 9, garbage 13, stress 15,
# chords 16, smp 17, mnm/frame 20, decode..guard 35, link..tdm 46), so a failing part shows
# early (v0.45: ping dropped with PING; the part is stock alone); ship_gate stops at the first part that fails. Each part runs in its own process, so
# the order changes nothing a part checks.
GROUPS = (("wipe",), ("stock",), ("garbage",), ("stress",), ("chords",), ("smp",),
          ("mnm", "frame"), ("decode", "map", "voice", "guard"), ("link", "rec", "mainrec", "pvmix", "tdm"),
          ("flexlevel",), ("mainmark",),         # v0.50: a FLEX take's level, unity and GAIN
          ("recwhole",),          # v0.39: whole takes with the link at work (about 70 min)
          # v0.45: FASCIA (type 18): bit-exact to live.py (the audition, idle, a steal, p-locks);
          # chords and beside the other machines, untriggered silence; garbage; the stress test
          ("fascia",), ("fchords", "fsilence"), ("fgarbage",), ("fstress",),
          ("fkeep",),             # RIFT v0.11: a held chord kept under a melody and REUSE re-strikes
          ("organ",),             # RIFT: ORGAN (type 19) bit-exact, beside FASCIA, a machine switch
          ("silt",),              # RIFT: SILT (type 20) bit-exact, two at once, a machine switch, a negative control
          ("sstress",),           # RIFT: sixteen SILT voices under the guard
          ("ligature",),          # RIFT: LIGATURE (type 21) bit-exact, two at once, a machine switch, a negative control
          ("lstress",),           # RIFT: sixteen LIGATURE voices under the guard
          ("digidrum",),          # RIFT: DIGIDRUM (type 22) bit-exact, two at once, a machine switch, a negative control
          ("dstress",),           # RIFT: sixteen DIGIDRUM voices under the guard
          ("plateau",),           # RIFT v0.17: PLATEAU (type 24) bit-exact on the bus, the one instance, a negative control
          ("pstress",),           # RIFT v0.17: a PLATEAU track beside fifteen FASCIA voices under the guard
          ("glass",),             # RIFT v0.18: GLASS (filter 6) bit-exact on FM Tone and FASCIA tracks, a negative control
          ("smear",),             # RIFT v0.16: SMEAR's stage bit-exact to its program, lanes, an empty slot
          ("mstress",))           # RIFT v0.16: sixteen SMEAR tracks
# RIFT (2026-11-13): no Machinedrum or Monomachine engine. The runner's parts that test only
# them do not exist on RIFT (sharc_waverider_m5.py, RIFT_GONE); the rest run as before, with
# rstress in place of the PERC/MnM stress scenarios.
RIFT_GONE = ("voice", "guard", "wipe", "mnm", "garbage", "frame", "cost")


def _rift() -> bool:
    import sys as _s
    _src = str(pathlib.Path(__file__).resolve().parents[1] / "src")
    if _src not in _s.path:
        _s.path.insert(0, _src)
    from dnfw.perc import program as _pp       # noqa: PLC0415
    return _pp.RIFT


if _rift():
    GROUPS = tuple(g for g in (tuple(x for x in grp if x not in RIFT_GONE) for grp in GROUPS) if g)


def parts() -> list[list[str]]:
    want = [x for x in default_steps() if not (_rift() and x in RIFT_GONE)]   # RIFT: the runner drops these
    out = [[s for s in g if s in want] for g in GROUPS]
    out = [g for g in out if g]
    left = [s for s in want if not any(s in g for g in out)]
    if left:
        out.append(left)                        # any step not grouped runs in a part of its own
    assert sorted(s for g in out for s in g) == sorted(want)
    return out


def command(stock: str, digikit_sharc: str, steps: list[str] | None = None, tag: str = "",
            python: str | None = None) -> list:
    """PYTHON: the interpreter (2026-11-12: the gate passes PyPy; scripts/gate_crosscheck.py CPython)."""
    cmd = [python or sys.executable, "scripts/sharc_waverider_m5.py", "--image", stock, "--digikit", digikit_sharc]
    if steps is not None:
        cmd += ["--steps", ",".join(steps), "--tag", tag or "part"]
    return cmd


def verdict(rc: int, out: str) -> tuple[bool, str]:
    return rc == 0, ("all steps PASS, incl. types 0-4 bit-identical to stock" if rc == 0 else out[-800:])


OWN = (HERE / "gate_sharc.py",)
