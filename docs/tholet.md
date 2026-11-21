
## Transient storage (2026-11-18)

The image has ~36 KB to spare after DIGIDRUM. The six strikes are stored as 50 ms at 24 kHz,
8-bit μ-law: 1,200 bytes each, 7,200 bytes in all (int16 at 48 kHz would be 28.8 KB). Against
the 48 kHz originals, after μ-law and back up to 48 kHz, each measures 38 dB SNR (37.3–38.5 dB
over the set; 16 kHz drops BRITE to 31.9 dB, so 24 kHz it is). The DSP expands μ-law
with a 256-word table in L2 at power-on.
