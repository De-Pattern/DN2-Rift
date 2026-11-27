"""RIFT v0.30 (a tester, 2026-11-26, on DN2 mk2 v0.74: "quite a few things ... accumulate performance debt
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
    by, ui = {}, {}
    state = {"in": False}
    if attribute:
        def code(uc, addr, size, ud):
            i = bisect.bisect_right(addrs, addr) - 1
            k = syms[i][1] if i >= 0 else "?"
            d = by if state["in"] else ui
            d[k] = d.get(k, 0) + 1
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
    P = c.panel.panelin
    key = lambda code: divmod(code - 1, 8)                       # noqa: E731

    def held(code, on, n=2):
        c.machine.pc = (P.press if on else P.release)(c.machine.m, c.panel.profile, *key(code))
        c.periods(n)
    out = {}
    for phase in ("stopped", "playing", "liverec"):
        if phase == "playing":
            held(20, True); held(20, False)                      # PLAY
        if phase == "liverec":                                   # RECORD + PLAY... (REC held, PLAY: live)
            held(21, True); held(21, False)                      # STOP
            held(19, True); held(20, True); held(20, False); held(19, False)
        by.clear()
        ui.clear()
        c.isr_units.clear()
        n = 0
        while n < periods:
            if phase == "liverec" and n % 12 == 0:               # seven trig keys at once, then let go
                for k in range(25, 32):
                    c.machine.pc = P.press(c.machine.m, c.panel.profile, *key(k))
                c.periods(3)
                for k in range(25, 32):
                    c.machine.pc = P.release(c.machine.m, c.panel.profile, *key(k))
                n += 3
                continue
            if not c.period():
                break
            n += 1
        u = list(c.isr_units)
        out[phase] = {"periods": len(u), "isr_median": statistics.median(u) if u else None,
                      "isr_max": max(u) if u else None,
                      "ours_by_function": {k: round(v / max(1, len(u))) for k, v in
                                           sorted(by.items(), key=lambda kv: -kv[1])[:30]},
                      "ours_total": round(sum(by.values()) / max(1, len(u))),
                      "ui_ours_by_function": {k: round(v / max(1, len(u))) for k, v in
                                              sorted(ui.items(), key=lambda kv: -kv[1])[:30]},
                      "ui_ours_total": round(sum(ui.values()) / max(1, len(u))),
                      "ui_units": getattr(c, "ui_units", None)}
    out["halt"] = c.halt
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--stock", default=str(HERE.parent.parent / "Digitone_II_OS1.11.syx"))
    p.add_argument("--snapshot", default=str(HERE.parent.parent / "digikit/out/snapshots/dn2-1.11/ui800M-v014.snap"))
    p.add_argument("--layout", default=str(HERE.parent / "src/dnfw/mods/waverider_code.json"))
    p.add_argument("--periods", type=int, default=120)
    p.add_argument("--syms", default=None, help="every C symbol (WR_ALL_SYMS=FILE gen_waverider_code.py), statics too")
    p.add_argument("--json", default=None)
    a = p.parse_args()
    lay = json.loads(pathlib.Path(a.layout).read_text())["layout"]
    if a.syms:
        lay = {**lay, **json.loads(pathlib.Path(a.syms).read_text())}
    rep = {"stock": profile(a.stock, a.snapshot, a.stock, a.periods, False, lay),
           "build": profile(a.build, a.snapshot, a.stock, a.periods, True, lay)}
    for k in ("stopped", "playing", "liverec"):
        s, b = rep["stock"][k], rep["build"][k]
        print(f"{k}: ISR a period, stock median {s['isr_median']} max {s['isr_max']}; build median {b['isr_median']} "
              f"max {b['isr_max']}; our code {b['ours_total']} instructions a period", flush=True)
        print("   ours by function:", b["ours_by_function"], flush=True)
        print(f"   UI side, our code {b['ui_ours_total']} a period:", b["ui_ours_by_function"], flush=True)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1))
    return 0





def latency(build, snap, stock, frame_units, bursts=16, keys=7):
    """RIFT v0.31 (claude/rift-ui-latency-reading-2026-11-27.md; a tester's 3 ms stock / 101 ms mod): live
    recording's key latency, the frame fixed at FRAME_UNITS (stock's: a heavier ISR leaves the UI less,
    as on the unit). REC + PLAY, then KEYS trig keys pressed together and released together, BURSTS
    times; for each trig key item, from its press (or release) to the UI loop's receive returning it
    (the instruction after the stock call site, 0x4002f17e + 6: stock's own receive, or ours around it),
    in the emulator's clock units and in frames"""
    from unicorn import UC_HOOK_CODE                             # noqa: PLC0415
    from unicorn import m68k_const as K                          # noqa: PLC0415
    c = Coupled(build, snap, stock, dsp=False)
    c.frame_units = frame_units
    c.set_timing("faithful")
    P = c.panel.panelin
    key = lambda code: divmod(code - 1, 8)                       # noqa: E731
    clock = c.panel.timers
    sent, got = {}, []

    def after_receive(uc, addr, size, ud):
        it = uc.reg_read(K.UC_M68K_REG_D0)
        if not it:
            return
        b = bytes(uc.mem_read(it, 8))
        code = int.from_bytes(b[4:8], "big")
        if b[0] == 0 and 25 <= code < 25 + keys and code in sent:
            got.append((clock.now - sent.pop(code)) / frame_units)
    c.uc.hook_add(UC_HOOK_CODE, after_receive, begin=0x4002F17E + 6, end=0x4002F17E + 6)

    def held(code, on, n=2):
        c.machine.pc = (P.press if on else P.release)(c.machine.m, c.panel.profile, *key(code))
        c.periods(n)
    held(19, True); held(20, True); held(20, False); held(19, False)
    c.periods(20)
    for _ in range(bursts):
        for on in (True, False):
            for k in range(25, 25 + keys):
                c.machine.pc = (P.press if on else P.release)(c.machine.m, c.panel.profile, *key(k))
                sent[k] = clock.now
            c.periods(40)
            sent.clear()
    got.sort()
    return {"frames": [round(x, 2) for x in got], "n": len(got),
            "median": round(statistics.median(got), 2) if got else None, "max": round(max(got), 2) if got else None,
            "halt": c.halt}


def main_latency() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--stock", default=str(HERE.parent.parent / "Digitone_II_OS1.11.syx"))
    p.add_argument("--snapshot", default=str(HERE.parent.parent / "digikit/out/snapshots/dn2-1.11/ui800M-v014.snap"))
    p.add_argument("--latency", action="store_true")
    p.add_argument("--json", default=None)
    a, _ = p.parse_known_args()
    c = Coupled(a.stock, a.snapshot, a.stock, dsp=False)
    c.set_timing("faithful")
    fu = c.frame_units
    rep = {"frame_units": fu, "stock": latency(a.stock, a.snapshot, a.stock, fu),
           "build": latency(a.build, a.snapshot, a.stock, fu)}
    for k in ("stock", "build"):
        print(f"{k}: a trig key's press or release to its receive, frames (0.67 ms each): n {rep[k]['n']}, median {rep[k]['median']}, max {rep[k]['max']}; {rep[k]['frames']}", flush=True)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main_latency() if "--latency" in sys.argv else main())
