"""The review of v0.30: rec.c rec_poll's overview fill (csrc/sampler/rec.c:760-780), ported line for line, run
over a take's reports. A report is (frames recorded so far, the recorder's peak 0..32767).

    python3 docs/qa/v0.30/overview_fill.py
"""


def fill(o, rec_frames, rec_peak, total):
    fr = rec_frames if rec_frames < total else total - 1
    col = fr * 100 // total
    v = (rec_peak >> 7) & 0xFF
    if not v and rec_peak:
        v = 1
    c0 = col
    while c0 > 0 and not o[c0 - 1]:
        c0 -= 1
    for c in range(c0, min(col, 99) + 1):
        if v > o[c]:
            o[c] = v


def take(peaks, total=96000, every=1920):
    """PEAKS(frame) -> the peak reported at that frame; a report every EVERY frames (25 a second at 48 kHz)"""
    o = [0] * 100
    for f in range(0, total, every):
        fill(o, f, peaks(f), total)
    return o


def show(name, o):
    print(f"{name}\n  " + " ".join(f"{x:3d}" for x in o[:50]) + "\n  " + " ".join(f"{x:3d}" for x in o[50:]))


if __name__ == "__main__":
    # a two-second take: digital silence for the first half, then one sound at about -6 dB
    show("silence for a second, then a sound (peak 16000) for a second",
         take(lambda f: 0 if f < 48000 else 16000))
    # a hit, silence, a hit: the gap
    show("a hit (0..0.2 s), silence, a quieter hit at 1.5 s",
         take(lambda f: 20000 if f < 9600 else 6000 if f >= 72000 else 0))
    # the control: sound all the way
    show("control: a steady sound", take(lambda f: 12000))
