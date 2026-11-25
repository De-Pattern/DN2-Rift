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
| **v0.24** | 2026-11-25 | RUBBER (an SH-101-style ladder) in GLASS's place, its curves as FLTR page 2 knobs; SMEAR: pitch and speed apart; clean knob icons | `builds/v0.24-APART/` | yes |
| v0.23 | 2026-11-24 | FASCIA's crackle (the guard's budget for RIFT's synths: x 1.25, the reserve kept); CPU on RIFT's machine pages when the DSP drops a voice; CONTOUR's crosshair logo; the quick guide | `builds/v0.23-STEADY/` | yes |
| v0.22 | 2026-11-24 | GLASS's overload fixed (the same sound at well under two thirds of the DSP time, inside the guard's budget); SMEAR: TUNE moves PLAY, FRZ (Freeze), page 2 redrawn; CONTOUR's own logo; the manual brought up to date | `builds/v0.22-FROST/` | yes |
| v0.21 | 2026-11-23 | The master reverb is a plate (Dattorro's tank in stereo behind the stock REVERB page); the new start-up logo (RIFT in block letters that drip and decompose); PLATEAU withdrawn for rework; FLEX levels from the DN2 mk2 mod's v0.71 | `builds/v0.21-PLATE/` | yes |
| v0.20 | 2026-11-23 | SLEN NXT (a slide lasts until the next trig, from the DN2 mk2 mod); CONTOUR: FDBK rescaled, FDBK and FM in key on high notes | `builds/v0.20-NXT/` | yes |
| v0.19 | 2026-11-22 | CONTOUR, a wave-terrain synth (8 surfaces, 2 pages); RIFT's machine pages at stock's size; SMEAR's page 2 shows the sample, its read point and a grain cloud | `builds/v0.19-CONTOUR/` | yes |
| v0.18 | 2026-11-22 | The silent-unit fix (SMEAR's VOC off, the guard expects a voice's peak, an output guard on every RIFT machine); PLATEAU no longer dropped beside other tracks; GLASS, a VCFQ-style filter on every machine; MACHINE SEL: PLATEAU's own section, SMEAR first of the samples, their logos | `builds/v0.18-GLASS/` | yes |
| v0.17 | 2026-11-21 | PLATEAU, RIFT's first FX machine: a Dattorro plate reverb on a track, fed by a BUS of chosen tracks (FUNC + VOICE picks them); BUS for FLEX (SRC BUS, REC BUS); THOLET removed; DIGIDRUM's new logo | `builds/v0.17-PLATEAU/` | yes |
| v0.16 | 2026-11-21 | SMEAR, a Nebulae-style looper (VOC, PLAY and GRN readers of one loop, BLND between them); LIGATURE's eight new blocks (TICK, ENV, VCA, CDIV, DUST, CHAOS, CRUSH, LISSA); MACHINE SEL logos for RIFT's machines | `builds/v0.16-SMEAR/` | yes |
| v0.15 | 2026-11-21 | THOLET, a piano leaning toward a Rhodes with a grain cloud (Error Kit's concept); KEYBOARD HOLD (PTN + KEYBOARD) from the DN2 mk2 mod | `builds/v0.15-THOLET/` | yes |
| v0.14 | 2026-11-21 | MONTUNE: FLEX takes of MAIN and IN +12 dB on playback, MON on the RECORDER, MICROTUNING (11 factory tunings, USER 1..8, per track, saved with the project) | `builds/v0.14-MONTUNE/` | yes |
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

## v0.24 · APART

- **File:** `RIFT_v0.24_APART_OS1.11.syx` (`builds/v0.24-APART/`)
- **sha256:** `8debdc360d978560ae7004d6aba232cb683ce9c9c88491ea9822136a28dffafc`
- **Gated:** 2026-11-25T02:23, `CLEARED TO FLASH`
- **Source:** `61248f5` (this repository)

**Changes**

- **RUBBER in GLASS's place** (owner, 2026-11-24: "replace glass with a RUBBER roland sh-101 style filter ... mono basslines sound liquid and rubbery"): the FLTR type 6. A four-pole low-pass after the SH-101's IR3109: four one-pole TPT stages solved with zero-delay feedback, Pade's tanh (DIGIDRUM's `sat`) at the input and in the resonance loop, part of the resonance's bass loss made up at the input, the stages' coefficient ramped across each block. RES to self-oscillation (K_MAX 4.4); TYPE's record is DRIVE (1..4); ATK/DEC and their bends as GLASS's; no LPG. `glass.program.samples_fast`: the 32 samples in registers, bit-exact to `sample()` and to `live.Voice` (about 3,200 cycles a slot a block on the unit's model; GLASS's was 4,200).
- **RUBBER's FLTR pages** (owner: the curves "should be knobs on the second page ... make it so they don't move sustain and release"): while the active track's filter is RUBBER, `rubber_cells` (page.c) blanks SUS and REL on page 1 (Multi-Mode's descriptor row, which filter 6 reads) and puts them on page 2's two empty places (ABND, DBND), Env. Delay's place blank; the stock rows come back on any other filter. The two are drawn as knobs (`rub_knob`). The flexcore gate step checks the rows both ways.
- **SMEAR: pitch and speed apart** (owner: "the point of nebulae is that it decouples pitch from speed"): PLAY's read point moves at SPD x the sample's rate; TUNE and the note set the pitch only, through two read heads at the pitch ratio crossfaded with triangles half a cycle apart (HEAD_LEN 2048). With no transposition at speed 1 PLAY is v0.21's plain read, bit for bit.
- **Knob icons** (owner: the ring "meant to resemble more skeuomorphic shadows ... make it much cleaner"): LG_ARC drawn at the page's size, one pixel wide (the 17 x 12 design scaled up had doubled dots).
- The manual and the quick guide: RUBBER, SMEAR's TUNE and SPD.

**Tests**

1. A mono bassline on RUBBER: short DEC, ENV up, RES 60-90: snappy, squelchy; DRIV up thickens it; RES at the top self-oscillates (KEY.T up plays it in tune).
2. FLTR page 2 on RUBBER: ABND and DBND as knobs; page 1 SUS/REL blank and the envelope picture still while turning them. Another filter: stock pages.
3. SMEAR at BLND 0: TUNE and the keyboard change the pitch only; SPD changes the speed only. TUNE 64 at SPD 1: as before.
4. RIFT machine pages: clean knob rings.

**Known issues**

- Sounds saved with GLASS open with RUBBER (the same filter type).

## v0.23 · STEADY

- **File:** `RIFT_v0.23_STEADY_OS1.11.syx` (`builds/v0.23-STEADY/`)
- **sha256:** `ac090a3cd3db877ad781cb3f63e62a12ea64161f4a7d1182301bc8439fd9465a`
- **Gated:** 2026-11-24, `CLEARED TO FLASH`
- **Source:** `5839eea` (this repository)

**Changes**

- **FASCIA's crackle** (owner, 2026-11-24, v0.21: "crackling in fascia ... it does crackle with one note"; takton: "crackling and noise in some synths"). FASCIA's sound code is the same as v0.19's, and the master plate's scratch words were ruled out (FASCIA scrambled at those words between blocks renders bit for bit the same). The likely cause is the DSP's time guard: it expected a voice to cost 1.5 x its last block and kept 1/8 of the frame in reserve; FASCIA's voice is RIFT's costliest (about 113k cycles at its peak on the unit's model), and v0.21's plate lengthened the stock's tail by a few thousand cycles, so a lone voice was left out on some blocks: clicks. `perc.guard.around` gains `grow`: FASCIA's dispatch (FASCIA, ORGAN, SILT, LIGATURE, DIGIDRUM, CONTOUR) expects x 1.25 (GROW 2). The reserve is unchanged.
- **CPU on RIFT's machine pages** (owner: "i dont see any cpu indicators"): while the DSP has left a voice out for time in the last half second (`smp_skipped_any`, the idle packets' SKIPMASK), "CPU" stands in the strip between the D/H column and the page dots (columns 121..123); the page is redrawn as it comes and goes.
- **CONTOUR's MACHINE SEL logo:** the owner's pick (a ridge over a grid, its orbit, a crosshair, the moon).
- **The quick guide** (`site/rift-quick.html`), linked from the manual and beside MANUAL on the patcher.

**Tests**

1. FASCIA, one note, then busy patterns: no clicks. If a click comes, look for CPU on the page: CPU showing means time; no CPU means something else (report it).
2. Heavy patterns (FASCIA chords, CONTOUR FDBK high notes): CPU shows when a tail is dropped, and goes away.
3. MACHINE SEL: CONTOUR's new logo.

**Known issues**

- Unverified on hardware: whether x 1.25 removes every click on the unit (the reserve keeps the frame safe either way).

## v0.22 · FROST

- **File:** `RIFT_v0.22_FROST_OS1.11.syx` (`builds/v0.22-FROST/`)
- **sha256:** `9b6d4c0d4f8cca2f9b0b43e3de3f55dbe0feb9c79ed5c1ca2fee36a5e1e7e0ac`
- **Gated:** 2026-11-24, `CLEARED TO FLASH`
- **Source:** `49e85dd` (this repository)

**Changes**

- **GLASS's overload** (owner, 2026-11-23: "a weird cpu issue ... weirdly bitcrushed like the monomachine overload sound"). Measured on the unit's cost model (rcost): GLASS took about 7,200 cycles a slot a block, as sample() loaded and stored every intermediate; fifteen WaveTone tracks on GLASS were 279k cycles over an idle frame's 415k, past the 667k frame. And GLASS ran after our voices' end mark, so the guard's limit (guard.tail_limit) never counted it: voices filled the frame to the limit and GLASS ran past it. Now:
  - `glass.program.samples_fast`: the filter's state, coefficients and level in registers, the same operations on the same operands in the same order (bit-exact to v0.18's sample() and to live.Voice): about 4,200 cycles a slot (`FAST`, False: the old loop).
  - The voices' end mark (`G.end_mark`) before GLASS and the sanitizer, so their time is measured with the stock's tail and the voices' limit leaves room for it.
- **SMEAR TUNE** (owner: "get TUNE working"): PLAY read at SPD x RATE, so TUNE and the note moved only the grains: at BLND 0 nothing. PLAY now reads at SPD x tr (tape).
- **SMEAR FRZ** (owner: "a FREEZE param"): page 2's E on OFS1 (record 246; WaveTone's default 50 reads OFF, so earlier tracks open unfrozen), OFF / ON. ON holds the read point (SPD kept) and gives PLAY's share of BLND to the grains. smp.asm grew past its L2 room; pvmix.asm moved to the span's last 768 bytes.
- **SMEAR page 2** (owner: "crammed in with the top row knobs ... closer to what WERP or slice does"): ONESHOT's page-2 layout; OVLP, SPRY, PRND and WIN as small pictures of what they do; the strip at the waveform's place; FRZ's label with a bar while on.
- **CONTOUR's MACHINE SEL logo** (owner: "a terrain synthesis logo"): two hills' contour lines.
- **The manual** (owner: "still mentions tholet and doesnt have every new feature"): THOLET gone from every section and entry; KEYBOARD HOLD back in Performance (it showed only with THOLET); the FLEX levels as v0.21 has them (4 dB, not 12); SMEAR's VOC said off; FRZ, TUNE and page 2; GLASS's CPU note.
- Gate: rcost's GLASS case (a slot within 5,000 cycles: v0.21's is 7,200), the runner's `smear` case "v0.22 FRZ", unit tests `test_v022_*` (GLASS fast = v0.18 path = live in the knee's three regions and both morph halves; SMEAR TUNE on PLAY, FRZ), test_sampler's FRZ detents.

**Known issues**

- SMEAR's VOC is still off (v0.18).

**Tests**

0. GLASS on six or more busy tracks (high RES, ENV, LPG) beside FASCIA or SMEAR: no crushed sound; GLASS sounds as in v0.21.
1. SMEAR at BLND 0: TUNE and notes transpose PLAY.
2. SMEAR FRZ ON / OFF, and p-locked on trigs.
3. SMEAR page 2: the four pictures move with OVLP, SPRY, PRND, WIN; the sample view clear; FRZ's bar.
4. MACHINE SEL: CONTOUR's logo.

## v0.21 · PLATE

- **File:** `RIFT_v0.21_PLATE_OS1.11.syx` (`builds/v0.21-PLATE/`)
- **sha256:** `fb49af0aad953c1b778e67c7f29ac0652e6c6fc1508b892f675a651ae773c7bc`
- **Gated:** 2026-11-23, `CLEARED TO FLASH`
- **Source:** `72382c7` (this repository)

**Changes**

- **The master reverb is a plate** (owner, 2026-11-23: "replace the stock master reverb with Plateau", the UI left as it is): Dattorro's tank (PLATEAU's, `dnfw.mverb`) in stereo (Table 2's first seven taps the left, the last seven the right) in the stock reverb core's place. The stock FX function's call of the core (sw 0xb8370c, `CALL 0xb82d1a (DB)`) becomes `JUMP wr_mv` (mverb.asm, in L2 after smear.asm); wr_mv reads the stock input stage's 32 samples (after the sends, HPF and LPF) and writes the 64 the stock mix stage takes (MIX VOL, routing), then resumes past the call. Its controls are the frame's reverb words (the FX slot at 2554: PRE 2586, DEC 2588, FREQ 2590, GAIN 2592): PRE the pre-delay (0..0.3 s), DEC the tank's decay, FREQ and GAIN a high shelf in the tank's loop. Its state and lines in DDR (0x82690000, 270 KB), cleared by itself after power-on (17 silent blocks).

- **A new start-up logo** (owner, 2026-11-23, after the GRAINS block-letter reference): the smoke gathers into RIFT in block letters (solid blocks, a one-pixel seam, a thin shadow line), then over the last 0.7 s the letters drip (one-pixel trickles from their lower edges) and decompose (the top first, in clumps, a little grit falling). 80 frames as before; the logo forms 3 % sooner. `tools/anim/rift_anim3d.py --json` writes `bootanim_rift.json`.
- **Rounder skeletons and real drums** (owner): a rounded cranium with brow, cheekbones, muzzle, teeth and a tapering jaw; round joints; djembe goblets; a steel pan's dish on a tripod. Pre-rendered: no run-time cost (6 bytes more).
- **PLATEAU withdrawn** (owner: "plateau is awful ... pull it, save it for later work"): out of MACHINE SEL (`plateau.machines.LISTED`) and its DSP program out of the build (`ON_DSP`: its 9 KB of the DSP's 1 MiB upload are the master reverb's room); a saved PLATEAU track opens as FM Tone. The source stays for its rework.

- **FLEX levels from the DN2 mk2 mod's v0.71** (owner: "the one we need finally"; NiKo's measurements on the mod's v0.67, a slate tone at -24 dBFS over USB): a take of a track `TRK_HW_DB` 6 (was 24), MAIN and IN takes played `MAIN_PLAY_DB` 4 louder (was 12). Takes recorded on earlier versions keep their level (a track's take 18 dB hot: GAIN -18 brings one back).

- Gate: runner part `mverb` (the stock FX path, bit-exact to `live.Verb` with noise in, the controls moving, the longest pre-delay; silence in, silence out; a negative control); rcost's master-reverb case; unit tests `test_mverb_program`.

**Known issues**

- As v0.20: CONTOUR has no MACHINE SEL logo; the page icons are the old ones scaled up; SMEAR's VOC is off.
- GLASS on several busy tracks can run the DSP past its frame (a crushed, crackly sound): fixed in v0.22. SMEAR's TUNE does nothing at BLND 0: fixed in v0.22.

**Tests**

0. The master reverb: a track's reverb send up, DEC, PRE, FREQ and GAIN round their ranges: a plate; sends at 0: nothing from the reverb. MIX VOL, HPF and LPF as before.
1. Power on: the campfire, the camera to the sky, the smoke forming RIFT in block letters, then dripping and crumbling; "RIFT 0.21" bottom right.
2. MACHINE SEL: no PLATEAU, no empty FX section; SMEAR first of the sample machines.
3. A project saved with a PLATEAU track: that track opens as FM Tone.
4. FLEX: record a track at GAIN 0: the take plays at the track's own level. Record MAIN and IN: their takes play at their sources' level.

## v0.20 · NXT

- **File:** `RIFT_v0.20_NXT_OS1.11.syx` (`builds/v0.20-NXT/`)
- **sha256:** `201ad11135fcc2b5ad56303449d6768152b31a0ebff92c8a6ce4e8aedfa3f4f8`
- **Gated:** 2026-11-23, `CLEARED TO FLASH`
- **Source:** `0a3ed43` (this repository)

**Adds**

- **SLEN NXT** (owner, 2026-11-22: "the slide trig update from dn2mk2 fw"; the DN2 mk2 mod's v0.66, ad2e1c5 + 1b0fd3e, the Analog Four's rule: "the slide is completed when the next trig is reached"): a slide lasts until the track's next trig (a note or a lock trig), round the track's own length; with no other trig, the whole length (up to 128 steps). NXT is SLEN's first choice and what a slide trig with no SLEN lock does (v0.19 and before: 1 step); the fixed lengths 1/8 .. 64 are unchanged. Stored as lock value 15 when locked explicitly (older firmware plays it as 1 step).
- **CONTOUR FDBK rescaled** (owner, 2026-11-23: "too extreme beyond about 38 ... amazing before that, especially in the first 5 or so value steps"): fb = u (0.0175 + 0.0525 u), 0.07 at 127 (was 0.25 u): the old usable 0..36 over the whole knob, the old first 5 steps over about the first 36.
- **CONTOUR in key on high notes** (owner: FDBK and FM "not in key" from about C4; "if it's between the two, keep the exact effect feedback has now"): FDBK pushes the orbit by a fixed amount in Hz, so above about B3 it pulls or locks the pitch off the note. At or below B3 (247.5 Hz), or with FDBK 0, every sample is as v0.19's (a unit test holds it). Above it, the feedback follows the pitch (a fixed share of the note) and the orbit takes 2 steps a sample (to about B4) or 4 (above): each note B3's behaviour transposed, in key. The guard expects CONTOUR's 4-step peak (CTR_PEAK, 110k cycles; rcost holds the worst block to it) whenever a slot's FDBK is up, so a jump to a high note never overruns the frame.
- Gate: runner contour part (feedback on high notes, 2 and 4 steps, notes moving: bit-exact), rcost (CONTOUR 4 steps within CTR_PEAK); unit tests (high notes bit-exact; nothing changes at or below B3 or without feedback).
- Gate: emu_slides' NXT checks (stock's track objects for all 16 tracks, stock's own step test, 8 cases exact per frame against the model: the next trig, round the length, no other trig, the next step, past 16 steps, an explicit SLEN, an explicit NXT, per-track length), run last, after FASCIA's, so every earlier slide check is frame for frame as before.

**Known issues**

- As v0.19: CONTOUR has no MACHINE SEL logo; the page icons are the old ones scaled up; SMEAR's VOC is off; PLATEAU's voice can be taken on a busy pattern.
- A slide trig in a project saved on v0.19 or earlier with no SLEN lock now lasts until the next trig, not 1 step: lock SLEN 1 to keep the old timing.

**Tests**

1. A FREQ (or any RIFT machine control) p-lock with SLD on, no SLEN lock, trigs on steps 1 and 5: the glide takes the four steps to step 5.
2. Only one trig on the track: the slide takes the whole pattern length.
3. SLEN set to 1: one step, as before. SLEN's first choice reads NXT.
4. A track with its own length (per-track mode): NXT wraps round that length.
5. Save, power-cycle, load: SLEN locks and NXT kept.
6. CONTOUR: FDBK from 0 up: a fine low end, usable all the way to 127.
7. CONTOUR with FDBK and FM up: play from C2 to C6: every note in key; up to B3 exactly as v0.19.
8. Four CONTOUR tracks with FDBK up playing high notes beside FASCIA: no dropouts.

## v0.19 · CONTOUR

- **File:** `RIFT_v0.19_CONTOUR_OS1.11.syx` (`builds/v0.19-CONTOUR/`)
- **sha256:** `7fa1dcfdd279f88449ca88ed3bb73762c9e6a1294173070f1db20e88512d3aa3`
- **Gated:** 2026-11-22, `CLEARED TO FLASH`
- **Source:** `8782096` (this repository)

**Adds**

- **CONTOUR** (type 25, `dnfw.contour`): a wave-terrain synth (owner, 2026-11-22: "option b", our own engine after TERRAIN for the Digitone II; none of its code is used).
  - An orbit (X, Y phases, RATIO from a table of 16; SIZX, SIZY, CNTX, CNTY, ROT; DRFT a slow wander of the centre) reads one of eight surfaces (SINE, FOLD, CHEB, FM, RING, EDGE, CHAOS, BITS), MORPH into the next; WARP, FOLD, FM (into the orbit's speed), FDBK, GRIT, LEV. Two pages (SYN1 ORBIT, SYN2 LAND), 16 controls.
  - DSP: in FASCIA's walk, stealable by the frame guard; its records ride ORGAN's; tables in DDR (0x8122B000); bit-exact to `contour.live.Voice` (25 unit tests, a negative control). About 24k cycles a block on the unit's cost model (rcost).
  - ColdFire: MACHINE SEL after DIGIDRUM in the synths, two LINE pages, formatters, slides; the output guard covers it (18..25); the DSP's age walk counts it as ours.
- **Machine pages at stock's size**: RIFT's 17x12 icons drawn at 22x16, the labels in stock's font, the rows at stock's positions (owner: the pages left a gap at the bottom).
- **SMEAR's page 2 display**: the sample's waveform, STRT/SIZE loop markers, the DSP's read point (SMEAR now writes it to the sampler voice's position, so the idle packet's playhead is SMEAR's own), and a grain cloud drawn from DENS, SPRY and OVLP.
- SMEAR's VOC code is no longer emitted while VOC is off (smear.asm 998 instructions); DSP image 1,042,588 of 1,048,575 bytes.
- Gate: runner part `contour` (every surface with every land control, two at once, FASCIA -> CONTOUR, a negative control); `rcost` includes CONTOUR's heaviest settings; emulator step `contour`.

**Known issues**

- CONTOUR has no MACHINE SEL logo yet.
- The page icons are the old ones scaled up until the redrawn set.
- SMEAR's grain cloud is drawn from its knobs, not from the DSP's grains.
- SMEAR's VOC is still off.
- PLATEAU's voice can be taken by the voice allocator on a busy pattern (reserve one).

**Tests**

1. MACHINE SEL: Contour after Digidrum. Notes from the keys; SURF through its eight surfaces; MORPH.
2. SIZX and SIZY small to large; CNTX, CNTY off centre; ROT; RATIO through its range; DRFT on a held note.
3. FM, FDBK, FOLD and GRIT up together: stable, nothing else goes silent.
4. Four or five CONTOUR tracks with FASCIA and ORGAN playing: no dropouts.
5. Every RIFT machine's pages: bigger icons, stock's font, nothing overlapping, no gap at the bottom.
6. SMEAR with a sample, page 2: the waveform, the read point moving, the cloud following DENS, SPRY and OVLP.
7. Save a project with a CONTOUR track, power-cycle, load: still Contour, same sound.

## v0.18 · GLASS

- **File:** `RIFT_v0.18_GLASS_OS1.11.syx` (`builds/v0.18-GLASS/`)
- **sha256:** `8e86233d9c16accfcaf22cae501a2809fc711e3aacc295fde0f0b2abc60e6f9a`
- **Gated:** 2026-11-22, `CLEARED TO FLASH`
- **Source:** `6f547dc` (this repository)

**Fixes**

- **The silent unit** (the owner and a tester, 2026-11-22: a SMEAR note gave a burst, then the whole unit silent until a reboot). SMEAR's VOC jobs cost 200..260k cycles a block on the unit's cost model (instructions + 0.95 x (4 L2 + 10 DDR accesses), fitted to the idle frame's measured 416k of 667k); the guard expected a voice's last block's cost, which VOC's light blocks kept low, so a heavy job ran the DSP past the frame. **VOC is off** (BLND's VOC share played by PLAY; `smear.live.VOC_ON`); the guard expects VOC's peak (`smear.stage.VOC_PEAK`) whenever it runs; and **an output guard**: fascia.asm's last pass zeroes any slot's block holding a sample not finite or not under 64 and starts its voice afresh (`fascia.program.sanitize`).
- **PLATEAU silent beside other tracks**: the guard stole it (left out twice in a note); now it is only left out of a block that has no room, and tried again the next.
- Gate: runner parts `rcost` (each machine's worst block on the unit's cost model against the frame; VOC within VOC_PEAK) and `sanitize` (NaN, +-inf, 100 and -64 blocks zeroed and their voices marked; 1.0 and -63.9 kept: negative controls).

**Adds**

- **GLASS** (filter type 6, `dnfw.glass`): a filter after the Serge VCFQ, on every machine (the owner, 2026-11-21: "high resonance without sounding clippy ... a more rounded, glassy sound ... not lose much low end with high resonance").
  - A zero-delay-feedback state-variable filter at twice the rate; a quadratic knee inside the loop (exactly linear below it, bounded at twice it); RES as ring time (4 ms .. 4 s, the same at every pitch); the input eased and the lows given back as RES rises; TYPE the LP/BP/HP morph.
  - Its own envelope: attack then decay from each trig, each segment bent (ABND on SUS, DBND on REL: exponential .. straight .. logarithmic); ENV on the cutoff; KEY.T.
  - LPG (on ENV DELAY, from 64): a vactrol-like gate on the level and the cutoff (DEC sets its fall).
  - DSP: at FASCIA's walk's end, on every slot whose filter is 6 (the stock unpack gives it DSP filter 0, so the chain skips its filter stage); its settings are Multi-Mode's fields in the track record; its state in DDR. fascia.asm moved 6 KB lower in L2 (perc.asm is 9 KB of its 16) to make room.
  - ColdFire: the DN2 mk2 mod's PING P2 edits, as GLASS (the FLTR list's Glass, the names, LOAD keeps 6, Multi-Mode's records, descriptor and curve); GLASS's names on the FLTR page while a track's filter is it.
- MACHINE SEL (owner): PLATEAU a section of its own (the FX machines, group 5: `group_fn`), with its own logo and FX under it; SMEAR first of the sample machines, with its own logo. Gate: the logos step checks both.
- Gate: runner part `glass` (bit-exact on two WaveTone tracks and a FASCIA track, the walk's models exact, Multi-Mode tracks untouched, a negative control); engine step (filter 6 kept by SAVE/LOAD, 7 and 8 load as Multi-Mode); flexcore (GLASS's names on and off); unit tests `test_glass_program` (15, a negative control), `test_glass_coldfire`.

**Known issues**

- SMEAR's VOC is off until it is redesigned to fit the unit.

- GLASS's layout is the interim one: ATTACK and DECAY BEND sit on SUS and REL (page 1), so GLASS's envelope has no sustain or release; LPG is a knob (ON from 64), not a switch.
- A sound saved with GLASS loads as Multi-Mode on stock firmware or the DN2 mk2 mod.
- PLATEAU's voice can be taken by the voice allocator on a busy pattern (reserve one).

**Tests**

0. SMEAR with a sample in SAMP: notes from the [TRIG] keys for a while, BLND across its range: it keeps sounding and nothing else goes silent. PLATEAU with two other tracks playing: the reverb stays.
1. FLTR: Glass after Equalizer, on a stock machine and on a RIFT machine. RES up: short hits ring as clean tones, never harsh.
2. TYPE through LP, BP, HP; FREQ and RES together.
3. KEY.T up, RES high: play a melody: the ring follows the notes.
4. ENV up; ABND and DBND fully left, then fully right: the sweep's shape changes.
5. LPG (ENV DELAY page 2) above 64: bongo-like pings; DEC sets their length.
6. Save the project with a GLASS track, power-cycle, load: still Glass.

## v0.17 · PLATEAU

- **File:** `RIFT_v0.17_PLATEAU_OS1.11.syx` (`builds/v0.17-PLATEAU/`)
- **sha256:** `3adfd4eb8044ced0842b83bd7af850eefc1b8c75b77634affe254aea498ef501`
- **Gated:** 2026-11-21, `CLEARED TO FLASH`
- **Source:** `01cbc1c` (this repository)

**Adds**

- **PLATEAU** (type 24, `dnfw.plateau`, `docs/fx-machines.md`): RIFT's first FX machine, a plate reverb after Dattorro's 1997 design (the network Valley's Plateau is built on; Plateau's code is not used).
  - It is a track: its input is the **BUS**, the chosen tracks' blocks (what TRK1..16 record), summed; its output is the track's voice, mono, through the track's own filter, amp, pan, sends and LEVEL. The sources keep their dry output.
  - Pages: FX1 PLATE: PRED SIZE DCAY DIFF / DAMP BAND LCUT LEV; FX2 TANK: TLOW MSPD MDEP HOLD / TUND IGN DRV ERLY.
  - **The BUS page:** FUNC + VOICE on a PLATEAU track (not the RECORDER): sixteen cells, [TRIG n] in or out, the LEDs lit, YES or NO back. The mask rides three of its records (six, six and four bits as knob values), set through the knob's path. A new PLATEAU track starts with every track but FX and FLEX tracks; its own track never.
  - One instance: its lines (336 KB) in THOLET's former DDR ring; the newest voice to start owns them, an older one goes quiet; a fresh one clears them (21 blocks of silence).
  - The bus is guarded: a sample not finite or not under 64 is taken as 0.
- **BUS for FLEX:** SRC BUS records the sum of chosen tracks; REC BUS, FLEX REC's third page (RIGHT from REC SETUP), picks them. MUTE SRC mutes every bus track. The mask rides CHAN's and R.LEN's low bytes; a take's source word carries it (bits 16..31). fascia.asm makes the sum, the recorder reads it the next block.
- **THOLET removed** completely (type 23 is a gone type: a saved THOLET track loads as FM Tone). Room: the image 12.6 KB, the DSP 8.2 KB; PLATEAU uses 7.8 KB of the DSP's.
- **DIGIDRUM's logo** is the owner's drum hit.
- Gate:
  - runner parts `plateau` (bit-exact in the assembled walk on the bus it read; its own track never summed; the lines' clearing; TUNED, HOLD with DRV; a second track taking the one instance; a negative control) and `pstress` (beside fifteen FASCIA voices under the guard: 0.36 of the frame); `rec` run 3b (BUS);
  - emulator: `flexcore` (BUS on FLEX; PLATEAU's defaults and mask, its BUS page through the firmware's keys, LEDs, its own track refused, NO and a track change close it), `rectext` (REC BUS and PLATEAU's BUS page pixel for pixel);
  - unit tests `test_plateau_program` (17, a negative control).

**Known issues**

- PLATEAU's voice is an ordinary voice: on a busy pattern the dynamic allocator can take it. Reserve one for its track in the voice allocation menu.
- A bus of many loud tracks can clip PLATEAU's input or a FLEX BUS take: turn IGN (or FLEX's GAIN) down.
- A MAIN or IN FLEX buffer saved to a sample slot plays 12 dB quieter than the buffer did.
- ERASE MOD DATA does not clear the tunings yet.

**Tests**

1. MACHINE SEL: Plateau after DIGIDRUM. On a free track, an INF trig; two other tracks playing.
2. FUNC + VOICE on it: the BUS page; every track but its own (struck) and any FLEX track lit. [TRIG] a playing track out and in: the reverb follows.
3. SIZE, DCAY, DIFF, DAMP; HOLD ON (the tail freezes), OFF (it fades).
4. TUND ON: play notes on the PLATEAU track: the plate rings at each note.
5. A second PLATEAU track triggered: it takes over, the first goes quiet.
6. FLEX: REC SETUP, RIGHT to REC BUS; pick two tracks; SRC BUS; record a take: both tracks in it.
7. A project with a THOLET track (v0.15/v0.16): it opens as FM Tone.
8. MACHINE SEL: DIGIDRUM shows the drum hit (DRUM).

## v0.16 · SMEAR

- **File:** `RIFT_v0.16_SMEAR_OS1.11.syx` (`builds/v0.16-SMEAR/`)
- **sha256:** `27e78d5763c42c49cff63f7831d50b88b6ce8073a0a04bfa800685202c2afdc4`
- **Gated:** 2026-11-21, `CLEARED TO FLASH`
- **Source:** `7f917f1` (this repository)

**Adds**

- **SMEAR** (type 9, in WERP's place; `dnfw.smear`, `docs/smear.md`): a Nebulae-style looper.
  - Three readers of one loop:
    - VOC, a phase vocoder on two lanes shared by the instrument (L2 and DDR);
    - PLAY, a tape read;
    - GRN, eight grains (seven windows).
  - BLND moves between them.
  - Its own chain stage, `smear.asm`, runs between `smp.asm` and `fascia.asm`. It has a mailbox written by the sample machines' glue, its own cost guard, and L0/L3/L5 kept around it.
  - Pages:
    - page 1: TUNE SPD BLND SAMP / STRT SIZE DENS LEV;
    - page 2: OVLP SPRY PRND WIN (four detents a window).
  - MACHINE SEL and TRK + CLEAR give it its own start (`smr_default`). SIZE reads LEN's 0..120 record.
- **The tables over the sample link:**
  - ORGAN's, THOLET's and SMEAR's tables (48 KB) are sent by the ColdFire at power-on (`K_TABLES`, `TABLE_LOAD`, a READY magic).
  - Each machine is silent until READY.
  - This keeps the DSP's upload under 1 MiB (1,043,650 of 1,048,575 unpacked).
- **LIGATURE: eight new blocks**, ports of WEFT's (`rv_weft.c`): TICK, ENV, VCA, CDIV, DUST, CHAOS, CRUSH, LISSA.
- **MACHINE SEL logos** (owner, 2026-11-21):
  - The logos: FASCIA, ORGAN, SILT, LIGATURE, DIGIDRUM (label DRUM), FLEX (REC) and the DT2 sample machines (SAMP).
  - How it is drawn: `csrc/waverider/page.c` `lg_draw` draws over stock's picture in the SRC column, after stock has drawn the screen. It finds MACHINE SEL by its view's vtable, and the machine by stock's own type-under-cursor (`0x4005b162`).
  - The logo data: `scripts/gen_logos.py`, from `src/dnfw/waverider/logos/*.png`, 46 × 32.
- **Room for it:**
  - In RIFT, the Monomachine page code (`md_page.c`) is stubbed. The image has 998 bytes left.
- Gate:
  - emulator steps `smear`, `logos` (each machine's picture pixel for pixel; THOLET, a stock machine and the FLTR column stock's) and `ligature`;
  - runner parts `smear`, `mstress`, the v0.17 blocks in `ligature`;
  - unit tests `test_smear_*`, `test_logos`, the lig tests;
  - the decode check now follows smp → smear → fascia.

**Known issues**

- SMEAR's second VOC lane runs from DDR: its speed on the unit is unmeasured (the guard keeps the frame either way).
- A MAIN or IN FLEX buffer saved to a sample slot plays 12 dB quieter than the buffer did.
- ERASE MOD DATA does not clear the tunings yet.

**Tests**

1. MACHINE SEL: Smear in WERP's place. Load a sample; BLND 0: the sample stretched.
2. SPD to FRZ: the sound held; STRT scans.
3. BLND 127; DENS, OVLP, SPRY; WIN through its seven.
4. Three SMEAR tracks: all sound; the oldest's VOC gives way.
5. Power-cycle with ORGAN or THOLET on a track: they sound within a second of the start.
6. LIGATURE: TICK -> ENV -> VCA on a WAVE: gated in time; DUST, CHAOS, LISSA as modulators.
7. MACHINE SEL: each logo under the cursor (DRUM, REC, SAMP labels); FM TONE and the FLTR column stock.

## v0.15 · THOLET

- **File:** `RIFT_v0.15_THOLET_OS1.11.syx` (`builds/v0.15-THOLET/`)
- **sha256:** `55650a6772453f5e77af099336ca4a0ab49dfef6881c1d3210e80d9393097583`
- **Gated:** 2026-11-21, `CLEARED TO FLASH`
- **Source:** `2f6874e` (this repository)

**Adds**

- **THOLET** (type 23, kind 19; the concept is Error Kit's; `dnfw.tholet`, `docs/tholet.md`):
  - It renders in FASCIA's walk; MACHINE SEL lists it after DIGIDRUM; it has two LINE pages
    (SYN1 PIANO: TUNE HAMR TONE FELT / DEC EP STRK LEV; SYN2 CLOUD: GRAN GDEN GSIZ GFM / GSPR REL VSNS BRTH).
  - Its sound:
    - a strike: one of six Kawai grand transients (VCSL, CC0), 50 ms at 24 kHz in μ-law;
    - 2 × 12 string partials as two-pole resonators; FELT adds a felt layer; EP morphs toward a Rhodes tine and adds the pickup's bark;
    - a grain cloud in a DDR ring (8 expodec grains), swelling into the tail;
    - REL is the damper at the note-off.
  - A retune keeps each ringing partial's amplitude and phase. Before this, a TUNE jump of 4 octaves mid-note rang 10× too loud.
  - Bit-exact: `live.Voice` = the program's run mode (`test_tholet_program`, 24 tests) = the assembled code (runner part `tholet`). Runner part `tstress` runs sixteen voices under the guard.
  - Its tables are in DDR (`THOLET_TABLES_DDR`, `THOLET_RING_DDR`).
- **perc.asm moved 16 KB lower** (0x200bc000), so fascia.asm has 140 KB of room (134.7 KB used).
- **KEYBOARD HOLD**, from the DN2 mk2 mod's v0.64 (dn2mk2-firmware 13a1d0b, 59fdcb4, 1541dab):
  - PTN + KEYBOARD switches stock's sustain (MIDI CC 64's) on all 16 tracks.
  - Notes already held stay latched; MIDI notes in and the arp's keys are held too; HOLD off releases them all.
  - The PTN view shows KB HOLD ON or OFF.
  - Gate step: `kbhold`.
- Includes v0.14.
- Gate: ColdFire step 6f6 `tholet` (MACHINE SEL, pages, p-locks, LFO names, TRK + CLEAR); `kbhold`; runner parts `tholet`, `tstress`; unit tests `test_tholet_program`.

**Known issues**

- A MAIN or IN FLEX buffer saved to a sample slot plays 12 dB quieter than the buffer did.
- ERASE MOD DATA does not clear the tunings yet.
- The DSP image has 1.3 KB of its 1 MiB upload left (v0.16 moves tables to the ColdFire).

**Tests**

1. MACHINE SEL: THOLET after DIGIDRUM; a note: a piano's strike and strings; HAMR through its six.
2. FELT, EP, STRK; DEC; page 2: GRAN up, a held note breaks into grains; short trigs: REL damps.
3. Turn TUNE quickly while a note rings: no jump in level.
4. PTN + KEYBOARD: KB HOLD ON; a chord played and let go keeps sounding; MIDI notes held too; again: all released.

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
