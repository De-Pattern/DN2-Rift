"""RIFT v0.30 (the owner, 2026-11-27, on SLICE: "p locks aren't always hit on time ... almost as if
it lags a step behind"; "I p-locked the first slice on a few steps and it kept playing the rim shot
for a while"): which slice each sequenced, slice-locked trig is given, at the frame its note starts.

The sequencer plays it, as a user's pattern does. Track 1 (index 0), GRID's ALLOCATE SLICE (the
owner's way to lay slice locks): trigs placed on steps 1, 3, 5 and 7 in GRID RECORDING, CREATE
LINEAR LOCKS locks slices 1, 2, 3, 4 on them; then the track made SLICE (type 13) and PLAY.

Each audio period, the frame the ColdFire sends the DSP is read: when a voice of track 1 starts a
note (its trig word in the frame), its SLCE word in that same frame (what the DSP's slice_bounds
reads at the note's start: value >> 1 is the slice, 0 NOTE) is recorded, and the next few frames'
too (a lock that arrives late shows as a change after the start).

Measured, per note: the step it fell on (the sequencer's TRACK_CUR), the slice that step is locked
to, the slice the frame carried at the note's start, and whether it changed later.

Usage: emu_coupled_slicelag.py --build BUILD.syx [--json OUT] [--passes 2]"""

from __future__ import annotations

import sys as _osport_sys, pathlib as _osport_pl  # noqa: E401
_osport_sys.path.insert(0, str(_osport_pl.Path(__file__).resolve().parents[1] / 'src'))

import argparse
import json
import pathlib
import struct
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from emu_coupled import Coupled                                 # noqa: E402
import emu_coupled_flex as F                                    # noqa: E402

_OSV = __import__("os").environ.get("DN2_OS", "1.11")
SLOT_TRACK = 0x80005308
KIT = 0x4210C08C
T = 0
SLCE_SLOT = 44
STEPS = (0, 1, 2, 3)                    # consecutive steps: a step behind shows as the neighbour's slice
RELATCH, RELATCH_BLOCKS = 0x2E0100, 24
TEMPO = 0x80005E60 + 2 * 108


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--layout", default=str(HERE.parent / "src/dnfw/mods/waverider_code.json"))
    p.add_argument("--stock", default=str(HERE.parent.parent / f"Digitone_II_OS{_OSV}.syx"))
    p.add_argument("--snapshot", default=str(HERE.parent.parent / f"digikit/out/snapshots/dn2-{_OSV}/ui800M-v014.snap"))
    p.add_argument("--json", default=None)
    p.add_argument("--passes", type=int, default=2)
    p.add_argument("--type", type=lambda s: int(s, 0), default=13, help="the track's machine when playing (13 SLICE, 12 GRID)")
    a = p.parse_args()
    lay = json.loads(pathlib.Path(a.layout).read_text())["layout"]
    c = Coupled(a.build, a.snapshot, a.stock, verbose=False)
    c.watchdog()
    F.install_smoother_model(c)
    rep = {"notes": [], "numbers": {}}
    t0 = time.perf_counter()
    P = c.panel.panelin
    key = lambda code: divmod(code - 1, 8)                       # noqa: E731

    def held(code, on, n=3):
        c.machine.pc = (P.press if on else P.release)(c.machine.m, c.panel.profile, *key(code))
        c.periods(n)

    def tap(code, n=3):
        held(code, True, n)
        held(code, False, n)

    # GRID's ALLOCATE SLICE, as the alloc gate step lays it (four trigs, linear locks 1..4)
    c.poke(KIT + 52 + 0xDE, bytes([12]))
    c.periods(4)
    tap(2, 6)
    tap(19, 6)                                                   # GRID RECORDING
    for st in STEPS:
        tap(25 + st, 4)
    tap(19, 6)
    tap(10, 6)                                                   # YES: ALLOCATE SLICE
    tap(10, 6)                                                   # YES: CREATE LINEAR LOCKS
    n_locked = c.long(lay["slc_alloc_n"])
    locks = {}
    for st in range(8):
        v = c.call(0x40037C52, 0, __import__("dnfw.sampler.machines", fromlist=["x"]).SLICE_REC, st)[0] & 0xFFFF
        if v != 0xFFFF and v:
            locks[st] = v
    tap(12, 6)                                                   # NO (the menu closed if still up)
    rep["numbers"]["locked"] = n_locked
    rep["numbers"]["locks"] = {k + 1: v for k, v in locks.items()}
    print(f"  locked {n_locked}: {rep['numbers']['locks']}", flush=True)
    c.poke(KIT + 52 + 0xDE, bytes([a.type]))
    c.periods(6)
    pat = c.long(F.SEQ_PATTERN)
    c.poke(pat + F.PAT_LENGTH, struct.pack(">H", 4))
    bpm120 = struct.unpack(">H", c.read(TEMPO, 2))[0] or 14400
    step = 86400000 // bpm120
    rep["numbers"]["step_samples"] = step
    tap(20)                                                      # PLAY
    from dnfw.sampler import machines as SMx                    # noqa: E402
    slot, lo, top = SMx.RECORDS[SMx.SLICE_REC]
    from dnfw.waverider import dsp as WD                        # noqa: E402

    def fslice(fr, v):                                           # voice v's SLCE word in the frame -> slice (0 NOTE)
        o = 168 + 2 * slot + 146 * v
        if not fr or len(fr) < o + 2:
            return None
        return max(0, min(top, (struct.unpack(">H", fr[o:o + 2])[0] >> 8) - lo)) >> 1
    n_periods = (len(STEPS) * step) // 32 + 80
    prev_step, step_at = None, 0
    trace = []
    for n in range(n_periods):
        if not c.period():
            break
        fr = c.last_frame
        cur = c.read(F.TRACK_CUR + T, 1)[0]
        if cur != prev_step:
            prev_step, step_at = cur, n
            rep["notes"].append({"step": cur + 1, "lock_slice": (locks.get(cur, 0) >> 9) or None, "trace": []})
        k = n - step_at
        if k <= 90 and rep["notes"]:
            trigw = list(struct.unpack(">4H", fr[34:42])) if fr else None
            sl = [fslice(fr, v) for v in range(16)]
            rep["notes"][-1]["trace"].append({"k": k, "block": c.blocks, "trig": trigw, "slices": sl})
        if n % 100 == 0:
            print(f"  [play] period {n}/{n_periods} step {cur + 1}, {time.perf_counter() - t0:.0f} s", flush=True)
    for o in rep["notes"]:
        want = o["lock_slice"]
        trig_k = [t["k"] for t in o["trace"] if t["trig"] and any(t["trig"])]
        slice_k = next((t["k"] for t in o["trace"] if want in t["slices"]), None)
        o["first_trig_k"] = trig_k[:3]
        o["first_slice_k"] = slice_k
        o["blocks_late"] = None if slice_k is None or not trig_k else slice_k - trig_k[0]
        print("  note", {kk: o[kk] for kk in ("step", "lock_slice", "first_trig_k", "first_slice_k", "blocks_late")}, flush=True)
        for t in o["trace"]:
            if t["trig"] and any(t["trig"]) or (o["trace"].index(t) and t["slices"] != o["trace"][o["trace"].index(t) - 1]["slices"]):
                print("    ", t, flush=True)
    ontime = [o for o in rep["notes"] if o["blocks_late"] is not None and o["blocks_late"] <= 0]
    late = [o for o in rep["notes"] if o not in ontime]
    rep["numbers"]["summary"] = {"steps": len(rep["notes"]), "on_time": len(ontime), "late_or_never": len(late),
                                 "relatch_window_blocks": RELATCH_BLOCKS}
    rep["seconds"] = round(time.perf_counter() - t0)
    rep["halt"] = c.halt
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1, default=str))
    print("  summary", rep["numbers"]["summary"], flush=True)
    ok = bool(rep["notes"]) and not late and not c.halt
    print("PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
