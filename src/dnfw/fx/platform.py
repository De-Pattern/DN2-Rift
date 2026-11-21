"""The insert platform's switch and its DSP layout (docs/fx-platform.md).

ON = False builds exactly what v0.1 shipped: ping.asm is the shared tail alone. ON = True puts
the insert loop in front of it: for each of the 16 voices, the voice's insert word (the table at
INSERT_DM, zeros at power-on) picks what runs on that voice's buffer before the stock filter.
Only a test effect exists yet (GAIN: the buffer times a float), so the platform is gated
before any sound is: off and zero, every voice's buffer is untouched, bit for bit.
"""
from __future__ import annotations

from ..waverider import dsp

ON = True

# 16 voices x 8 words, in the room PING's state had (dsp.PING_STATE_DM: past ping.asm's code,
# inside REGION, loaded as zeros: the tail's object is padded with zeros to REGION's end)
INSERT_DM = dsp.PING_STATE_DM                  # 0x2e1d00
INSERT_STRIDE = 32                             # bytes: [type, a, b, c, ...] a voice
INSERT_T_DM = INSERT_DM + 16 * INSERT_STRIDE   # the loop's voice counter (0x2e1f00)
VOICE_BUFS = 0x254A60                          # the voice buffers' pointers, 4 bytes a voice (PING's)
BLOCK_SIZE_DM = 0x2DDE24                       # the dispatch's R9, saved by PERC: samples a block

TYPES = {"OFF": 0, "GAIN": 1}                  # GAIN: a test effect, buffer *= word a (float32)
