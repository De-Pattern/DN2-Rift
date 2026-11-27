"""RIFT v0.30 (oksami, 2026-11-26, on DN2 mk2 v0.74: "quite a few things ... accumulate performance debt
that are triggering interrupts often ... sample communication, sampler modulation and recording, and a
few other features seem to interrupt even when not enabled"): where the ColdFire's audio ISR spends its
time, stock against a build, period by period.

The coupled emulator with the DSP off (the ColdFire alone: its ISR, the sequencer, the UI). For each
image: N periods stopped, then N playing (PLAY pressed), the ISR's cost a period (the fast stepper's
units, as emu_coupled counts it) and, for the build, every instruction the ISR runs inside our code
counted by the function it is in (the layout's symbols). Not a gate step: a probe.

    python3 scripts/emu_cf_profile.py --build RIFT_vX.Y_OS1.11.syx [--periods 120] [--json out.json]
"""
from __future__ import annotations

import argparse
import bisect
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
from emu_coupled import Coupled, ISR, ISR_RTE                   # noqa: E402

OUR = ((0x46AC0000, 0x46B00000), (0x4670C000, 0x46710000), (0x46708000, 0x4670A000),
       (0x467A8000, 0x467AA000), (0x467B8000, 0x467BA000))


def profile(build, snap, stock, periods, attribute, lay):
    c = Coupled(build, snap, stock, dsp=False)
    from unicorn import UC_HOOK_CODE                            # noqa: PLC0415
    syms = sorted((v, k) for k, v in lay.items() if isinstance(v, int) and any(a <= v < b for a, b in OUR))
    addrs = [a for a, _ in syms]
    by = {}
    state = {"in": False}
    if attribute:
        def code(uc, addr, size, ud):
            if not state["in"]:
                return
            i = bisect.bisect_right(addrs, addr) - 1
            k = syms[i][1] if i >= 0 else "?"
            by[k] = by.get(k, 0) + 1
        for a, b in OUR:
            c.uc.hook_add(UC_HOOK_CODE, code, begin=a, end=b - 1)
    orig_call = c.call

    def call(fn, *args, **kw):
        if fn == ISR:
            state["in"] = True
            try:
                return orig_call(fn, *args, **kw)
            finally:
                state["in"] = False
        return orig_call(fn, *args, **kw)
    c.call = call
    out = {}
    for phase in ("stopped", "playing"):
        if phase == "playing":
            c.press_play() if hasattr(c, "press_play") else None
        by.clear()
        c.isr_units.clear()
        for _ in range(periods):
            if not c.period():
                break
        u = list(c.isr_units)
        out[phase] = {"periods": len(u), "isr_median": statistics.median(u) if u else None,
                      "isr_max": max(u) if u else None,
                      "ours_by_function": {k: round(v / max(1, len(u))) for k, v in
                                           sorted(by.items(), key=lambda kv: -kv[1])[:30]},
                      "ours_total": round(sum(by.values()) / max(1, len(u)))}
    out["halt"] = c.halt
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--stock", default=str(HERE.parent.parent / "Digitone_II_OS1.11.syx"))
    p.add_argument("--snapshot", default=str(HERE.parent.parent / "digikit/out/snapshots/dn2-1.11/ui800M-v014.snap"))
    p.add_argument("--layout", default=str(HERE.parent / "src/dnfw/mods/waverider_code.json"))
    p.add_argument("--periods", type=int, default=120)
    p.add_argument("--json", default=None)
    a = p.parse_args()
    lay = json.loads(pathlib.Path(a.layout).read_text())["layout"]
    rep = {"stock": profile(a.stock, a.snapshot, a.stock, a.periods, False, lay),
           "build": profile(a.build, a.snapshot, a.stock, a.periods, True, lay)}
    for k in ("stopped", "playing"):
        s, b = rep["stock"][k], rep["build"][k]
        print(f"{k}: ISR a period, stock median {s['isr_median']} max {s['isr_max']}; build median {b['isr_median']} "
              f"max {b['isr_max']}; our code {b['ours_total']} instructions a period", flush=True)
        print("   ours by function:", b["ours_by_function"], flush=True)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
