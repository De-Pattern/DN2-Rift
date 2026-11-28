"""RIFT v0.31, RIFT SETTINGS under digikit's ColdFire emulator (csrc/sampler/rec.c's keys,
smp_page.c's set_draw, csrc/jump/jump.c's sector, csrc/sampler/link.c's K_SETS): the gate's check.

    DT2_SECTIONS=../sec111 DT2_MAIN_IMG=../sec111/section_3_MAIN_OS.bin \\
    DNFW_EMU_FLAGS='{"weakptr": false}' ../digikit/.venv/bin/python -u scripts/emu_settings.py \\
        --build out/b --snapshot ../digikit/out/snapshots/dn2-1.11/ui800M-v014.snap \\
        --json out/settings.json [--png-dir out/settings]

The owner (2026-11-28): "i want an option to lessen or remove it for users", "lets put it in +drive
settings". The +Drive is played by Python (emu_erase.py's harness). Checked:

- **ui**: the browser opened as a person opens it, +DRIVE, RIGHT: the menu, ERASE MOD DATA selected;
  DOWN: SETTINGS; YES: RIFT SETTINGS, the GUARD SAFE. RIGHT: LOOSE, RIGHT: OFF, RIGHT: OFF still,
  LEFT: LOOSE, YES: OFF, YES: SAFE (round), YES: LOOSE. Each change asks the DSP's words again
  (smp_sets_asked) and writes the settings sector (SET_SECTOR: 'DN2S', version 1, flags bit 0
  DIRECT JUMP kept as it was, bits 1..2 the GUARD, the check word), and nothing else is written;
  a key that changes nothing writes nothing. NO: back to the menu, SETTINGS still selected; UP,
  YES: ERASE's first question as before (v0.39's keys), NO: nothing erased; LEFT: the menu shut.
- **boot**: a power-on on each sector: none (SAFE), LOOSE with DIRECT JUMP on (both kept), an
  older build's (bit 0 only: SAFE, DIRECT JUMP on), bits 1..2 = 3 (not a mode: SAFE), a bad
  check word (ignored: SAFE, DIRECT JUMP off). Each boot asks the DSP's words once the sector is
  read (smp_sets_asked, smp_sets_due), and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import emu_erase as E                                   # noqa: E402  (its +Drive, harness, browser)

SET = 0x6FF000
MAGIC, VERSION = 0x444E3253, 1
failures: list[str] = []
report: dict = {"checks": {}}


def check(name, ok, detail=""):
    report["checks"][name] = {"ok": bool(ok), "detail": detail}
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  ({detail})" if detail else ""), flush=True)
    if not ok:
        failures.append(name)


def sector(flags, good=True):
    w = [MAGIC, VERSION, flags]
    chk = (~w[0] ^ w[1] ^ w[2]) & 0xFFFFFFFF
    w.append(chk if good else chk ^ 1)
    return b"".join(struct.pack(">I", x) for x in w) + bytes(512 - 16)


def flags_of(disk):
    b = disk.get(SET)
    m, v, f, c = struct.unpack(">4I", b[:16])
    ok = m == MAGIC and v == VERSION and c == (~m ^ v ^ f) & 0xFFFFFFFF and not any(b[16:])
    return f if ok else None


def run_ui(a, lay, SMx):
    from emulib.panel import DOWN, LEFT, NO, RIGHT, UP, YES, Panel
    disk = E.Disk()
    disk.put(SET, sector(1))                            # DIRECT JUMP on: kept through every change
    machine, st = E.harness(a, disk, ready=False)
    panel = Panel(machine, png_dir=a.png_dir or "out/settings")
    i32 = lambda n: struct.unpack(">i", machine.read(lay[n], 4))[0]          # noqa: E731
    u8 = lambda n: machine.read(lay[n], 1)[0]                                # noqa: E731
    f0 = len(E.faults(machine))
    panel.settle(20_000_000)
    E.browser(machine, panel, lay, SMx)
    machine.write(E.BLK_READY, struct.pack(">I", 1))
    panel.settle(8_000_000)
    check("the browser opens on its two stores", i32("smp_fb_open") == 1 and i32("smp_fb_store") == -1,
          f"open {i32('smp_fb_open')}, store {i32('smp_fb_store')}")
    check("the settings sector read: DIRECT JUMP on, the GUARD SAFE", u8("jmp_on") == 1 and u8("jmp_guard") == 0,
          f"jump {u8('jmp_on')}, guard {u8('jmp_guard')}")
    if i32("smp_fb_cur") != 0:
        panel.tap(UP, after=4_000_000)
    screens = report.setdefault("screens", {})
    panel.tap(RIGHT, after=6_000_000)
    screens["menu"] = panel.screen("settings_menu")
    check("+DRIVE, RIGHT: the menu, ERASE MOD DATA selected", i32("smp_fb_menu") == 3 and i32("smp_fb_mcur") == 0,
          f"menu {i32('smp_fb_menu')}, row {i32('smp_fb_mcur')}")
    panel.tap(DOWN, after=6_000_000)
    screens["menu_settings"] = panel.screen("settings_menu_row2")
    check("DOWN: SETTINGS selected", i32("smp_fb_menu") == 3 and i32("smp_fb_mcur") == 1,
          f"menu {i32('smp_fb_menu')}, row {i32('smp_fb_mcur')}")
    panel.tap(YES, after=6_000_000)
    screens["safe"] = panel.screen("settings_safe")
    check("YES: RIFT SETTINGS, the GUARD SAFE", i32("smp_fb_menu") == 7 and u8("jmp_guard") == 0,
          f"menu {i32('smp_fb_menu')}, guard {u8('jmp_guard')}")

    steps = [(RIGHT, "RIGHT", 1), (RIGHT, "RIGHT", 2), (RIGHT, "RIGHT", 2), (LEFT, "LEFT", 1),
             (YES, "YES", 2), (YES, "YES", 0), (YES, "YES", 1)]
    names = ("SAFE", "LOOSE", "OFF")
    for key, kname, want in steps:
        asked, sets, mark, was = i32("smp_sets_asked"), i32("smp_guard_sets"), len(disk.log), u8("jmp_guard")
        panel.tap(key, after=6_000_000)
        panel.settle(6_000_000)                        # jmp_poll writes the sector on the UI pass
        g = u8("jmp_guard")
        writes = [x for x in disk.log[mark:] if x[0] != "R"]
        changed = want != was
        f = flags_of(disk)
        if changed:
            ok = (g == want and i32("smp_sets_asked") == asked + 1 and i32("smp_guard_sets") == sets + 1
                  and writes == [("W", SET, 1)] and f == (1 | want << 1) and i32("smp_fb_menu") == 7)
        else:
            ok = g == want and i32("smp_sets_asked") == asked and not writes and i32("smp_fb_menu") == 7
        check(f"{kname}: the GUARD {names[want]}" + (", the DSP's words asked again, the sector written (DIRECT JUMP kept)"
                                                     if changed else ", nothing asked or written"),
              ok, f"guard {g}, asked +{i32('smp_sets_asked') - asked}, writes {writes}, flags {f}")
        screens[f"{kname.lower()}_{names[want].lower()}_{len(screens)}"] = panel.screen(f"settings_{names[want].lower()}")
    panel.tap(NO, after=6_000_000)
    check("NO: back to the menu, SETTINGS still selected", i32("smp_fb_menu") == 3 and i32("smp_fb_mcur") == 1,
          f"menu {i32('smp_fb_menu')}, row {i32('smp_fb_mcur')}")
    mark = len(disk.log)
    panel.tap(UP, after=4_000_000)
    panel.tap(YES, after=6_000_000)
    check("UP, YES: ERASE MOD DATA's first question, as before", i32("smp_fb_menu") == 4,
          f"menu {i32('smp_fb_menu')}")
    panel.tap(NO, after=6_000_000)
    panel.tap(RIGHT, after=4_000_000)
    panel.tap(LEFT, after=4_000_000)
    writes = [x for x in disk.log[mark:] if x[0] != "R"]
    check("NO: nothing erased; RIGHT, LEFT: the menu shut", i32("smp_fb_menu") == 0 and not writes
          and i32("smp_er_state") == 0 and i32("smp_er_lock") == 0, f"menu {i32('smp_fb_menu')}, writes {writes}")
    check("the GUARD LOOSE and DIRECT JUMP on, on the +Drive", flags_of(disk) == 3, f"flags {flags_of(disk)}")
    check("no fault, no harness error", len(E.faults(machine)) == f0 and not st.get("errors"),
          f"faults {len(E.faults(machine)) - f0}, errors {st.get('errors')}")
    return disk


def boot_once(a, lay, disk):
    from emulib.panel import Panel
    machine, st = E.harness(a, disk)
    panel = Panel(machine, png_dir=a.png_dir or "out/settings")
    i32 = lambda n: struct.unpack(">i", machine.read(lay[n], 4))[0]          # noqa: E731
    u8 = lambda n: machine.read(lay[n], 1)[0]                                # noqa: E731
    f0 = len(E.faults(machine))
    mark = len(disk.log)
    panel.settle(30_000_000)
    return {"guard": u8("jmp_guard"), "jump": u8("jmp_on"), "asked": i32("smp_sets_asked"),
            "loaded": i32("jmp_loaded"), "writes": [x for x in disk.log[mark:] if x[0] == "W" and x[1] == SET],
            "faults": len(E.faults(machine)) - f0, "errors": st.get("errors")}


def run_boot(a, lay, after_ui):
    cases = [("no settings sector", None, 0, 0),
             ("LOOSE with DIRECT JUMP on", sector(1 | 1 << 1), 1, 1),
             ("OFF", sector(2 << 1), 2, 0),
             ("an older build's sector (bit 0 only)", sector(1), 0, 1),
             ("GUARD bits 3 (not a mode)", sector(3 << 1), 0, 0),
             ("a bad check word", sector(1 | 2 << 1, good=False), 0, 0),
             ("the ui run's +Drive", "ui", 1, 1)]
    rows = {}
    for name, sec, guard, jump in cases:
        if sec == "ui":
            d = after_ui
            d.log, d.cmds, d.on_trim = [], [], None
        else:
            d = E.Disk()
            if sec is not None:
                d.put(SET, sec)
        r = boot_once(a, lay, d)
        rows[name] = r
        check(f"power-on, {name}: the GUARD {('SAFE', 'LOOSE', 'OFF')[guard]}, DIRECT JUMP {'on' if jump else 'off'}, "
              f"the DSP's words asked, nothing written",
              r["loaded"] == 1 and r["guard"] == guard and r["jump"] == jump and r["asked"] >= 1 and not r["writes"]
              and r["faults"] == 0 and not r["errors"], json.dumps(r)[:300])
    report["boot"] = rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--json", default=None)
    p.add_argument("--png-dir", default=None)
    p.add_argument("--layout", default=str(HERE.parent / "src/dnfw/mods/waverider_code.json"))
    a = p.parse_args()
    lay = json.loads(pathlib.Path(a.layout).read_text())["layout"]
    for k in ("jmp_guard", "smp_sets_asked", "smp_sets_due", "smp_guard_sets", "jmp_loaded"):
        if k not in lay:
            check(f"the layout has {k}", False)
    if failures:
        print("settings: FAIL " + ", ".join(failures))
        return 1
    sys.path.insert(0, str(HERE.parent / "src"))
    from dnfw.sampler import machines as SMx                    # noqa: PLC0415
    random.seed(31)
    disk = run_ui(a, lay, SMx)
    run_boot(a, lay, disk)
    report["failures"] = failures
    report["ok"] = not failures
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(f"settings: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)} ({len(report['checks'])} checks)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
