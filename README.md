# RIFT firmware versions

Every RIFT build, newest first, with what it adds and what to test after flashing it.
Each build **contains everything before it**, so you only ever flash the newest one. All
builds are on stock Digitone II **OS 1.11**.

**Get it:** the **DN2 Mod Patcher**, its RIFT section, https://de-pattern.github.io/dn2mk2/patcher.html#rift (or this repository's own Pages site), builds the file in
your browser from your own Digitone II OS 1.11, Digitakt II OS 1.17 and Machinedrum UW OS 1.63 files (the
sample machines still read tables built from the Machinedrum's), and only lets
you save it when it is byte for byte the cleared file. The cleared files are also on the
**`builds`** branch, one folder per version (`vX.Y-NAME/`), each beside its gate record
(`.gate.json`). They are kept off `main` so the code branch never holds Elektron firmware.

**Only flash a file whose sha256 matches its gate record** (`CLEARED TO FLASH` from
`scripts/ship_gate.py`). The sha256 is listed below and in the `.gate.json` beside it. On
Windows: `certutil -hashfile FILE SHA256`.

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
| **v0.14** | 2026-11-21 | MONTUNE: FLEX takes of MAIN and IN +12 dB on playback, MON on the RECORDER, MICROTUNING (11 factory tunings, USER 1..8, per track, saved with the project) | `builds/v0.14-MONTUNE/` | yes |
| v0.13 | 2026-11-20 | PARITY with the DN2 mk2 mod: EDIT SLICE POINTS (live edits, played slice selected, zoom to 128 frames, zero-crossing snap), FUNC + E in CREATE SLICE GRID, ALLOCATE SLICE NO keeps RANDOM's locks, FLEX takes of a track +24 dB, a FLEX save never normalises | `builds/v0.13-PARITY/` | yes |
| v0.12 | 2026-11-20 | LIGATURE's PATCH screen: the wiring on page 1 as a grid with cables, EDIT on YES (block, type, inputs, amounts, output), the BLOCK view, knobs named by block; 128 wirings kept per project | `builds/v0.12-PATCHING/` | yes |
| v0.11 | 2026-11-19 | Held voices keep the DSP's time: a melody's or a re-struck note's tail is dropped before a held chord (dreamsaremaps) | `builds/v0.11-VOICEKEEP/` | yes |
| v0.10 | 2026-11-19 | DIGIDRUM, digital drums after the Syntakt's (BD Modern, SD Basic, SD Vintage, CP Vintage, CY Alloy, PC Carbon), TYPE p-lockable per trig, page 2 OVER / EQ / tremolo / base-width filter / LEV | `builds/v0.10-DIGIDRUM/` | yes |
| v0.9 | 2026-11-19 | LINE, the new screens on every RIFT machine (thin lines, a moving icon per control, values the Syntakt way, p-locks highlighted); LIGATURE in MACHINE SEL; RESONATOR removed; the manual (MANUAL on the patcher) | `builds/v0.9-LINE/` | yes |
| v0.8 | 2026-11-18 | RESONATOR returns (the DN2 mk2 mod's Rings-style modal resonator, as a RIFT machine: TUNE LEV STRC BRIT / DAMP POS EXCT HIT) | `builds/v0.8-RESONATOR/` | yes |
| v0.7 | 2026-11-18 | FLEX buffers B1..B8 in every sample machine's SAMP, MUTE SRC only while the FLEX track plays, the stock NAME screen for file names (from the DN2 mk2 mod's v0.54-v0.57); ORGAN: BLOM is the breath's attack; turned knobs show their value (a lock with its trig held) on RIFT's machines; the campfire start-up animation | `builds/v0.7-FLEXPOOL/` | yes |
| v0.6 | 2026-11-17 | SILT, RIFT's third machine (material synthesis: FIBER, SILT, SKIN, FLUID played by ten gestures, alone or as an ensemble); ORGAN: BLOM a slow swell (breath from EDGE), MTUN replaces PHRM, MCHR replaces VELO | `builds/v0.6-SILT/` | yes |
| v0.5 | 2026-11-17 | ORGAN pages 3 (ATTACK: PERC, PDEC, PHRM, KCLK, VELO, MIXT, ROTR, RSPD) and 4 (BREATH: BRTH, TURB, BREK, BDEP, PRES, BLOM, EDGE, PVEL), all off at 0; v0.4 organ sounds unchanged; CELESTE fades instead of switching | `builds/v0.5-BREATH/` | yes |
| v0.4 | 2026-11-16 | ORGAN, RIFT's second machine (Ravel's pipe organ: five stops, seven drawbar ranks, chiff, wind, tremulant, celeste); FASCIA starts as the demo vibraphone with CHAR 0; TRK + CLEAR keeps a machine's own defaults; FUNC + turn on GEOM and SHIFT snaps to 0 | `builds/v0.4-ORGAN/` | yes |
| v0.3 | 2026-11-14 | FLEX from the DN2 mk2 mod's v0.53 (MUTE SRC: the auto-mute; R.LEN at the pattern's scale; a voice plays its own locked BUF; R.LEN a bar a detent; PLAY two detents; INF trig length on a switch to FLEX); FASCIA starts at DAMP 28 and CHAR 127, and FUNC + turn moves its TUNE by octaves | `builds/v0.3-FLEX/` | yes |
| v0.1 | 2026-11-13 | FASCIA (pass 3: 32 controls on four pages); the Machinedrum and Monomachine engines removed (their tracks open as FM Tone); the sample machines, +Drive library, recorder, Direct Jump and slides kept from the DN2 mk2 mod; stock start-up screen | `builds/v0.1-FASCIA/` | yes |

## v0.14 · MONTUNE

- **File:** `RIFT_v0.14_MONTUNE_OS1.11.syx` (`builds/v0.14-MONTUNE/`)
- **sha256:** `d3b5728922eca19b7f39dd055e235dac0cef9bed2bb913a048ca04347bcb5d3a`
- **Gated:** 2026-11-21, `CLEARED TO FLASH`
- **Source:** `153423e` (this repository)

**Adds**

- **FLEX takes of MAIN and IN, +12 dB on playback** (the owner and Error Kit, 2026-11-20): the
  recorder marks a FLEX take's buffer half when its source is MAIN or IN (`MAIN_MARK`, bit 15 of
  the buffer directory's steps word); a voice on a marked half plays it `MAIN_PLAY_DB` (12) louder.
  The take is stored as recorded, never boosted into the clamp. TRK takes unchanged (TRK_HW_DB 24).
- **MON on the RECORDER** (the DN2 mk2 mod's v0.59, from dn2mk2-firmware 9682441, aee05a8):
  knob C; with SRC IN the input is heard while armed or recording (`rec.c`; pvmix and smp
  regenerated here).
- **MICROTUNING** (the mod's v0.61, a7fee88, 796f5d6, 8812fba): `tune.c` as is; KB SETUP's H is
  TUNE; TUNING and EDIT; a record per project at 0x6E0400..0x6E04FF (memory map updated).
  RIFT's machines read the frame's note word as note + fine / 256, so all of them are retuned;
  SLICE and GRID never.
- Gate: runner part `mainmark` (the mark for MAIN and IN only, a track's none; the frames the same
  either way; playback +12 dB sample for sample; a 0 dB negative control); `recorder`, `rectext`
  (MON), the runner's `pvmix` (MON's mix); `tune`, `tunerec`; unit tests `test_mon`, `test_tunings`.

**Known issues**

- A MAIN or IN FLEX buffer saved to a sample slot plays 12 dB quieter than the buffer did.
- ERASE MOD DATA does not clear the tunings yet (as in the mod).

**Tests**

1. FLEX from MAIN at GAIN 0: about the level heard, no distortion; from IN with the input up: the same.
2. FLEX from a track: unchanged.
3. RECORDER, SRC IN, C = MON ON: the input heard while armed and recording; MON in the corner.
4. KB SETUP's H: a tuning on the track; push: TUNING (ROOT, TRK, ALL); a USER tuning's EDIT.
5. SAVE, LOAD another, LOAD back, power-cycle: the tuning kept.

## v0.13 · PARITY

- **File:** `RIFT_v0.13_PARITY_OS1.11.syx` (`builds/v0.13-PARITY/`)
- **sha256:** `195fe44faa3c4abaeb26160a7ae6f844d0fd81abc1f559b9ec409774766fe092`
- **Gated:** 2026-11-20, `CLEARED TO FLASH`
- **Source:** `341cfc1` (this repository)

**Adds** (the DN2 mk2 mod's updates, ported as is from dn2mk2-firmware ff1ffe5, 6e8baa6,
e354e03, 40c2a91, 2a37c41, cd0779d, 754b31c, 53374d2, 1fd9d24; the generated SHARC and ColdFire
code regenerated here)

- **EDIT SLICE POINTS** (the mod's v0.62, impbox): edits play 0.2 s after the knobs rest (no YES);
  a played slice is selected; ZOOM to a 128-frame view drawn from the sample's own frames (read
  from the +Drive); FUNC + START / END snaps to the nearest zero crossing (`slice.c`, `link.c`).
- **CREATE SLICE GRID:** FUNC + E jumps SLICES 2 / 4 / 8 / 16 / 32 / 64 (Wolljamin; `slc_grid_jumps`).
- **GRID's ALLOCATE SLICE:** NO exits keeping RANDOM's locks, as the DT2 (the mod's v0.60, impbox).
- **FLEX level** (the mod's v0.63): a take of a track 24 dB louder (`TRK_HW_DB`, the owner's number:
  GAIN +24 made a take match its source by ear); GAIN 0 is what was +24.
- **FLEX save:** a FLEX buffer saved to a slot keeps its take as it lies, never normalised
  (`smp_save_keep`; `rec.c` `bn_save`).
- The page renderer's span grows to 0x3C000 (the MD graphics move to 0x46afc000).
- Gate: `slicefine` (new: live edits, zero crossings, deep zoom, a played slice, FUNC + E);
  `alloc` (NO keeps RANDOM's locks); `sharc:flexlevel` (GAIN -24 at the runner's unity, GAIN 0 the
  same take x 15.85 where unclipped, a 0 dB negative control); `link16` norm's fifth take (a FLEX
  save kept as it lies).

**Known issues**

- Playing the same note again on the same voice doesn't re-select its slice (a different note does).
- MAIN and IN FLEX takes unchanged (still quiet).

**Tests**

1. EDIT SLICE POINTS: move START, stop, play the key: the change is heard without YES.
2. Play the track: the editor selects the slice that plays.
3. ZOOM fully in: single cycles; FUNC + E / FUNC + H land on zero crossings.
4. CREATE SLICE GRID: FUNC + E steps 2 / 4 / 8 / 16 / 32 / 64; E alone one.
5. ALLOCATE SLICE, RANDOM, NO: RANDOM's locks stay.
6. FLEX of a track, GAIN 0: about the track's level. A boosted FLEX track: 24 dB hotter, GAIN 0 brings it back.
7. Save the FLEX buffer while it plays: no jump; the saved sample loads at the same level.

## v0.12 · PATCHING

- **File:** `RIFT_v0.12_PATCHING_OS1.11.syx` (`builds/v0.12-PATCHING/`)
- **sha256:** `aac214284b76d3568f1e14a38e24325aeac8a891841a22d2a3f8c0e11f569c5b`
- **Gated:** 2026-11-20, `CLEARED TO FLASH`
- **Source:** `2b0e9ec` (this repository)

**Adds**

- **LIGATURE's PATCH screen** (owner, 2026-11-19: "just fix the ligature ui so its usable ... we dont
  need presets"; `csrc/sampler/lig.c`, `smp_page.c`):
  - page 1: the wiring as WEFT's grid (tiles 1-9, A, B, C; cables in the gutters, a back-cord dotted)
    and the page's eight controls below in their knobs' places;
  - EDIT (YES): A BLK, B TYP, C INA, D AMA / E INB, F AMB, G MOV, H OUT; the arrows; FUNC + NO
    empties a block; YES the BLOCK view; NO leaves;
  - pages 2-4: each knob named by its block's type (`TYPE_SETS`).
- **The wirings, per project**: 128 (`dnfw.ligature.live` WSLOTS, 25 words each), PATCH 0..127
  picks one (shown 1..128). Kept in each project's list after the slice area (`pools.c` F_WIRE,
  L_WIRE; read on LOAD and at power-on; a NEW project's are the factory patches), sent by the
  sample link into the pool's WIRE area (`link.c` K_WIRE, the magic last; a slot as it is edited).
  Seeded with the factory patches, slot k the one PATCH k played before: a saved sound sounds the
  same.
- **The DSP** decodes the slot's wiring into the voice every block (`live.decode`, the contract:
  any word reads as a safe wiring); with no table there, the factory patch as before.
- Includes v0.11 (held voices keep the DSP's time).
- Gate: `ligedit` (new: EDIT, BLOCK, the edits in the table, the list asked for, the screens);
  `ligature` (page 1 the PATCH screen, its p-locks on page 2); `pools` W1..W6 (the wirings in the
  lists, the DSP, LOAD, NEW, a power cycle, power cuts); the runner's `ligature` part (the seeded
  table, random wirings and garbage, bit-exact on the assembled code); unit tests.

**Known issues**

- No MOVE (FUNC + BLK) yet: a block is rebuilt where you want it.
- The BLOCK view shows a block's settings as the wiring holds them, not with page 2-4's offsets.
- Not yet seen on hardware: the screens' legibility on the unit's display.

**Tests**

1. A LIGATURE track, page 1: the grid; PATCH changes it.
2. YES: B, C-F and H edit the block; the sound follows at once.
3. YES on a block: BLOCK; YES back; FUNC + NO empties it; NO leaves.
4. SAVE, LOAD another project, LOAD back, power-cycle: the wiring is kept.
5. A NEW project: the factory patches.
6. Pages 2-4: names follow the blocks.

## v0.11 · VOICEKEEP

- **File:** `RIFT_v0.11_VOICEKEEP_OS1.11.syx` (`builds/v0.11-VOICEKEEP/`)
- **sha256:** `e0e477dcd82356a01681de3485b15a61a04cd1e70663b94822bbe27c3e206165`
- **Gated:** 2026-11-19, `CLEARED TO FLASH`
- **Source:** `5807099` (this repository)

**Adds**

- **Held voices keep the DSP's time** (dreamsaremaps, Discord 2026-11-19). The frame guard
  renders our voices in ORDER and leaves out, then steals, the ones that do not fit. ORDER was
  newest first (v0.29), so a melody over a held chord, or a REUSE re-strike, took the time and the
  held notes were stolen. Now each slot's note-off (the frame's mask 36) marks it released until its
  next note, and ORDER puts every released voice after every held one, newest first within each
  (`src/dnfw/perc/program.py`: RELS_OFF, SORTS_OFF, RELEASED_BIAS).
- SHARC runner part `fkeep` (gate group `sharc:fkeep`): two held FASCIA notes under a melody, the
  clock made to move so about three voices fit: the held notes sound to the end (on v0.10 both die
  within four blocks); three held with one re-struck over and over.

**Known issues**

- More notes held at once than the DSP can run: the newest still win.
- The REUSE report itself was not reproduced at the emulator's CPU level; its case is in `fkeep`.

**Tests**

1. A busy FASCIA or SILT track: hold a two-note chord, play a melody over it: the chord keeps sounding.
2. Hold a chord, re-strike one of its notes several times (REUSE): the others keep sounding.
3. Every RIFT machine plays as before.

## v0.10 · DIGIDRUM

- **File:** `RIFT_v0.10_DIGIDRUM_OS1.11.syx` (`builds/v0.10-DIGIDRUM/`)
- **sha256:** `783eafd2c4ea8f89cdbca9aa4a54316d84513ce31b369ef100f23160632dba52`
- **Gated:** 2026-11-19, `CLEARED TO FLASH`
- **Source:** `c81ef3a` (this repository)

**Adds**

- **DIGIDRUM** (type 22, where RESONATOR was), in MACHINE SEL after LIGATURE: six digital drum
  voices after the Syntakt's, BD Modern, SD Basic, SD Vintage, CP Vintage, CY Alloy, PC Carbon
  (`src/dnfw/digidrum/`: `model.py` the design, `live.py` the float32 contract, `program.py` the
  DSP program in FASCIA's walk, bit-exact to `live.Voice` for all six types).
  - Page 1 DRUM: TYPE (a choice, p-lockable per trig), TUNE, PNCH, DEC, and O1..O4, named and
    used by the TYPE (`dgd_own`, `smp_page.c` relabels them as TYPE turns).
  - Page 2 TONE: OVER, EQF, EQG (a peaking EQ), AMD, AMF (a tremolo), FLTF, FLTW (a base/width
    filter), LEV.
  - On the LINE pages, its formatters in `fmt.c`, its slides, its DDR records.
- `scripts/ship_gate.py`: the unit step runs `test/test_digidrum_program.py`; step `digidrum`
  (MACHINE SEL, the page, p-locks, LFO names, TRK + CLEAR on the ColdFire); the SHARC runner's
  `digidrum` (bit-exact to the live model) and `dstress` (every slot on DIGIDRUM at once).

**Known issues**

- A v0.8 RESONATOR track never re-saved in v0.9 opens as DIGIDRUM, with its old values read as
  DIGIDRUM's.
- The voices are matched to the Syntakt by ear, not yet by measurement against recordings.
- The CPU-limit voice drop (newest first) can take held notes on a busy track: see the
  dreamsaremaps report in the work queue; not changed in this version.

**Tests**

1. MACHINE SEL: DIGIDRUM after LIGATURE; each TYPE plays.
2. P-lock TYPE on several trigs: each trig plays its own voice.
3. Turn TYPE: page 1's last four labels follow it.
4. Page 2: OVER, EQ, tremolo, filter and LEV each act.
5. With other tracks running: no new clicks or dropouts.
6. The other machines: unchanged from v0.9 (the gate's SHARC parts hold them bit for bit).

## v0.9 · LINE

- **File:** `RIFT_v0.9_LINE_OS1.11.syx` (`builds/v0.9-LINE/`)
- **sha256:** `7dd50b8d21cbf187e44a975d44fcaaab2f4740559e2a434ddf74acf0c7be9e1d`
- **Gated:** 2026-11-19, `CLEARED TO FLASH`
- **Source:** `9005794` (this repository)

**Adds**

- **LIGATURE listed** in MACHINE SEL (`LISTED = True`, `src/dnfw/ligature/machines.py`).
- **RESONATOR removed** (owner, 2026-11-18; 75210b9 and 3d4e6b1 reverted). A v0.8 RESONATOR track loads as FM Tone, as any type RIFT lacks.
- **The manual:** `rift-manual.html`, behind the MANUAL button on the patcher's RIFT version row.

- **LINE**, the new page style for RIFT's machines: FASCIA, ORGAN, SILT and LIGATURE. It is drawn by `fsc_page_draw` in
  `csrc/sampler/smp_page.c`; the glyphs are listed in `pages.py` (`LINE_GLYPHS`, each machine's
  `lglyph`).
  - Two rows of four cells in the knobs' layout. Each cell is a 17 x 12 glyph that moves with
    its value, and its label under it.
  - Choices are drawn as boxes with the word inside, scrolling when the choice changes.
  - No side panel, and the stock SYN box is not drawn under it. The page dots stay.
  - Values show the Syntakt way: while a knob turns, while SYN is held, or while a trig is
    held. A p-locked cell is drawn inverted while its trig is held, with its locked value.
- `scripts/ship_gate.py`: the five machine UI steps read the new cells.

**Known issues**

- Not yet seen on hardware: the new screens' timing and legibility on the unit's display.

**Tests**

1. Every RIFT machine's pages: nothing overlaps, nothing is clipped, the track number is clean.
2. Turn each knob: its glyph moves and its value shows, then hides.
3. Hold SYN: every value shows.
4. P-lock controls, then hold that trig: the locked cells are inverted, with their values.
5. A choice control (FASCIA's modes, SILT's): the box scrolls to the new word.
6. LIGATURE from MACHINE SEL: plays, its pages draw, its p-locks hold.
7. Sound: unchanged from v0.8 (the gate's SHARC parts hold every engine bit for bit).

## v0.8 · RESONATOR

- **File:** `RIFT_v0.8_RESONATOR_OS1.11.syx` (`builds/v0.8-RESONATOR/`)
- **sha256:** `9965a3533162719d2e78f9592919efe582d053d926496c171286e5cebfc7e420`
- **Gated:** 2026-11-18, `CLEARED TO FLASH`
- **Source:** `4ea8dfd` (this repository)

**Adds**

- **RESONATOR** (MACHINE SEL: "Resonator" / "RES", type 22): the Rings-style modal resonator from
  the DN2 mk2 mod's early versions (v0.6-v0.25, `docs/rings.md` there), rebuilt as a RIFT machine
  in FASCIA's walk. 24 two-pole modes a voice, struck by a mallet blended with a noise burst.
  - One page: **TUNE** (semitones, -64..+63), **LEV**, **STRC** (0 a string's harmonic series,
    the middle a free bar, the top a plate or bell), **BRIT** (the mallet's width and how fast
    high modes die), **DAMP** (0.1 to 12 s), **POS** (where it is struck), **EXCT** (mallet to
    noise), **HIT** (how hard).
  - Every control p-locks, slides and is an LFO destination; turning a knob shows its value.
  - Each note latches its pitch at the trig; the modes keep ringing through a retrigger. A voice
    that has rung out costs nothing. When time runs short, the newest notes are kept.
- `src/dnfw/reson`: live.py (the sound), program.py (the DSP, bit for bit to live), machines.py.

**Known issues**

- Its screen is the standard RIFT page for now; the new LINE screen style comes later.
- Not yet tested on hardware: RESONATOR's sound and DSP load on the unit.

**Tests**

1. MACHINE SEL: Resonator after Silt. A note rings at its pitch; TUNE moves it in semitones.
2. STRC from 0 to 127: string, then marimba bar, then bell.
3. DAMP short and long; BRIT dark and bright; EXCT to noise.
4. Chords of four on one track; several RESONATOR tracks at once: listen for dropouts.
5. P-lock STRC and DAMP on single trigs; an LFO on POS; a slide on TUNE.
6. SAVE PROJECT, power-cycle, reload with RESONATOR tracks.

## v0.7 · FLEXPOOL

- **File:** `RIFT_v0.7_FLEXPOOL_OS1.11.syx` (`builds/v0.7-FLEXPOOL/`)
- **sha256:** `320a8cce74f91135b2bc7c02828593ee1d6e636d0f1ec63b87a92ebf0ed83143`
- **Gated:** 2026-11-18, `CLEARED TO FLASH`
- **Source:** `23cbc87` (this repository)

**Adds**

- **FLEX from the DN2 mk2 mod** (dn2mk2-firmware `3f314b4`..`5414008`, its v0.54 to v0.57; not
  DDRW, the Monomachine's):
  - the eight FLEX buffers in every sample machine's SAMP, past 127 as B1..B8: knob, list and
    p-locks; a track on Bn plays that buffer's playing take (`docs/flex-pool.md`);
  - MUTE SRC mutes the source only while the FLEX track plays; the REC 1/REC 2 names are gone;
    the F bank letter for buffers;
  - FILE NAME, RENAME and CREATE FOLDER on the Digitone's own NAME screen (`docs/name-screen.md`).
- **Values on RIFT's machines** (owner, 2026-11-17): FASCIA's, ORGAN's, SILT's (and LIGATURE's)
  pages show a just-turned knob's value in its label's place for a second, its lock with a trig
  held, as stock and the sample machines do (v0.48's rule; before, only with SYN held).
- **ORGAN:** BLOM is the breath's attack (Error Kit): it scales the breath and its edge noise,
  not the voice.
- **Start-up:** the campfire animation (80 frames; robots drumming, the camera to the sky, the
  smoke spells RIFT), the RIFT version over its last frame.
- **LIGATURE** (type 21) is in the build, engine and gate steps, but held from MACHINE SEL until
  its block-and-cable screens exist (owner, 2026-11-17).

**Known issues**

- Not yet tested on hardware: the FLEX buffer rows and the NAME screen on RIFT, the new
  start-up animation's timing on the unit.

**Tests**

1. Record a FLEX take; a ONESHOT track's SAMP past 127 to B1 plays it; the list shows FLEX BUF 1.
2. An empty buffer (FLEX EMPTY n) plays nothing.
3. SAMP p-locked to B2 on one trig.
4. MUTE SRC: the source is muted only while the FLEX track plays.
5. Sample RENAME and CREATE FOLDER open the stock NAME screen; YES keeps, NO aborts.
6. ORGAN, BLOM up: the breath swells in, the tone is not delayed.
7. A p-locked trig held on FASCIA, ORGAN and SILT, a knob turned: its cell shows the lock.
8. Power on: the campfire animation, then RIFT 0.7 on the last frame; boot completes.
9. MACHINE SEL lists Fascia, Organ, Silt (no Ligature).

## v0.6 · SILT

- **File:** `RIFT_v0.6_SILT_OS1.11.syx` (`builds/v0.6-SILT/`)
- **sha256:** `597242a434ea3c1d36719cecfe9b74a9f980e321735cce5614ff9230f4a2e531`
- **Gated:** 2026-11-17, `CLEARED TO FLASH`
- **Source:** `883af79` (this repository)

**Adds**

- **SILT**, RIFT's third machine (MACHINE SEL: "Silt" / "SLT", after ORGAN): material
  synthesis. A material (FIBER, SILT, SKIN, FLUID) played by a gesture (BOW, SCRAPE, STACC,
  TREMO, SPICC, LEGNO, GLISS, FRACT, SWELL, QUAKE), alone or as an ensemble (SOLO, MASS,
  MASS-8, SWARM). Four pages: MATTER, CONTACT, STRUCTURE and CONFIG.
  - Velocity strikes harder and bows faster; in MASS it also sets how many players join. The
    gate length is how long the gesture is held. LOOP re-starts it while the gate is open.
  - Page 4 (CONFIG) is chosen per trig and can be p-locked. Every page 1 to 3 control
    p-locks, slides and is an LFO destination; SHAPE, TUNE and QUAL are not LFO destinations.
  - SILT is the heaviest engine. QUAL sets its DSP cost (ECO, NORMAL, DEEP). When time runs
    short, the newest notes are kept and older voices are left out, as on FASCIA and ORGAN.
- **ORGAN** (Error Kit's requests on Discord):
  - **BLOM** opens the pipe slowly into the note (30 ms to 3 s); the breath you hear as it
    opens is EDGE's, so EDGE at 0 gives a clean swell for drones.
  - **MTUN** (Mixture Tune) replaces PHRM: it tunes the mixture down, 0 to 36 semitones.
    PERC stays on the 2nd harmonic.
  - **MCHR** (Mixture Character) replaces VELO: the mixture's pipe morphs toward a trumpet
    (toward a flute when the stop is TRUMPET), from glassy to buzzy. The organ plays at one
    level; PVEL still puts velocity on the pressure.

**Known issues**

- v0.5 ORGAN sounds with MIXT up sound different: their old PHRM value reads as MTUN (2ND as
  about 9 semitones down, 3RD as about 27) and VELO as MCHR. Set MTUN and MCHR to 0 to get
  the plain mixture back. v0.5 sounds that used BLOM have less breath unless EDGE is up.
- SILT's materials are not yet level-matched: FIBER plays about twice as loud as the others.
- Not yet tested on hardware: SILT's sound and DSP load on the unit, 16 SILT voices at once.

**Tests**

1. MACHINE SEL: Silt after Organ. The init sound: a bowed string, in tune; hold notes of
   different lengths (the gate is the bow).
2. MAT through FIBER, SILT, SKIN, FLUID; GEST through all ten; MODE SOLO, MASS, MASS-8, SWARM.
3. Velocity soft and hard in MASS (fewer and more players).
4. LOOP 16TH and FREE on a long gate; p-lock MAT and GEST on single trigs.
5. An LFO on PRESS and on MORPH; a slide on GLISS.
6. 8 SILT tracks at QUAL DEEP playing chords: listen for dropouts and watch the CPU flag;
   then ECO.
7. ORGAN: BLOM high, EDGE 0 on a long note (a clean swell); EDGE up (breath as it opens).
8. ORGAN: MIXT up, then MTUN through its range and MCHR from 0 to 127.
9. A v0.5 ORGAN project: it loads; sounds without MIXT sound as before.
10. SAVE PROJECT, power-cycle, reload with SILT tracks: they come back.

## v0.5 · BREATH

- **File:** `RIFT_v0.5_BREATH_OS1.11.syx` (`builds/v0.5-BREATH/`)
- **sha256:** `5798c52ff588e3f557c9c99e89a625b8a4784e7304f8401f92107b6d528e26ea`
- **Gated:** 2026-11-17, `CLEARED TO FLASH`
- **Source:** `41ca2ab` (this repository)

**Adds**

- **ORGAN: two new pages.** Everything on them starts at 0, and at 0 the organ is v0.4's,
  sample for sample (the owner: "do not change the core sounds").
  - **SYN3 ATTACK:** PERC (a Hammond-style percussion: a clean sine ping at each note), PDEC
    (its decay, a tick to a bell), PHRM (the ping on the 2ND or 3RD harmonic), KCLK (key click:
    a short contact click), VELO (velocity sensitivity: harder notes louder, with a stronger
    ping and click), MIXT (a mixture: high pipes above the stop, shimmer), ROTR and RSPD (a
    rotor: the level and tone swirl and the pipes waver, the speed easing between settings).
  - **SYN4 BREATH** (from the owner's flute clip): BRTH (the air's turbulence inside the tone:
    level, pitch and brightness flutter from within), TURB (how fast: a slow waver to a 50 Hz
    rasp), BREK and BDEP (a voice-like break: the tone cracks down into a rough half-pitch
    growl and recovers), PRES (blowing pressure: sharper, likelier to break), BLOM (each note
    blooms from breath into tone, up to 3 s), EDGE (breath heard through the pipe), PVEL
    (velocity on the pressure).
  - Every new control is p-lockable and slides; all but BLOM, EDGE and PVEL are LFO
    destinations (their records take no modulation).
  - **Organ sounds made in v0.4 sound exactly as before.** Their pages 3 and 4 show leftover
    numbers (64s) and stay off; the first turn of any knob on those pages sets both pages to
    their defaults (all off) and moves the turned knob from there.
- **CELESTE** fades its rank in and out instead of switching it (a tester: a click turning CELST
  from 0 to 2 and back).
- **The tremulant's sine** is now computed exactly as the model: past three quarters of each
  cycle v0.4's DSP was off by up to 0.01 % (inaudible; found by a longer test).

**Tests**

1. An ORGAN sound from v0.4: it sounds as before. SYN3 and SYN4 show numbers; turn PERC: the
   ping starts from the bottom and every other page 3 and 4 control reads its default.
2. A new ORGAN track: SYN3 and SYN4 at their defaults (PERC, KCLK, MIXT, ROTR, BRTH, BREK,
   PRES, BLOM, EDGE at 0): the organ as in v0.4.
3. PERC up on fast notes: the ping; PDEC short to long; PHRM 2ND and 3RD.
4. KCLK on fast notes; VELO up and play soft and hard.
5. MIXT up; ROTR up, RSPD slow then fast (the speed eases over).
6. BRTH up, TURB slow to fast; BREK and BDEP up (the breaks), PRES up (more of them).
7. BLOM up on long notes (breath into tone); EDGE up.
8. CELST from 0 to 2 and back on a held note: no click.
9. SAVE PROJECT, power-cycle, reload with pages 3 and 4 set: they come back.
10. v0.4's tests, if v0.4 was never flashed.

**Known issues**

- ORGAN's presets are still not shipped as sounds (docs/organ.md).

## v0.4 · ORGAN

- **File:** `RIFT_v0.4_ORGAN_OS1.11.syx` (`builds/v0.4-ORGAN/`)
- **sha256:** `eaf9b205dc629cde303ae8a3c155e5a3b3e43995addfc9f9e1590221b3b1376a`
- **Gated:** 2026-11-16, `CLEARED TO FLASH`
- **Source:** `f6bb341` (this repository)

**Adds**

- **ORGAN** (MACHINE SEL, after FASCIA), RIFT's second original machine: the pipe organ of the
  owner's Ravel firmware for the M-VAVE FM-1, the same engine at 48 kHz (its samples equal Ravel's
  own C to within the SHARC's divide, far below hearing). Five stops (FLUTE, NACHTHORN, PRINCIPAL,
  GAMBA, TRUMPET), each a set of pipe tables that change with pitch as real ranks do; seven
  drawbar ranks; the pipes' speech, chiff, wind and air; a tremulant and a celeste.
  - **SYN1 RANKS:** STOP; 16FT, 8FT, 4FT, NAZ (the Nazard, 2 2/3 ft), 2FT, TIER (the Tierce,
    1 3/5 ft), 1FT: each rank's level.
  - **SYN2 PIPES:** CHIFF (the pipe's breathy onset), SPCH (speech: how slowly the pipes speak,
    the lower ranks slower), SPRD (spread: the ranks speak one after another), AIR (wind noise
    in the pipes), WIND (an unsteady wind: pitch and level), TREM and RATE (the tremulant),
    CELST (a celeste rank beside the 8', detuned up).
  - It starts at Ravel's own sound: NACHTHORN, 8FT 110, 4FT 70, 2FT 40, CHIFF 40, SPCH 50,
    SPRD 40, AIR 25, WIND 30, RATE 60.
  - Every control is p-lockable, an LFO destination and slides (STOP steps, as a choice).
  - An organ plays until the next note on its track, as the Monomachine's machines did: the
    DN2's AMP envelope shapes what is heard (set a release).
  - ORGAN runs in FASCIA's program, under the same DSP-time guard; it costs much less than a
    FASCIA voice.
- **FASCIA fixes** (owner, 2026-11-15):
  - A new FASCIA track starts as the demo vibraphone (STRIKE into a VIBE bar over a TUBE) with
    CHAR 0 again: CHAR 127 drove every sound hard into its saturator.
  - **TRK + CLEAR** on a FASCIA or ORGAN track now restores that machine's own defaults (it used
    to reload stock's record defaults: HARD 100, DUST 64, TUNE +36, DAMP 127 and so on).
  - **FUNC + turn on GEOM and SHIFT** (centre-zero knobs): toward the middle lands on 0, from 0
    on the end that way.

**Tests**

1. MACHINE SEL -> ORGAN on an empty track (after FASCIA in the list): SYN1 shows STOP NACH and
   the ranks; a held note sounds an organ at once.
2. Each STOP (FUNC + turn: one a click); each rank alone; the 16FT rank on a low note.
3. SYN2: CHIFF and SPCH on fast notes; SPRD high (the ranks enter one by one); TREM with RATE;
   CELST against the 8FT.
4. A chord over four tracks or a fast arpeggio (the steal: no click on a retrigger).
5. P-locks and an LFO on 8FT and on CELST; a slide.
6. Switch a sounding track between FASCIA and ORGAN: each starts clean at its next note.
7. SAVE PROJECT, power-cycle, reload: the organ track comes back the same.
8. FASCIA from MACHINE SEL: the vibraphone, CHAR 0. Turn a few knobs, then TRK + CLEAR: the
   vibraphone's values come back (not HARD 100 / DUST 64 / TUNE +36).
9. FUNC + turn on GEOM and on SHIFT from either side: it stops at 0; again from 0: the end.
10. v0.3's tests, if v0.3 was never flashed.

**Known issues**

- As v0.3. FASCIA with BEND up and DAMP near 0 can sustain on some hits and decay short on
  others, and now and then a voice cuts out (the owner's report, 2026-11-15): BEND's glide can
  feed a long-ringing body. Lower BEND (10 or less) or raise DAMP until the fix lands.
- ORGAN's presets (Ravel's INFINITE, PLENUM, VOX CELESTE, FLUTE 4', TROMPETTE) are
  not shipped as sounds yet: their settings are in docs/organ.md.

## v0.3 · FLEX

- **File:** `RIFT_v0.3_FLEX_OS1.11.syx` (`builds/v0.3-FLEX/`)
- **sha256:** `187972b3ea31849ac9eacb68674d7cad2e579589eb0898501d55c32f8f110a6c`
- **Gated:** 2026-11-14, `CLEARED TO FLASH`
- **Source:** `f366203` (this repository)

(v0.2, FASCIA's DAMP alone, was folded into this one before it was published.)

**Adds**

- **FLEX as the DN2 mk2 mod's v0.53 has it** (RIFT v0.1 had v0.51's):
  - **MUTE SRC** (REC SETUP): the SRC track leaves the mix while FLEX REC records it (its
    LEVEL and FX sends faded to 0 in the frame), and comes back when MUTE SRC is off.
  - The **RECORDER's R.LEN** counts steps at the pattern's scale (R.LEN 64 stops after 64).
  - A **FLEX voice plays the buffer its own BUF names**, the step's lock applied (a BUF lock on
    a playback trig was ignored); FLEX REC still records into the track's BUF.
  - FUNC + turn moves FLEX REC's **R.LEN a bar** (16 steps) a detent.
  - **PLAY**: two detents a choice (was four).
  - A switch to FLEX sets the track's **trig length to INF** (hear the whole take).
  - FLEX's **BUF** knob holds one value a buffer (four detents a buffer); a locked BUF keeps its
    number in the label's place while highlighted.
  - FLEX REC lights the page LEDs from its own page.
- **FASCIA's DAMP** starts at **28** when FASCIA is chosen on a track (was 60): the bodies ring
  about four times longer (T60 about 3.2 s against 0.7 s). Saved sounds keep their own DAMP.
- **FASCIA's CHAR** starts at **127** (was 0: hardly heard otherwise). Only the panel's start:
  the audition patches sound as before.
- **FASCIA's TUNE with FUNC + turn jumps by octaves**, as fw1's tunes do: 0, 32, 64, 96, 127
  (-2, -1, 0, +1, +2 octaves), to the next one the knob's way. Without FUNC it moves as before.

**Tests**

1. FLEX REC with MUTE SRC on: the source track is silent in the mix but recorded; MUTE SRC off,
   it is back.
2. RECORDER, R.LEN 64 at a 2x pattern scale: it stops after 64 steps.
3. FLEX: lock BUF on a playback trig to another buffer: that trig plays the locked buffer.
4. FUNC + R.LEN: a bar a detent. PLAY: two detents a choice.
5. Switch a track to FLEX: its trig length reads INF.
6. MACHINE SEL -> FASCIA on an empty track: SYN2's DAMP reads 28, SYN3's CHAR 127, and a hit
   rings long.
7. FASCIA's TUNE (SYN2), FUNC held: each click lands on the next octave (0, 32, 64, 96, 127);
   without FUNC it turns smoothly.
8. v0.1's tests, if v0.1 was never flashed.

**Known issues**

- As v0.1. FLEX's v0.53 behaviour is the mod's, gated here on RIFT's build; the mod's own
  known issues for v0.53 apply.

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
