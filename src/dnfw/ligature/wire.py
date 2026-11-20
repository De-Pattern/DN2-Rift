"""LIGATURE's wirings as the build needs them, without numpy (the browser patcher builds the firmware):
dnfw.ligature.live's constants, its types' names and the factory patches encoded (wire.json, written by
write_json from live; test_ligature_wire holds the two equal)."""
from __future__ import annotations

import json
import pathlib

WIRE_JSON = pathlib.Path(__file__).with_name("wire.json")
_D = json.loads(WIRE_JSON.read_text(encoding="utf-8"))
NB, NSRC, NP = _D["NB"], _D["NSRC"], _D["NP"]
WSLOTS, WWORDS, WHDR, WMAGIC, WVERSION = _D["WSLOTS"], _D["WWORDS"], _D["WHDR"], _D["WMAGIC"], _D["WVERSION"]
WTABLE_WORDS = WHDR + WSLOTS * WWORDS
TYPES = tuple(_D["TYPES"])
TYPE_NAMES = {int(k): v for k, v in _D["TYPE_NAMES"].items()}


def factory() -> list[list[int]]:
    return [list(w) for w in _D["FACTORY"]]


def write_json() -> None:
    from . import live as L
    fac = []
    for k in range(L.NP):
        rows, o, bm = L.patch_rows(k)
        fac.append(L.encode(rows, o, bm))
    d = {"note": "written by dnfw.ligature.wire.write_json from dnfw.ligature.live; do not edit",
         "NB": L.NB, "NSRC": L.NSRC, "NP": L.NP, "WSLOTS": L.WSLOTS, "WWORDS": L.WWORDS, "WHDR": L.WHDR,
         "WMAGIC": L.WMAGIC, "WVERSION": L.WVERSION, "TYPES": list(L.TYPES),
         "TYPE_NAMES": {str(t): L.TYPE_NAMES[t] for t in L.TYPES}, "FACTORY": fac}
    WIRE_JSON.write_text(json.dumps(d) + "\n", encoding="utf-8", newline="\n")
