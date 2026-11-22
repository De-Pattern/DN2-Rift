"""SMEAR's committed link tables (smear/ddr.json, what the numpy-free build sends) are what stage.py and
program.py compute, word for word; and the build reads them without numpy."""
import struct

from dnfw.smear import ddr
from dnfw.smear import program as SP
from dnfw.smear import stage as SG


def _b(ws):
    return b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in ws)


def test_the_committed_tables_are_the_programs():
    assert ddr.table_bytes("vtables") == _b(SP.voice_tables_words())
    assert ddr.table_bytes("qsin") == _b(SG.qsin_words())
    assert ddr.table_bytes("pairs") == _b(SG.pairs_words())


def test_the_loader_needs_no_numpy():
    src = (ddr.DDR_JSON.parent / "ddr.py").read_text()
    assert "numpy" not in src.split('"""', 2)[2]
