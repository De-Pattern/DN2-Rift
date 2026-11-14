# RIFT firmware versions

Every RIFT build, newest first, with what it adds and what to test after flashing it.
Each build **contains everything before it**, so you only ever flash the newest one. All
builds are on stock Digitone II **OS 1.11**.

**Get it:** the **RIFT Patcher** (this repository's GitHub Pages site) builds the file in
your browser from your own Digitone II OS 1.11, Digitakt II OS 1.17 and Machinedrum UW OS 1.63 files (the
sample machines still read tables built from the Machinedrum's), and only lets
you save it when it is byte for byte the cleared file. The cleared files are also on the
**`builds`** branch, one folder per version (`vX.Y-NAME/`), each beside its gate record
(`.gate.json`). They are kept off `main` so the code branch never holds Elektron firmware.

**Only flash a file whose sha256 matches its gate record** (`CLEARED TO FLASH` from
`scripts/ship_gate.py`). The sha256 is listed below and in the `.gate.json` beside it. On
Windows: `certutil -hashfile FILE dc2b9f7c64c01d214df30dd600a99bc787a4ce16d4e54c40534cd346e2b05462`.

Every flash, every version:

1. **Back up the +Drive** with Elektron Transfer.
2. **Low volume.** Flash over USB as usual; keep the proven DIN recovery cable at hand.
3. Run the **regression check** (about 10 minutes, `docs/SAFETY.md`): boots with no
   `EXCEPTION`; one track each of FM Tone, FM Drum, WaveTone, Swarmer and a MIDI track all
   play as before; chorus, delay, reverb, master overdrive and compressor; pattern change,
   song mode, a p-lock, an LFO on a stock machine; SAVE PROJECT, power-cycle, reload.
4. Then the version's own tests, below. If anything is off: recovery to stock 1.11, then
   say what you saw.

| version | date | adds | download | gated |
|---|---|---|---|---|
| **v0.1** | 2026-11-13 | FASCIA (pass 3: 32 controls on four pages); the Machinedrum and Monomachine engines removed (their tracks open as FM Tone); the sample machines, +Drive library, recorder, Direct Jump and slides kept from the DN2 mk2 mod; stock start-up screen | `builds/v0.1-FASCIA/` | yes |

## v0.1 · FASCIA

- **File:** `RIFT_v0.1_FASCIA_OS1.11.syx` (`builds/v0.1-FASCIA/`)
- **sha256:** `dc2b9f7c64c01d214df30dd600a99bc787a4ce16d4e54c40534cd346e2b05462`
- **Gated:** 2026-11-13, `CLEARED TO FLASH`
- **Source:** `eeb191d` (this repository)

**Adds**

- **FASCIA** (MACHINE SEL), the physical and spectral percussion and tuned-body engine of
  the approved pass-3 tour: two exciters into two coupled modal bodies, thru-zero FM, ring
  and frequency shift, a spectral morph, formants, water, folding, drive and a low-pass gate.
  Pages SYN1 EXCITERS, SYN2 RESONATORS, SYN3 SPECTRAL, SYN4 ONSET/INTERACT.
- Every control p-lockable and slid; all but ATK, FDBK and VARY are LFO destinations.
- The Machinedrum (PERC) and Monomachine engines are gone. A DN2 mk2 sound or project with
  one of them opens that track as FM Tone, as stock opens any machine it lacks.
- Kept from the DN2 mk2 mod (v0.51): ONESHOT, WERP, STRETCH, REPITCH, GRID, SLICE, FLEX;
  the +Drive library and per-project pools; the recorder and FLEX REC; Direct Jump;
  parameter slides; ERASE MOD DATA.
- Stock start-up screen; "RIFT v0.1" at the top of the +Drive browser.

**Tests**

1. MACHINE SEL → FASCIA on a track: four pages, every knob, the choice boxes (TYPA, TYPB,
   BODA, BODB, CTYP, XMOD).
2. Play the audition patches' kinds of sound: glass, bells, bars, drums, bowed and blown,
   water. Listen for clicks at note starts and ends.
3. P-locks and slides on FASCIA's controls; an LFO on several of them (ATK, FDBK and VARY
   are not offered).
4. Chords and fast rolls on one FASCIA track: how many notes hold before one drops, and
   whether the drop is clean. Watch the DSP LOAD meter (FUNC held).
5. FASCIA beside sample tracks playing: the samples must never crackle.
6. SAVE PROJECT with FASCIA tracks, power-cycle, reload; a preset and a sound lock.
7. Load a DN2 mk2 project with a PERC or Monomachine track: the track is FM Tone, nothing
   else changes.
8. The sample machines and the recorder as on DN2 mk2 v0.51.

**Known issues**

- FASCIA is heavy on the DSP. On the emulator's memory clock about 3 voices of the heaviest
  patches (water, snare wires) fit at once, about 6 of a typical one and 8 of the lightest
  (kalimba). Past that the guard drops a FASCIA voice for that moment; sample voices get
  their time first. The unit's DSP LOAD meter gives the real numbers.
- OS 1.11 only.
