/* RIFT v0.12: LIGATURE's PATCH screen (owner, 2026-11-19: "just fix the ligature ui so its usable ...
 * we dont need presets"; the approved mockups, claude/ligature-design.md section 3).
 *
 *   Page 1 (SYN1)   the wiring PATCH plays, drawn as WEFT's grid: twelve tiles in three rows of four
 *                   in signal order (1..9, A, B, C), the cables between them (a back-cord dotted),
 *                   and below it the page's eight controls (PATCH TUNE FINE LFO1 / LFO2 VSNS DRIV
 *                   LEVL), each in its knob's place. smp_page.c draws it.
 *   YES             the EDIT screen over it: the selected tile inverted; the knobs edit the wiring:
 *                   A BLK, B TYP, C INA, D AMA / E INB, F AMB, G MOV, H OUT. LEFT/RIGHT/UP/DOWN
 *                   move through the tiles; FUNC + NO empties the block; YES the BLOCK view (its
 *                   inputs, its two settings by name, where it goes), YES again back; NO leaves.
 *   Pages 2..4      each knob named for its block's setting (4CUT, 4RES ...), from the wiring.
 *
 * The wirings: the project's 128 (dnfw.ligature.live WSLOTS), PATCH picks one. Kept here in RAM (the
 * words little-endian, as the DSP reads them), sent to the DSP's WIRE area by link.c (a slot when it
 * changes, all of them after a load), and kept in the project's list by pools.c (a list written two
 * seconds after the last edit, or when EDIT closes). A new project's wirings are the factory patches,
 * slot k the one PATCH k played before (so a sound saved before plays as it did). */
#include "wr_gen.h"

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

#define FRAMES (*(volatile u32 *)0x4058E8D4u)
#define KIT (*(volatile u32 *)0x800052A0u)
#define ACTIVE_TRACK (*(volatile u8 *)0x42431A6Cu)
#define SOUND(t) (KIT + 52u + 1163u * (u32)(t))
#define RECORD(id) ((const int *)(0x401F7F94u + 60u * (id)))
#define SOUND_VALUE(snd, id) ((int)(*(volatile u16 *)((snd) + 20u + 2u * (u32)RECORD(id)[1]) >> 8) - (RECORD(id)[2] >> 8))

#define IT_KEY 0
#define IT_KNOB 1
#define F_PRESS 0x01
#define F_RELEASE 0x10
enum { K_YES = 10, K_UP = 11, K_NO = 12, K_LEFT = 13, K_DOWN = 14, K_RIGHT = 15, K_FUNC = 17 };

/* the table in RAM: in the sample link's mirror, above pools.c's staging (pools.c's W_WIRE below it) */
#define LIG_WRAM ((u8 *)(SMP_MIRROR + 0x218000u))
#define LIG_WBYTES (4u * LIG_WTABLE_WORDS)
_Static_assert(0x218000u + LIG_WBYTES <= 0x220000u, "the wirings fit below link.c's resident spans");

extern void smp_wire_push(int slot);           /* link.c: to the DSP (-1: all) */
extern void smp_pl_wire_changed(void);         /* pools.c: into the project's list */
extern int smp_func_held;
extern u32 wr_draws;

int lig_state __attribute__((section(".data"))) = 0;          /* 0 off, 1 EDIT, 2 BLOCK */
int lig_blk __attribute__((section(".data"))) = 0;            /* the selected block, 0..11 */
int lig_cur __attribute__((section(".data"))) = 0;           /* the wiring EDIT shows */
u32 lig_seen_draw __attribute__((section(".data"))) = 0xFFFFFFFFu;   /* wr_draws when page 1 was drawn */
u32 lig_edits __attribute__((section(".data"))) = 0;          /* (counts: the gate reads them) */
u32 lig_saves __attribute__((section(".data"))) = 0;
u32 lig_loads __attribute__((section(".data"))) = 0;          /* tables taken from a list */
u32 lig_seeds __attribute__((section(".data"))) = 0;          /* tables made from the factory patches */
static u32 dirty_at __attribute__((section(".data"))) = 0;
static int track __attribute__((section(".data"))) = -1;

static u32 le32(const u8 *p) { return (u32)p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24; }
static void put_le32(u8 *p, u32 v) { p[0] = (u8)v; p[1] = (u8)(v >> 8); p[2] = (u8)(v >> 16); p[3] = (u8)(v >> 24); }

static void put_word(int k, int j, u32 v)
{
    put_le32(LIG_WRAM + 4u * (LIG_WHDR + LIG_WWORDS * (u32)k + (u32)j), v);
}

int lig_table_ok(const u8 *t)
{
    return t && le32(t) == LIG_WMAGIC && le32(t + 4) == LIG_WVERSION;
}

static void seed(void);
/* the table is always whole: RAM never written yet (a path where pools.c's power-on did not run, or
 * the emulator's snapshot) reads as the factory patches */
static void ensure(void)
{
    if (!lig_table_ok(LIG_WRAM))
        seed();
}

const u8 *lig_wbytes(void) { ensure(); return LIG_WRAM; }
u32 lig_wsize(void) { return LIG_WBYTES; }

/* slot K's word J (0..24) */
u32 lig_word(int k, int j)
{
    if (k < 0 || k >= LIG_WSLOTS || j < 0 || j >= LIG_WWORDS)
        return 0;
    ensure();
    return le32(LIG_WRAM + 4u * (LIG_WHDR + LIG_WWORDS * (u32)k + (u32)j));
}

static void seed(void)
{
    put_le32(LIG_WRAM, LIG_WMAGIC);
    put_le32(LIG_WRAM + 4, LIG_WVERSION);
    for (int k = 0; k < LIG_WSLOTS; k++) {
        int p = (k * LIG_NP) >> 7;
        if (p > LIG_NP - 1)
            p = LIG_NP - 1;
        for (int j = 0; j < LIG_WWORDS; j++)
            put_word(k, j, lig_factory[p][j]);
    }
    lig_seeds++;
}

/* pools.c: the project's table (SRC, LIG_WBYTES, from its list) or none (the factory patches);
 * then all of it to the DSP */
void lig_wire_loaded(const u8 *src)
{
    if (lig_table_ok(src)) {
        for (u32 k = 0; k < LIG_WBYTES; k++)
            LIG_WRAM[k] = src[k];
        lig_loads++;
    } else
        seed();
    dirty_at = 0;
    smp_wire_push(-1);
}

/* the active track's wiring slot (its PATCH), or -1: not a LIGATURE track */
int lig_track_slot(void)
{
    u32 t = ACTIVE_TRACK;
    if (!KIT || t > 15)
        return -1;
    volatile u8 *s = (volatile u8 *)SOUND(t);
    if ((signed char)s[0xDE] != LIG_TYPE)
        return -1;
    int top = lig_top[0], v = SOUND_VALUE(SOUND(t), lig_rid[0]);
    int k = top == 127 ? v : (v * 254 + top) / (2 * top);
    return k < 0 ? 0 : k > 127 ? 127 : k;
}

static int tidx(int ty)
{
    for (int i = 0; i < LIG_NT; i++)
        if (lig_types[i] == ty)
            return i;
    return -1;
}

static int clampi(int x, int lo, int hi) { return x < lo ? lo : x > hi ? hi : x; }

static void edited(void)
{
    lig_edits++;
    smp_wire_push(lig_cur);
    dirty_at = FRAMES | 1u;
}

static void flush(void)
{
    if (dirty_at) {
        dirty_at = 0;
        lig_saves++;
        smp_pl_wire_changed();
    }
}

/* knob CODE (1..8: A..H) turned by D on the EDIT or BLOCK screen */
static void knob(int code, int d)
{
    int k = lig_cur, i = lig_blk;
    if (code == 1) {
        lig_blk = clampi(lig_blk + d, 0, LIG_NB - 1);
        return;
    }
    u32 w0 = lig_word(k, 2 * i), w1 = lig_word(k, 2 * i + 1), last = lig_word(k, 2 * LIG_NB);
    int ty = (int)(w0 & 0xFF), sa = (int)(w0 >> 8 & 0xFF), sb = (int)(w0 >> 16 & 0xFF), d1 = (int)(w0 >> 24);
    int aa = (signed char)(w1 & 0xFF), ab = (signed char)(w1 >> 8 & 0xFF), d2 = (int)(w1 >> 16 & 0xFF);
    int out = (int)(last & 0xFF), bm = (int)(last >> 8 & 0xFFF);
    if (code == 2) {                            /* TYP: through the palette, none first */
        int was = tidx(ty), n = clampi(was + d, -1, LIG_NT - 1);
        if (n == was)
            return;
        ty = n < 0 ? 0 : lig_types[n];
        if (was < 0) {                          /* a new block: its settings in the middle */
            d1 = 64;
            d2 = 64;
            if (!aa)
                aa = 100;
        }
    } else if (code == 3)
        sa = clampi(sa + d, 0, LIG_NSRC - 1);
    else if (code == 4)
        aa = clampi(aa + d, -100, 100);
    else if (code == 5)
        sb = clampi(sb + d, 0, LIG_NSRC - 1);
    else if (code == 6)
        ab = clampi(ab + d, -100, 100);
    else if (code == 7)
        bm = d > 0 ? bm | 1 << i : bm & ~(1 << i);
    else if (code == 8)
        out = clampi(out + d, 0, LIG_NB - 1);
    else
        return;
    put_word(k, 2 * i, (u32)ty | (u32)sa << 8 | (u32)sb << 16 | (u32)(d1 & 0xFF) << 24);
    put_word(k, 2 * i + 1, (u32)(aa & 0xFF) | (u32)(ab & 0xFF) << 8 | (u32)(d2 & 0xFF) << 16);
    put_word(k, 2 * LIG_NB, (u32)out | (u32)bm << 8);
    edited();
}

static void empty_block(void)
{
    int k = lig_cur, i = lig_blk;
    put_word(k, 2 * i, 0);
    put_word(k, 2 * i + 1, 0);
    u32 last = lig_word(k, 2 * LIG_NB);
    put_word(k, 2 * LIG_NB, last & ~((u32)1 << (8 + i)));
    edited();
}

static void close(void)
{
    lig_state = 0;
    track = -1;
    flush();
}

int lig_visible(void) { return lig_state != 0; }

static int page_up(void) { return lig_seen_draw == wr_draws; }

/* the UI's item (rec.c's smp_ui_pop, after SLICE's menus) -> 1: ours */
int lig_pop(u8 *it)
{
    u32 code = (u32)it[4] << 24 | (u32)it[5] << 16 | (u32)it[6] << 8 | it[7];
    u32 flags = (u32)it[8] << 24 | (u32)it[9] << 16 | (u32)it[10] << 8 | it[11];
    int press = it[0] == IT_KEY && (flags & F_PRESS) && !(flags & F_RELEASE);
    if (it[0] == IT_KEY && code == K_FUNC)
        return 0;
    int func = smp_func_held;
    if (lig_state == 0) {
        if (press && code == K_YES && !func && page_up()) {
            int k = lig_track_slot();
            if (k < 0)
                return 0;
            lig_cur = k;
            track = ACTIVE_TRACK;
            lig_state = 1;
            if (lig_blk < 0 || lig_blk >= LIG_NB)
                lig_blk = 0;
            return 1;
        }
        return 0;
    }
    if (it[0] == IT_KNOB) {
        if (code < 1 || code > 8)
            return 0;
        knob((int)code, (signed char)it[8]);
        return 1;
    }
    if (it[0] != IT_KEY)
        return 0;
    int ours = code == K_YES || code == K_NO || (code >= K_UP && code <= K_RIGHT);
    if (!ours)
        return 0;
    if (!press)
        return 1;
    if (code == K_NO && func)
        empty_block();
    else if (code == K_NO)
        close();
    else if (code == K_YES)
        lig_state = lig_state == 1 ? 2 : 1;
    else if (code == K_LEFT)
        lig_blk = clampi(lig_blk - 1, 0, LIG_NB - 1);
    else if (code == K_RIGHT)
        lig_blk = clampi(lig_blk + 1, 0, LIG_NB - 1);
    else if (code == K_UP)
        lig_blk = lig_blk >= 4 ? lig_blk - 4 : lig_blk;
    else if (code == K_DOWN)
        lig_blk = lig_blk + 4 < LIG_NB ? lig_blk + 4 : lig_blk;
    return 1;
}

/* every UI pass (page.c's wr_poll): the list two seconds after the last edit; EDIT lets go when its
 * track is no longer the active LIGATURE track, or its PATCH moved (a p-lock, a slide) */
void lig_poll(void)
{
    if (dirty_at && FRAMES - dirty_at > 3000u)
        flush();
    if (lig_state && ((int)ACTIVE_TRACK != track || lig_track_slot() < 0))
        close();
}

/* page.c's wr_screen, over the page */
extern void smp_lig_draw(void *c, int state, int slot, int blk);
void lig_draw(void *c)
{
    smp_lig_draw(c, lig_state, lig_cur, lig_blk);
}
