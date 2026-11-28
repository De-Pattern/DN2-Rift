"""RIFT v0.28 (the owner, 2026-11-26): RUBBER (filter 6, dnfw.glass) is pulled. The image keeps the stock's
FLTR list, names, LOAD bound and slot_to_id, so a saved filter 6 loads as Multi-Mode; no GLASS code on the DSP."""

import json
import pathlib

import pytest

from dnfw.glass import coldfire as P

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "src/dnfw/mods/waverider_code.json").read_text())

pytestmark = pytest.mark.skipif(P.ON, reason="RUBBER is in the build")


def test_no_glass_chunk_or_layout():
    assert "glass_chunk" not in SPEC
    assert not [k for k in SPEC["layout"] if k.startswith("glass_")]   # (v0.29: page.c's RUBBER code out too)


def test_stock_sites_untouched():
    sites = [P.LIST_ALLOC, P.LIST_END, P.LIST_CAP, P.LIST_BEGIN, P.LOAD_BOUND, P.SLOT_SITE, P.GRAPH_SITE, P.OVER_SITE] \
        + [s[0] for s in P.NAME_SITES]                 # (QA's review of v0.28, C4: the curve's and the descriptor's too)
    for e in SPEC["edits"]:
        n = len(e["new"]) // 2
        assert not any(e["va"] <= va < e["va"] + n for va in sites), hex(e["va"])


def test_no_glass_on_the_dsp():
    asm = (ROOT / "csrc/waverider/sharc/fascia.asm").read_text()
    assert "wr_fs_rt_g_slot" not in asm and "wr_fs_rt_g_bend" not in asm
