"""RIFT v0.30 (QA's review of LEAN's "keys first"): a steady stream of key items must not starve the
polls that skip a pass which took one. The ColdFire alone (emu_coupled, the DSP off), live recording
(REC + PLAY), then [TRIG] key items put straight into the UI queue (queue_send 0x40001896, as the panel
driver sends them), a press or a release every frame for STREAM frames. Checks:

  1. every item comes out of the queue (the receive at 0x4002f184), none left over after the stream;
  2. our UI polls keep running during the stream: rec_poll (which carries rpt_poll's held repeats, the
     value display, rt_poll's saves) at least once for every 9 items received, and smp_er_poll with it;
  3. the audio ISR keeps its period (the emulator's run did not stop).

Usage: emu_keystream.py --build BUILD.syx [--stream 600] [--json OUT]"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
from emu_coupled import Coupled                                 # noqa: E402

QUEUE_SEND, UI_QUEUE, RECV_RET = 0x40001896, 0x4059D214, 0x4002F184
ITEMS_AT = 0x46A30000


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--stock", default=str(HERE.parent.parent / "Digitone_II_OS1.11.syx"))
    p.add_argument("--snapshot", default=str(HERE.parent.parent / "digikit/out/snapshots/dn2-1.11/ui800M-v014.snap"))
    p.add_argument("--layout", default=str(HERE.parent / "src/dnfw/mods/waverider_code.json"))
    p.add_argument("--stream", type=int, default=600)
    p.add_argument("--json", default=None)
    a = p.parse_args()
    lay = json.loads(pathlib.Path(a.layout).read_text())["layout"]
    from unicorn import UC_HOOK_CODE                             # noqa: PLC0415
    from unicorn import m68k_const as K                          # noqa: PLC0415
    c = Coupled(a.build, a.snapshot, a.stock, dsp=False)
    P = c.panel.panelin
    key = lambda code: divmod(code - 1, 8)                       # noqa: E731
    n = {"recv": 0, "rec_poll": 0, "er_poll": 0, "on": False}
    pending = set()

    def recv(uc, addr, size, ud):
        it = uc.reg_read(K.UC_M68K_REG_D0)
        if it and 0x40000000 <= it < 0x50000000:
            t, code, flags = struct.unpack(">III", bytes(uc.mem_read(it, 12)))
            if t == 0 and (code, flags) in pending:
                pending.discard((code, flags))
                n["recv"] += 1
    c.uc.hook_add(UC_HOOK_CODE, recv, begin=RECV_RET, end=RECV_RET)
    for name, sym in (("rec_poll", "rec_poll"), ("er_poll", "smp_er_poll")):
        if sym in lay:
            def cnt(uc, addr, size, ud, name=name):
                if n["on"]:
                    n[name] += 1
            c.uc.hook_add(UC_HOOK_CODE, cnt, begin=lay[sym], end=lay[sym])

    def held(code, on, k=2):
        c.machine.pc = (P.press if on else P.release)(c.machine.m, c.panel.profile, *key(code))
        c.periods(k)
    c.periods(10)
    held(19, True); held(20, True); held(20, False); held(19, False)
    c.periods(20)
    n["on"] = True
    sent = 0
    for f in range(a.stream):
        k = 25 + (f // 2) % 7
        flags = 1 if f % 2 == 0 else 0x10
        at = ITEMS_AT + 16 * (f % 128)
        c.uc.mem_write(at, struct.pack(">IIII", 0, k, flags, 0))
        pending.add((k, flags))
        c.call(QUEUE_SEND, UI_QUEUE, at, 2, 0)
        sent += 1
        if not c.period():
            break
    c.periods(120)                                               # the queue drains
    n["on"] = False
    rep = {"sent": sent, **{k: v for k, v in n.items() if k != "on"}, "left": len(pending), "halt": c.halt}
    checks = {
        "1. every item comes out of the queue": rep["left"] == 0 and rep["recv"] > 0,
        "2. rec_poll runs at least once for every 9 items received": rep["rec_poll"] * 9 >= rep["recv"],
        "2b. smp_er_poll runs with it": rep["er_poll"] * 9 >= rep["recv"],
        "3. the ISR kept its period (no halt)": not c.halt,
    }
    for k, ok in checks.items():
        print(("  ok    " if ok else "  FAIL  ") + k, flush=True)
    print(f"  numbers: {rep}", flush=True)
    rep["checks"] = checks
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1))
    ok = all(checks.values())
    print("PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
