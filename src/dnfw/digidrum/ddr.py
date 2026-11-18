"""DIGIDRUM's DDR tables as the build ships them, read from the committed ddr.json (no numpy: the build
also runs in the browser patcher). dnfw.digidrum.program.write_ddr_json writes the file;
test_digidrum_program holds the two equal."""
from __future__ import annotations

import json
import pathlib
import struct

DDR_JSON = pathlib.Path(__file__).with_name("ddr.json")


def tables_bytes() -> bytes:
    words = [int(v, 16) for v in json.loads(DDR_JSON.read_text(encoding="utf-8"))["words"]]
    return struct.pack(f"<{len(words)}I", *words)
