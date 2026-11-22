"""SMEAR's tables the ColdFire sends at power-on (dsp.link_tables), as the build ships them: read from
the committed ddr.json, so the build needs no numpy (it also runs in the browser patcher, which has
none). dnfw.smear.program.write_ddr_json writes the file (scripts/gen_smear_asm.py);
test_smear_ddr holds it equal to what stage.py and program.py compute."""
from __future__ import annotations

import json
import pathlib
import struct

DDR_JSON = pathlib.Path(__file__).with_name("ddr.json")


def _words(name: str) -> list[int]:
    return [int(v, 16) for v in json.loads(DDR_JSON.read_text(encoding="utf-8"))[name]]


def table_bytes(name: str) -> bytes:
    """'vtables' (program.voice_tables_words), 'qsin' (stage.qsin_words), 'pairs' (stage.pairs_words)"""
    ws = _words(name)
    return struct.pack(f"<{len(ws)}I", *(w & 0xFFFFFFFF for w in ws))
