/* The sample machines' controls as the DT2 handles them (v0.15, docs/sampler.md):
 *
 *   smp_quant   one detent a choice. A control with a few choices (PLAY, MODE, BARS,
 *               SEG, GRID, SLCE, the recorder's SRC) sits on a record of 0..127 or so;
 *               the stock setter (0x40037b74) now asks smp_quant before it writes the
 *               value, and a small turn moves to the next choice instead of the next
 *               value. Only for a sound whose machine is one of ours, only these slots.
 *   smp_formats the value the header shows when a control moves: the choice's name
 *               (FWD, 1/4, 1/16, a sample's name, IN, TRK3, MONO L, ON ...) instead of
 *               WaveTone's (Prim., Harm., a number). The records' formatters are swapped
 *               while a sample machine's track is the active one, as wr_names swaps their
 *               names, and put back otherwise.
 */
#include "wr_gen.h"

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

#define SEG_DETENTS 3                           /* v0.25: WERP's SEG, detents a choice */
#define CHOICE_DETENTS 4                        /* v0.26: PLAY, MODE, BARS, GRID */
#define PLAY_DETENTS 2                          /* v0.53 (owner: PLAY's four took too much turning, above all
                                                 * locking a trig): FWD .. RLOOP in 6 detents, not 12 */
#define SOUND_TYPE 0xDE                         /* the sound's machine type byte */
#define SOUND_VALUES 0x14                       /* its values, a 16-bit word a slot */
#define MNM_TUNE_J 7                            /* TUNE: knob H on every Monomachine machine */
#define MNM_TUNE_REC 240u                       /* its record (perc_param_ids[7]) */
#define RECORD_FMT(id) (*(void **)(0x401F7F94u + 60u * (id) + 0x34u))
#define RECORD_LO(id) (((const int *)(0x401F7F94u + 60u * (id)))[2] >> 8)

extern int smp_count(void);
extern const char *smp_name(int k);

static int zone_of(const struct smp_q *q, int c)
{
    int z = 0;
    while (z < q->n - 1 && c >= q->th[z])
        z++;
    return z;
}

/* v0.27: the Monomachine machines' choices (waves, switches, consonants, PCH's steps) as the
 * sample machines' (owner: "remember the detents ... on the ones with choices"): a short list
 * (8 or fewer) four detents a choice, a long one (the 32/64 waves, the 21 consonants, PCH's 33
 * steps) one detent a choice; a knob as it is. The choice is the page's (page.c mnm_text):
 * knob = the value over its record's span x 127, rounded; choice = knob x n / 128, or PCH's
 * table. A choice is written as the middle of its knob range. */
static int mnm_kn(int j, int v)
{
    int top = mnm_top[j];
    v -= mnm_lo[j];
    v = v < 0 ? 0 : v > top ? top : v;
    return (v * 254 + top) / (2 * top);
}

static int mnm_ch(int n, int k)
{
    return n == MNM_PCH ? mnm_pch_idx[k > 127 ? 127 : k] : (k * n) >> 7;
}

static int mnm_rep(int j, int n, int c)        /* the value (coarse) in the middle of choice C */
{
    int a = -1, b = -1;
    for (int k = 0; k < 128; k++)
        if (mnm_ch(n, k) == c) {
            if (a < 0)
                a = k;
            b = k;
        }
    if (a < 0)
        a = b = 0;
    int k = (a + b) / 2, top = mnm_top[j];
    return mnm_lo[j] + (k * 2 * top + 127) / 254;
}

/* v0.47: the Monomachine's TUNE (owner: FUNC + turn did not snap; the header said 0%..100%).
 * TUNE is the Monomachine's knob 0..127, 64 in tune, 32 a semitone (dnfw.mnm.machines: F =
 * note x 2048 / 12 + TUNE x 683 / 128): -2..+2 semitones. Its record spans 0..100, and the
 * knob is that x 127 / 100, rounded (page.c mnm_knob, the DSP's), so not every knob is there:
 * a value is written as the record value whose knob is nearest (perc.live.knob_word). FUNC +
 * turn moves to the next semitone the knob's way: 0, 32, 64, 96, 127. */
static int mnm_val_for(int j, int k, int t, int dir)
{
    /* the record's coarse value whose knob is past K the knob's way and nearest T (a tie: the
     * one further that way), so a click always moves */
    int top = mnm_top[j], best = -1, bd = 1000;
    for (int v = 0; v <= top; v++) {
        int kv = (v * 254 + top) / (2 * top);
        if (dir > 0 ? kv <= k : kv >= k)
            continue;
        int d = kv - t;
        if (d < 0) d = -d;
        if (d < bd || (d == bd && dir > 0)) { bd = d; best = v; }
    }
    return best < 0 ? -1 : mnm_lo[j] + best;
}

static int mnm_tune_step(int old, int dir)
{
    int k = mnm_kn(MNM_TUNE_J, old >> 8), t;
    if (dir > 0)
        t = k >= 127 ? 127 : (k / 32 + 1) * 32;
    else
        t = k <= 0 ? 0 : ((k - 1) / 32) * 32;
    if (t > 127) t = 127;
    int v = mnm_val_for(MNM_TUNE_J, k, t, dir);
    return v < 0 ? old : v << 8;                /* at the end already: as it is */
}

static int fq_click __attribute__((section(".data"))) = 0;      /* v0.32: a FUNC click (+1/-1), else 0 */

static int mnm_quant(int mi, int slot, int old, int value)
{
    int j = 0;
    while (j < 8 && mnm_slot[j] != slot)
        j++;
    if (j == 8 || !mnm_choices[mi][j])
        return value;                           /* not one of the eight, or a knob */
    int n = mnm_choices[mi][j], count = n == MNM_PCH ? mnm_pch_idx[127] + 1 : n;
    int oc = old >> 8, nc = (value >> 8) & 0xFF, d = nc - oc;
    if (nc == oc)
        return value;
    int c;
    if (d >= -8 && d <= 8) {
        static int m_acc __attribute__((section(".data"))) = 0;
        static u32 m_at __attribute__((section(".data"))) = 0;
        static int m_slot __attribute__((section(".data"))) = -1;
        int need = fq_click ? 1 : count <= 8 ? 4 : 1;   /* v0.32: FUNC: one a click */
        u32 now = *(volatile u32 *)0x4058E8D4u;
        int dir = d > 0 ? 1 : -1;
        if (now - m_at > 3000u || (m_acc > 0) != (dir > 0) || m_slot != slot)   /* 2 s */
            m_acc = 0;
        m_at = now;
        m_slot = slot;
        m_acc += dir;
        if (m_acc > -need && m_acc < need)
            return old;                         /* not yet: the choice stays */
        m_acc = 0;
        c = mnm_ch(n, mnm_kn(j, oc)) + dir;
    } else {
        c = mnm_ch(n, mnm_kn(j, nc));          /* a jump: the choice it lands in */
    }
    if (c < 0) c = 0;
    if (c > count - 1) c = count - 1;
    return mnm_rep(j, n, c) << 8;
}

/* v0.45: FASCIA's choices (TYPA, TYPB 6; BODA 9; BODB 10; XMOD 5: dnfw.fascia.machines), four
 * detents a choice, every one of them (the owner: the v0.26 feel; mnm_quant gives a list of
 * more than eight one detent each). The knob is the value over its record's span x 127,
 * rounded (0..127 records: the value), the choice (knob x n) >> 7, the model's choice(); a
 * choice is written as the middle of its knob range; a jump lands in the choice it reaches. */
#define FSC_DETENTS 4

static int fsc_j(const wr_mach_t *M, int slot)  /* the control on SLOT, or -1 */
{
    for (int j = 0; j < M->n; j++)
        if (M->slot[j] == slot)
            return j;
    return -1;
}

static int fsc_kn(const wr_mach_t *M, int j, int c)     /* coarse value -> knob 0..127 */
{
    int top = M->top[j];
    c -= M->lo[j];
    c = c < 0 ? 0 : c > top ? top : c;
    return top == 127 ? c : (c * 254 + top) / (2 * top);
}

static int fsc_rep(const wr_mach_t *M, int j, int o)    /* the coarse value in the middle of choice O */
{
    int n = M->choices[j], a = -1, b = -1;
    for (int k = 0; k < 128; k++)
        if (((k * n) >> 7) == o) {
            if (a < 0)
                a = k;
            b = k;
        }
    if (a < 0)
        a = b = 0;
    int k = (a + b) / 2, top = M->top[j];
    if (top == 127)
        return M->lo[j] + k;
    int best = 0, bd = 1000;                    /* the value whose knob is nearest k (as */
    for (int v = 0; v <= top; v++) {            /* dnfw.fascia.machines word_of) */
        int d = (v * 254 + top) / (2 * top) - k;
        d = d < 0 ? -d : d;
        if (d < bd) {
            bd = d;
            best = v;
        }
    }
    return M->lo[j] + best;
}

int fsc_q_off __attribute__((section(".data"))) = 0;   /* MACHINE SEL's defaults (rec.c): as written */

/* RIFT: FASCIA's and ORGAN's (the machine's descriptor, wr_gen.h wr_mach_t) */
static int fsc_quant(const wr_mach_t *M, int slot, int old, int value)
{
    int j = fsc_j(M, slot);
    if (fsc_q_off || j < 0 || !M->choices[j])
        return value;                           /* not the machine's, or a knob */
    int n = M->choices[j];
    int oc = old >> 8, nc = (value >> 8) & 0xFF, d = nc - oc;
    if (nc == oc)
        return value;
    int c;
    if (d >= -8 && d <= 8) {
        static int f_acc __attribute__((section(".data"))) = 0;
        static u32 f_at __attribute__((section(".data"))) = 0;
        static int f_slot __attribute__((section(".data"))) = -1;
        int need = fq_click ? 1 : FSC_DETENTS;  /* FUNC: one a click */
        u32 now = *(volatile u32 *)0x4058E8D4u;
        int dir = d > 0 ? 1 : -1;
        if (now - f_at > 3000u || (f_acc > 0) != (dir > 0) || f_slot != slot)   /* 2 s */
            f_acc = 0;
        f_at = now;
        f_slot = slot;
        f_acc += dir;
        if (f_acc > -need && f_acc < need)
            return old;                         /* not yet: the choice stays */
        f_acc = 0;
        c = ((fsc_kn(M, j, oc) * n) >> 7) + dir;
    } else
        c = (fsc_kn(M, j, nc) * n) >> 7;        /* a jump: the choice it lands in */
    if (c < 0) c = 0;
    if (c > n - 1) c = n - 1;
    return fsc_rep(M, j, c) << 8;
}

/* v0.32: FUNC + turn on our machines' controls (a tester's list, v0.30; the owner: a
 * control that jumps with FUNC should go on jumping to its next value, one that does not
 * should not move). Stock gives some parameter records a FUNC jump (WaveTone's TUNE by
 * octaves, its waves). Our controls sit on stock records, and on most of the ones that
 * carry a jump the stock jump lands on one fixed value and stays there (TUNE at 50, BR1 SU
 * at 0, PLAY MODE at 0 ...). So, with FUNC held, a fresh knob turn and a track on one of
 * our machines, each control is one of:
 *   KEEP    stock's jump is right for it: the sample machines' TUNE and PERC's first
 *           control (record 238: by octaves), PERC's TYPE;
 *   CHOICE  a control of choices (waves, modes, voice types, SEG, BARS, PCH): the next
 *           choice the way the knob turned, one a click;
 *   NONE    anything else: it does not move, as a stock control with no jump.
 * The knob comes from the UI item (rec.c smp_ui_pop: smp_knob_d, smp_knob_at). */
extern int smp_func_held;
extern int smp_knob_d;
extern u32 smp_knob_at;
#define KNOB_FRESH 150u                         /* 100 ms: the turn this write comes from */
enum { F_OFF, F_KEEP, F_CHOICE, F_NONE, F_TUNE, F_OCT, F_BIP };
#define OWN_REC_FIRST 238u                      /* our records (dnfw.perc / dnfw.sampler machines) */
#define OWN_REC_LAST 260u

static int func_kind(u8 *s, int slot, u32 id)
{
    if (!smp_func_held || !smp_knob_d || *(volatile u32 *)0x4058E8D4u - smp_knob_at > KNOB_FRESH)
        return F_OFF;
    int ty = (signed char)s[SOUND_TYPE];
    /* v0.33: only our machines' own controls, records 238..260 (PERC's, the Monomachine's
     * and the sample machines' pages); LFO, filter, amp and FX keep stock's FUNC jumps (the
     * owner and a tester: LFO DEPTH and SPEED snapped to nothing on our tracks in v0.32) */
    const wr_mach_t *M = wr_mach_type(ty);
    if (M) {                                    /* v0.45: FASCIA's (some on FM Tone's records); RIFT: ORGAN's */
        int j = fsc_j(M, slot);                 /* a choice steps, a knob stays put */
        if (j >= 0 && j == M->tune_j && M->rid[j] == id)
            return F_OCT;                       /* RIFT v0.3 (owner): TUNE by octaves, as fw1's tunes */
        if (j >= 0 && M->rid[j] == id && M->bipolar[j] && M->top[j] == 127 && M->lo[j] == 0)
            return F_BIP;                       /* RIFT v0.4 (owner): a centre-zero knob: 0, then an end */
        return j < 0 || M->rid[j] != id ? F_OFF : M->choices[j] ? F_CHOICE : F_NONE;
    }
    if (id < OWN_REC_FIRST || id > OWN_REC_LAST)
        return F_OFF;
    if (ty == 5)                                /* PERC */
        return slot == PERC_PTCH_SLOT || slot == PERC_TYPE_SLOT ? F_KEEP : F_NONE;
    int mi = mnm_index(ty - 4);
    if (mi >= 0) {
        for (int j = 0; j < 8; j++)
            if (mnm_slot[j] == slot) {
                if (j == MNM_TUNE_J && mnm_labels[mi][j][0] == 'T' && mnm_labels[mi][j][1] == 'U')
                    return F_TUNE;              /* v0.47: by semitones (the owner) */
                return mnm_choices[mi][j] ? F_CHOICE : F_NONE;
            }
        return F_NONE;
    }
    int type = SMP_IDX(ty - 4);                 /* v0.44: the sample row (BOUNCE's is 6, type 17) */
    if (type < 0)
        return F_OFF;                           /* a stock machine: stock's */
    if (slot == SMP_TUNE_SLOT)
        return F_KEEP;
    for (int k = 0; k < SMP_NQ; k++)
        if (smp_q[k].slot == slot && (smp_q[k].types & (1 << type)))
            return F_CHOICE;
    for (int k = 0; k < SMP_NQS; k++)
        if (smp_qs[k].slot == slot && (smp_qs[k].types & (1 << type)))
            return F_CHOICE;
    return F_NONE;
}

/* from the setter's write (hooks.S, smp_quant_hook): S = the sound, SLOT, VALUE the
 * value about to be written (coarse << 8 | fine), ID its record -> the value to write */
/* RIFT v0.5: a v0.4 ORGAN sound holds stock's record defaults on the 16 records pages 3 and 4
 * ride (org_legacy; the DSP reads that set as both pages at 0, so the organ sounds as it did). The
 * first write to one of their controls puts v0.5's defaults on all 16 (the sound's own words, where
 * the frame and the pages read them) and moves the written control from its default as the knob
 * moved. Not while fsc_write_defaults writes (fsc_q_off). */
static int org_is_legacy(u8 *s)
{
    for (int k = 0; k < ORG_N - ORG_LEGACY_FIRST; k++)
        if (*(volatile u16 *)(s + SOUND_VALUES + 2 * org_slot[ORG_LEGACY_FIRST + k]) != org_legacy[k])
            return 0;
    return 1;
}

static int org_unlegacy(u8 *s, int slot, int value)
{
    int j = fsc_j(&wr_mach_org, slot);
    if (j < ORG_LEGACY_FIRST || !org_is_legacy(s))
        return value;
    int old = *(volatile u16 *)(s + SOUND_VALUES + 2 * slot);
    for (int k = ORG_LEGACY_FIRST; k < ORG_N; k++)
        *(volatile u16 *)(s + SOUND_VALUES + 2 * org_slot[k]) = org_default[k];
    int nv = (org_default[j] >> 8) + (((value >> 8) & 0xFF) - (old >> 8));
    if (nv < org_lo[j]) nv = org_lo[j];
    if (nv > org_lo[j] + org_top[j]) nv = org_lo[j] + org_top[j];
    return nv << 8;
}

int smp_samp_direct __attribute__((section(".data"))) = 0;   /* v0.55: smp_set_samp's own write */
int smp_quant(u8 *s, int slot, int value, u32 id)
{
    if (smp_samp_direct && slot == SMP_SAMP_SLOT) {     /* v0.55: smp_set_samp's own write */
        extern u32 smp_samp_turned;
        smp_samp_turned = *(volatile u32 *)0x4058E8D4u;    /* (as below, for every SAMP write) */
        return smp_samp_direct > 0 ? smp_samp_direct << 8 : value;
    }
    if (!fsc_q_off && (signed char)s[SOUND_TYPE] == ORG_TYPE)
        value = org_unlegacy(s, slot, value);
    int fk = func_kind(s, slot, id);
    int old0 = *(volatile u16 *)(s + SOUND_VALUES + 2 * slot);
    if (fk == F_NONE)
        return old0;
    if (fk == F_TUNE)
        return mnm_tune_step(old0, smp_knob_d > 0 ? 1 : -1);
    if (fk == F_OCT) {
        /* RIFT v0.3: FASCIA's TUNE is +-24 semitones over the knob ((k - 64) x 24 / 64), so an
         * octave is 32: FUNC + turn moves to the next of 0, 32, 64, 96, 127 the knob's way
         * (-2, -1, 0, +1, +2 octaves; 127 is the knob's top, 23.6 semitones) */
        static const unsigned char oct[5] = {0, 32, 64, 96, 127};
        int k = old0 >> 8, n = k;
        if (smp_knob_d > 0) {
            for (int i = 0; i < 5; i++)
                if (oct[i] > k) { n = oct[i]; break; }
        } else {
            for (int i = 4; i >= 0; i--)
                if (oct[i] < k) { n = oct[i]; break; }
        }
        return n << 8;
    }
    if (fk == F_BIP) {
        /* RIFT v0.4 (owner, 2026-11-15): FUNC + turn on a knob whose zero is its middle (64):
         * toward the middle it lands on 0; from the middle (or past it) on the end that way */
        int k = old0 >> 8;
        if (smp_knob_d > 0)
            return (k < 64 ? 64 : 127) << 8;
        return (k > 64 ? 64 : 0) << 8;
    }
    if (fk == F_CHOICE) {                       /* one choice a click, the knob's way: a */
        fq_click = smp_knob_d > 0 ? 1 : -1;     /* detent's worth past the old value, */
        int oc0 = old0 >> 8;                    /* each table's own step below */
        if ((oc0 == 0 && fq_click < 0) || (oc0 == 255 && fq_click > 0)) {
            fq_click = 0;
            return old0;                        /* at the end already */
        }
        value = (oc0 + fq_click) << 8;
    } else
        fq_click = 0;
    if (wr_mach_type((signed char)s[SOUND_TYPE]))           /* v0.45: FASCIA; RIFT: ORGAN */
        return fsc_quant(wr_mach_type((signed char)s[SOUND_TYPE]), slot,
                         *(volatile u16 *)(s + SOUND_VALUES + 2 * slot), value);
    if (id == SMP_BUF_ID && (signed char)s[SOUND_TYPE] == SMP_BOUNCE_KIND + 4) {
        /* v0.54 (owner: BUF's detents are right, but the knob should not be seen moving
         * through them until the next buffer): FLEX's BUF holds one value a buffer, the one
         * rec.c buf_turn writes (lo + ceil(b x span / 8)), and moves a buffer every
         * CHOICE_DETENTS detents; in between the value, and the knob drawn from it, stay */
        extern unsigned int rt_buf_value(unsigned int v);
        static int b_acc __attribute__((section(".data"))) = 0;
        static u32 b_at __attribute__((section(".data"))) = 0;
        int old = *(volatile u16 *)(s + SOUND_VALUES + 2 * slot);
        int oc = old >> 8, nc = (value >> 8) & 0xFF, d = nc - oc;
        const int *rw = (const int *)(0x401F7F94u + 60u * SMP_BUF_ID);
        int lo = rw[2] >> 8, span = (rw[3] >> 8) - lo + 1;
        if (span < 8)
            span = 8;
        int b = (int)rt_buf_value((unsigned int)oc);
        if (d == 0)
            return old;                         /* a fine move: nothing to show */
        if (d >= -8 && d <= 8) {
            u32 now = *(volatile u32 *)0x4058E8D4u;
            int dir = d > 0 ? 1 : -1;
            if (now - b_at > 3000u || (b_acc > 0) != (dir > 0))     /* 2 s, or a turn back */
                b_acc = 0;
            b_at = now;
            b_acc += dir;
            if (b_acc > -CHOICE_DETENTS && b_acc < CHOICE_DETENTS)
                return (lo + (b * span + 7) / 8) << 8;              /* not yet: on its own value */
            b_acc = 0;
            b += dir;
        } else
            b = (int)rt_buf_value((unsigned int)nc);                /* a jump: where it landed */
        b = b < 0 ? 0 : b > 7 ? 7 : b;
        return (lo + (b * span + 7) / 8) << 8;
    }
    int mi = mnm_index((signed char)s[SOUND_TYPE] - 4);     /* v0.27: is_wr's kind */
    if (mi >= 0)
        return mnm_quant(mi, slot, *(volatile u16 *)(s + SOUND_VALUES + 2 * slot), value);
    int type = SMP_IDX((signed char)s[SOUND_TYPE] - 4);   /* v0.44: BOUNCE's row too */
    if (type < 0)
        return value;
    if (slot == SMP_SAMP_SLOT) {                /* v0.27: SAMP turned by hand (smp_page.c's list) */
        extern u32 smp_samp_turned;
        smp_samp_turned = *(volatile u32 *)0x4058E8D4u;
    }
    if (slot == SMP_SAMP_SLOT && type < SMP_N0 && smp_knob_d
        && *(volatile u32 *)0x4058E8D4u - smp_knob_at <= KNOB_FRESH) {
        /* v0.55: past SAMP 127 the list goes on to the eight FLEX buffers (rows 128..135, each
         * the buffer's code: rt_buf_code), turned by the knob's own steps */
        extern int rt_samp_buf(unsigned int samp);
        extern unsigned int rt_buf_code(unsigned int b);
        int old = *(volatile u16 *)(s + SOUND_VALUES + 2 * slot);
        int oc = old >> 8, nc = (value >> 8) & 0xFF;
        int ob = rt_samp_buf((unsigned int)oc);
        int row = ob >= 0 ? 128 + ob : oc;
        if (ob >= 0 || nc > 127 || (smp_knob_d > 0 && row + smp_knob_d > 127)) {
            int r = row + smp_knob_d;
            r = r < 0 ? 0 : r > 135 ? 135 : r;
            return (r >= 128 ? (int)rt_buf_code((unsigned int)(r - 128)) : r) << 8;
        }
    }
    int old = *(volatile u16 *)(s + SOUND_VALUES + 2 * slot);
    int oc = old >> 8, nc = (value >> 8) & 0xFF, d = nc - oc;
    for (int k = 0; k < SMP_NQ; k++) {
        const struct smp_q *q = &smp_q[k];
        if (q->slot != slot || !(q->types & (1 << type)))
            continue;
        if (nc == oc)
            return value;                       /* a fine move: as it is */
        int zo = zone_of(q, oc), z = zone_of(q, nc);
        if (d >= -8 && d <= 8) {
            /* a few detents a choice: v0.25, WERP's SEG three (owner: one detent each made
             * the middle choice easy to skip, and left the knob most of its turn with
             * nothing to do); v0.26, PLAY, MODE, BARS and GRID four (owner: their choices
             * sat in a sliver of the turn). A pause or a turn back starts the count again */
            static int q_acc __attribute__((section(".data"))) = 0;
            static u32 q_at __attribute__((section(".data"))) = 0;
            static int q_slot __attribute__((section(".data"))) = -1;
            int need = fq_click ? 1 : slot == SMP_SEG_SLOT ? SEG_DETENTS
                     : id == SMP_PLAY_REC ? PLAY_DETENTS : CHOICE_DETENTS;
            u32 now = *(volatile u32 *)0x4058E8D4u;
            int dir = d > 0 ? 1 : -1;
            if (now - q_at > 3000u || (q_acc > 0) != (dir > 0) || q_slot != slot)   /* 2 s */
                q_acc = 0;
            q_at = now;
            q_slot = slot;
            q_acc += dir;
            if (q_acc > -need && q_acc < need)
                return old;                     /* not yet: the choice stays */
            q_acc = 0;
        }
        if (d >= -8 && d <= 8) {                /* a detent (or a pushed one): the next choice */
            z = zo + (d > 0 ? 1 : -1);
            if (z < 0) z = 0;
            if (z > q->n - 1) z = q->n - 1;
        }
        return q->rep[z] << 8;
    }
    for (int k = 0; k < SMP_NQS; k++) {
        const struct smp_qs *q = &smp_qs[k];
        if (q->slot != slot || !(q->types & (1 << type)))
            continue;
        if (nc == oc)
            return value;
        int c = nc;
        if (d >= -8 && d <= 8)
            c = oc + (d > 0 ? q->step : -q->step);
        c = q->lo + (c - q->lo) / q->step * q->step;
        if (c < q->lo) c = q->lo;
        if (c > q->hi) c = q->hi - (q->hi - q->lo) % q->step;
        return c << 8;
    }
    return value;
}

/* -- the header's text -------------------------------------------------------------------- */

static void put(char *buf, const char *s, int max)
{
    int k = 0;
    while (k < max && s[k]) {
        buf[k] = s[k];
        k++;
    }
    buf[k] = 0;
}

static void put_num(char *buf, int v)
{
    char t[8];
    int n = 0, neg = v < 0;
    if (neg) v = -v;
    do {
        t[n++] = '0' + v % 10;
        v /= 10;
    } while (v && n < 6);
    int k = 0;
    if (neg) buf[k++] = '-';
    while (n)
        buf[k++] = t[--n];
    buf[k] = 0;
}

static int coarse(int v, u32 id)
{
    return ((v >> 8) & 0xFF) - RECORD_LO(id);
}

static int steps_at(int v, const unsigned char *steps)
{
    int k = 0;
    while (k < 7 && v >= steps[k])
        k++;
    return k;
}

static void f_play(int v, char *buf)
{
    static const char *n[4] = {"REV", "REV LOOP", "FWD LOOP", "FWD"};
    int c = coarse(v, SMP_PLAY_REC) >> 5;
    put(buf, n[c > 3 ? 3 : c], 9);
}

static void f_mode(int v, char *buf)
{
    static const char *n[4] = {"REV", "REV LOOP", "FWD LOOP", "FWD"};
    int c = coarse(v, SMP_MODE_REC) >> 5;
    put(buf, n[c > 3 ? 3 : c], 9);
}

static void f_bars(int v, char *buf)
{
    put(buf, smp_bars[steps_at(coarse(v, SMP_BARS_REC), smp_bars_steps)], 4);
}

static void f_seg(int v, char *buf)
{
    int n = 32 >> steps_at(coarse(v, SMP_SEG_REC), smp_seg_steps);   /* v0.18: 1/32, 1/16, 1/8 (the DT2's) */
    if (n == 1) {
        put(buf, "1", 2);
        return;
    }
    buf[0] = '1';
    buf[1] = '/';
    put_num(buf + 2, n);
}

static void f_grid(int v, char *buf)
{
    int g = coarse(v, SMP_GRID_REC) / 24;
    put_num(buf, smp_grids[g > 4 ? 4 : g]);
}

static void f_samp(int v, char *buf)
{
    int s = coarse(v, SMP_SAMP_REC);
    if (s <= 0) {
        put(buf, "OFF", 4);
        return;
    }
    int n = smp_count();
    if (n >= 0 && s <= n) {                     /* your samples: their names */
        const char *nm = smp_name(s - 1);
        if (nm[0]) {
            put(buf, nm, 7);
            return;
        }
    }
    put_num(buf, s);                            /* nothing there (v0.20: no test sounds) */
}

static void f_slce(int v, char *buf)            /* GRID's SLCE: NOTE, then 1..63 (v0.18, the DT2's) */
{
    int s = coarse(v, SMP_SLICE_ID) >> 1;
    if (s <= 0)
        put(buf, "NOTE", 4);
    else
        put_num(buf, s);
}

static void f_slen(int v, char *buf)            /* GRID's LEN: how many slices, 1..64 */
{
    put_num(buf, (coarse(v, SMP_SLEN_ID) >> 1) + 1);
}

/* RIFT v0.16 SMEAR (dnfw.smear.live._speed): SPD, -4.00..+4.00 (64 frozen, +-1 within 0.06);
 * WIN, the grain window's name (live.WIN_NAMES, k * 7 >> 7) */
static void f_spd(int v, char *buf)
{
    int k = coarse(v, 254), h = (k - 64) * 400 / 63;
    if (h > 94 && h < 106) h = 100;
    if (h < -94 && h > -106) h = -100;
    if (k == 64) {
        put(buf, "FRZ", 4);
        return;
    }
    int a = h < 0 ? -h : h;
    buf[0] = h < 0 ? '-' : '+';
    buf[1] = (char)('0' + a / 100);
    buf[2] = '.';
    buf[3] = (char)('0' + a / 10 % 10);
    buf[4] = (char)('0' + a % 10);
    buf[5] = 0;
}

static void f_win(int v, char *buf)
{
    static const char *n[7] = {"GAUS", "BHAR", "EXPO", "TRI", "RAMP", "SINC", "RECT"};
    int k = coarse(v, 262) * 7 >> 7;
    put(buf, n[k > 6 ? 6 : k], 5);
}

static void f_frz(int v, char *buf)             /* RIFT v0.22 SMEAR's FRZ: OFF, ON (its raw 0..100, ON from SMR_FRZ_ON) */
{
    put(buf, ((v >> 8) & 0xFF) >= SMR_FRZ_ON ? "ON" : "OFF", 4);
}

static void f_buf(int v, char *buf)             /* v0.49 FLEX's BUF: 01..08, an eighth of the knob each */
{
    extern unsigned int rt_buf_value(unsigned int v);
    unsigned int b = rt_buf_value((unsigned int)(v >> 8) & 0xFFu) + 1u;
    buf[0] = '0';
    buf[1] = (char)('0' + b);
    buf[2] = 0;
}

/* v0.47: the Monomachine's TUNE as a signed knob, -64..+63 (0 in tune, 32 a semitone),
 * not stock's percentage of the record it sits on */
static void f_mtune(int v, char *buf)
{
    int k = mnm_kn(MNM_TUNE_J, (v >> 8) & 0xFF) - 64;
    if (k > 0) {
        buf[0] = '+';
        put_num(buf + 1, k);
    } else
        put_num(buf, k);
}

/* v0.45: FASCIA's values in the header (and its page with SYN held): a knob 0..127, the
 * bipolar three (TUNE, GEOM, SHIFT; v2's SKIN gone with v2) -64..+63, a choice its option's name. One formatter
 * a control: the stock formatter is handed the value only. */
static void fsc_text(const wr_mach_t *M, int j, int v, char *buf)
{
    int k = fsc_kn(M, j, (v >> 8) & 0xFF), n = M->choices[j];
    if (M == &wr_mach_lig && j == 0) {          /* RIFT v0.12: PATCH, a wiring slot 1..128 */
        put_num(buf, k + 1);
        return;
    }
    if (n) {
        int o = (k * n) >> 7;
        put(buf, M->choice_name[M->choice_at[j] + (o > n - 1 ? n - 1 : o)], 7);
    } else if (M->bipolar[j]) {
        if (k == 64)
            put(buf, "0", 2);
        else {
            buf[0] = k > 64 ? '+' : '-';
            put_num(buf + 1, k > 64 ? k - 64 : 64 - k);
        }
    } else
        put_num(buf, k);
}
#define FSC_F(j) static void fsc_f##j(int v, char *b) { fsc_text(&wr_mach_fsc, j, v, b); }
#define ORG_F(j) static void org_f##j(int v, char *b) { fsc_text(&wr_mach_org, j, v, b); }
ORG_F(0) ORG_F(1) ORG_F(2) ORG_F(3) ORG_F(4) ORG_F(5) ORG_F(6) ORG_F(7)
ORG_F(8) ORG_F(9) ORG_F(10) ORG_F(11) ORG_F(12) ORG_F(13) ORG_F(14) ORG_F(15)   /* RIFT: ORGAN's 16 */
ORG_F(16) ORG_F(17) ORG_F(18) ORG_F(19) ORG_F(20) ORG_F(21) ORG_F(22) ORG_F(23)   /* v0.5: pages 3 */
ORG_F(24) ORG_F(25) ORG_F(26) ORG_F(27) ORG_F(28) ORG_F(29) ORG_F(30) ORG_F(31)   /* and 4 */
static void (*const org_fns[])(int, char *) = {
    org_f0, org_f1, org_f2, org_f3, org_f4, org_f5, org_f6, org_f7, org_f8, org_f9, org_f10, org_f11,
    org_f12, org_f13, org_f14, org_f15, org_f16, org_f17, org_f18, org_f19, org_f20, org_f21, org_f22,
    org_f23, org_f24, org_f25, org_f26, org_f27, org_f28, org_f29, org_f30, org_f31};
_Static_assert(sizeof org_fns / sizeof org_fns[0] == ORG_N, "one formatter an ORGAN control");
#define SLT_F(j) static void slt_f##j(int v, char *b) { fsc_text(&wr_mach_slt, j, v, b); }
SLT_F(0) SLT_F(1) SLT_F(2) SLT_F(3) SLT_F(4) SLT_F(5) SLT_F(6) SLT_F(7)
SLT_F(8) SLT_F(9) SLT_F(10) SLT_F(11) SLT_F(12) SLT_F(13) SLT_F(14) SLT_F(15)
SLT_F(16) SLT_F(17) SLT_F(18) SLT_F(19) SLT_F(20) SLT_F(21) SLT_F(22) SLT_F(23)
SLT_F(24) SLT_F(25) SLT_F(26) SLT_F(27) SLT_F(28) SLT_F(29) SLT_F(30) SLT_F(31)   /* RIFT: SILT's 32 */
static void (*const slt_fns[])(int, char *) = {
    slt_f0, slt_f1, slt_f2, slt_f3, slt_f4, slt_f5, slt_f6, slt_f7, slt_f8, slt_f9, slt_f10, slt_f11,
    slt_f12, slt_f13, slt_f14, slt_f15, slt_f16, slt_f17, slt_f18, slt_f19, slt_f20, slt_f21, slt_f22,
    slt_f23, slt_f24, slt_f25, slt_f26, slt_f27, slt_f28, slt_f29, slt_f30, slt_f31};
_Static_assert(sizeof slt_fns / sizeof slt_fns[0] == SLT_N, "one formatter a SILT control");
#define LIG_F(j) static void lig_f##j(int v, char *b) { fsc_text(&wr_mach_lig, j, v, b); }
LIG_F(0) LIG_F(1) LIG_F(2) LIG_F(3) LIG_F(4) LIG_F(5) LIG_F(6) LIG_F(7)
LIG_F(8) LIG_F(9) LIG_F(10) LIG_F(11) LIG_F(12) LIG_F(13) LIG_F(14) LIG_F(15)
LIG_F(16) LIG_F(17) LIG_F(18) LIG_F(19) LIG_F(20) LIG_F(21) LIG_F(22) LIG_F(23)
LIG_F(24) LIG_F(25) LIG_F(26) LIG_F(27) LIG_F(28) LIG_F(29) LIG_F(30) LIG_F(31)   /* RIFT: LIGATURE's 32 */
static void (*const lig_fns[])(int, char *) = {
    lig_f0, lig_f1, lig_f2, lig_f3, lig_f4, lig_f5, lig_f6, lig_f7, lig_f8, lig_f9, lig_f10, lig_f11,
    lig_f12, lig_f13, lig_f14, lig_f15, lig_f16, lig_f17, lig_f18, lig_f19, lig_f20, lig_f21, lig_f22,
    lig_f23, lig_f24, lig_f25, lig_f26, lig_f27, lig_f28, lig_f29, lig_f30, lig_f31};
_Static_assert(sizeof lig_fns / sizeof lig_fns[0] == LIG_N, "one formatter a LIGATURE control");
#define DGD_F(j) static void dgd_f##j(int v, char *b) { fsc_text(&wr_mach_dgd, j, v, b); }
DGD_F(0) DGD_F(1) DGD_F(2) DGD_F(3) DGD_F(4) DGD_F(5) DGD_F(6) DGD_F(7)   /* RIFT: DIGIDRUM's 16 */
DGD_F(8) DGD_F(9) DGD_F(10) DGD_F(11) DGD_F(12) DGD_F(13) DGD_F(14) DGD_F(15)
static void (*const dgd_fns[])(int, char *) = {dgd_f0, dgd_f1, dgd_f2, dgd_f3, dgd_f4, dgd_f5, dgd_f6, dgd_f7,
    dgd_f8, dgd_f9, dgd_f10, dgd_f11, dgd_f12, dgd_f13, dgd_f14, dgd_f15};
_Static_assert(sizeof dgd_fns / sizeof dgd_fns[0] == DGD_N, "one formatter a DIGIDRUM control");
#define PLT_F(j) static void plt_f##j(int v, char *b) { fsc_text(&wr_mach_plt, j, v, b); }
PLT_F(0) PLT_F(1) PLT_F(2) PLT_F(3) PLT_F(4) PLT_F(5) PLT_F(6) PLT_F(7)   /* RIFT v0.17: PLATEAU's 16 */
PLT_F(8) PLT_F(9) PLT_F(10) PLT_F(11) PLT_F(12) PLT_F(13) PLT_F(14) PLT_F(15)
static void (*const plt_fns[])(int, char *) = {plt_f0, plt_f1, plt_f2, plt_f3, plt_f4, plt_f5, plt_f6, plt_f7,
    plt_f8, plt_f9, plt_f10, plt_f11, plt_f12, plt_f13, plt_f14, plt_f15};
_Static_assert(sizeof plt_fns / sizeof plt_fns[0] == PLT_N, "one formatter a PLATEAU control");
#define CTR_F(j) static void ctr_f##j(int v, char *b) { fsc_text(&wr_mach_ctr, j, v, b); }
CTR_F(0) CTR_F(1) CTR_F(2) CTR_F(3) CTR_F(4) CTR_F(5) CTR_F(6) CTR_F(7)   /* RIFT v0.20: CONTOUR's 16 */
CTR_F(8) CTR_F(9) CTR_F(10) CTR_F(11) CTR_F(12) CTR_F(13) CTR_F(14) CTR_F(15)
static void (*const ctr_fns[])(int, char *) = {ctr_f0, ctr_f1, ctr_f2, ctr_f3, ctr_f4, ctr_f5, ctr_f6, ctr_f7,
    ctr_f8, ctr_f9, ctr_f10, ctr_f11, ctr_f12, ctr_f13, ctr_f14, ctr_f15};
_Static_assert(sizeof ctr_fns / sizeof ctr_fns[0] == CTR_N, "one formatter a CONTOUR control");
#define SPL_F(j) static void spl_f##j(int v, char *b) { fsc_text(&wr_mach_spl, j, v, b); }
SPL_F(0) SPL_F(1) SPL_F(2) SPL_F(3) SPL_F(4) SPL_F(5) SPL_F(6) SPL_F(7)   /* RIFT v0.25: SPALL's 16 */
SPL_F(8) SPL_F(9) SPL_F(10) SPL_F(11) SPL_F(12) SPL_F(13) SPL_F(14) SPL_F(15)
static void (*const spl_fns[])(int, char *) = {spl_f0, spl_f1, spl_f2, spl_f3, spl_f4, spl_f5, spl_f6, spl_f7,
    spl_f8, spl_f9, spl_f10, spl_f11, spl_f12, spl_f13, spl_f14, spl_f15};
_Static_assert(sizeof spl_fns / sizeof spl_fns[0] == SPL_N, "one formatter a SPALL control");
FSC_F(0) FSC_F(1) FSC_F(2) FSC_F(3) FSC_F(4) FSC_F(5) FSC_F(6) FSC_F(7)
FSC_F(8) FSC_F(9) FSC_F(10) FSC_F(11) FSC_F(12) FSC_F(13) FSC_F(14) FSC_F(15)
FSC_F(16) FSC_F(17) FSC_F(18) FSC_F(19) FSC_F(20) FSC_F(21) FSC_F(22) FSC_F(23)
FSC_F(24) FSC_F(25) FSC_F(26) FSC_F(27) FSC_F(28) FSC_F(29) FSC_F(30) FSC_F(31)   /* RIFT: pass 3's 32 */
static void (*const fsc_fns[])(int, char *) = {
    fsc_f0, fsc_f1, fsc_f2, fsc_f3, fsc_f4, fsc_f5, fsc_f6, fsc_f7, fsc_f8, fsc_f9, fsc_f10, fsc_f11,
    fsc_f12, fsc_f13, fsc_f14, fsc_f15, fsc_f16, fsc_f17, fsc_f18, fsc_f19, fsc_f20, fsc_f21, fsc_f22, fsc_f23,
    fsc_f24, fsc_f25, fsc_f26, fsc_f27, fsc_f28, fsc_f29, fsc_f30, fsc_f31};
_Static_assert(sizeof fsc_fns / sizeof fsc_fns[0] == FSC_N, "one formatter a FASCIA control");
static void *fsc_stock_fmt[FSC_N] __attribute__((section(".data")));

/* the records whose text is ours on a sample machine's track; 239, SLCE's and LEN's
 * records only on GRID's (ONESHOT's STRT, LOOP and CFAD are the same records) */
static const u16 fmt_ids[] = {SMP_PLAY_REC, SMP_MODE_REC, SMP_BARS_REC, SMP_SEG_REC, SMP_GRID_REC,
                              SMP_SAMP_REC, SMP_SLICE_ID, SMP_SLEN_ID, SMP_BUF_ID, MNM_TUNE_REC};
static void (*const fmt_fns[])(int, char *) = {f_play, f_mode, f_bars, f_seg, f_grid, f_samp,
                                               f_slce, f_slen, f_buf, f_mtune};   /* (v0.22: the recorder's are a screen's now) */
#define NFMT (int)(sizeof fmt_ids / sizeof fmt_ids[0])
static void *stock_fmt[NFMT] __attribute__((section(".data")));
static int fmt_saved __attribute__((section(".data"))) = 0;

void smp_fine(int kind);

/* from wr_names, when the active track's machine changes: KIND as is_wr answers it
 * (SMP_KIND0.. for the sample machines) */
void smp_formats(int kind)
{
    if (!fmt_saved) {
        for (int k = 0; k < NFMT; k++)
            stock_fmt[k] = RECORD_FMT(fmt_ids[k]);
        for (int j = 0; j < FSC_N; j++)         /* v0.45: FASCIA's, before anything is swapped */
            fsc_stock_fmt[j] = RECORD_FMT(fsc_rid[j]);
        fmt_saved = 1;
    }
    for (int j = 0; j < FSC_N; j++)             /* v0.45: stock's back first (the sample */
        RECORD_FMT(fsc_rid[j]) = fsc_stock_fmt[j];   /* machines' share five of the records) */
    int smp = SMP_IDX(kind) >= 0;   /* (v0.26: 10.. the Monomachine's; v0.44: 13 BOUNCE) */
    for (int k = 0; k < NFMT; k++) {
        void *f = stock_fmt[k];
        if (fmt_ids[k] == MNM_TUNE_REC) {       /* v0.47: on a Monomachine machine's track only */
            RECORD_FMT(fmt_ids[k]) = mnm_index(kind) >= 0 ? (void *)fmt_fns[k] : f;
            continue;
        }
        int grid_only = fmt_ids[k] == SMP_GRID_REC;
        int slices = fmt_ids[k] == SMP_SLICE_ID || fmt_ids[k] == SMP_SLEN_ID;  /* GRID's, SLICE's */
        if (smp && (!grid_only || kind == SMP_GRID_KIND)
            && (!slices || kind == SMP_GRID_KIND || kind == SMP_SLICE_KIND)
            && (fmt_ids[k] != SMP_MODE_REC || kind == SMP_WERP_KIND)
            && (fmt_ids[k] != SMP_BUF_ID || kind == SMP_BOUNCE_KIND)     /* v0.46: 244 is stock's elsewhere */
            && !(kind == SMP_WERP_KIND && (fmt_ids[k] == SMP_PLAY_REC || fmt_ids[k] == SMP_BARS_REC
                                           || fmt_ids[k] == SMP_SEG_REC || fmt_ids[k] == SMP_MODE_REC)))   /* RIFT v0.16: SMEAR's own */
            f = (void *)fmt_fns[k];
        RECORD_FMT(fmt_ids[k]) = f;
    }
    smp_fine(kind);
    if (kind == SMP_WERP_KIND) {                /* RIFT v0.16: SMEAR's SPD and WIN */
        RECORD_FMT(254) = (void *)f_spd;
        RECORD_FMT(262) = (void *)f_win;
        RECORD_FMT(SMR_FRZ_ID) = (void *)f_frz;   /* RIFT v0.22 */
    }
    if (kind == FSC_KIND)                       /* v0.45: FASCIA's, last */
        for (int j = 0; j < FSC_N; j++)
            RECORD_FMT(fsc_rid[j]) = (void *)fsc_fns[j];
    if (kind == ORG_KIND)                       /* RIFT: ORGAN's (its records are FASCIA's: restored above) */
        for (int j = 0; j < ORG_N; j++)
            RECORD_FMT(org_rid[j]) = (void *)org_fns[j];
    if (kind == SLT_KIND)                       /* RIFT: SILT's (FASCIA's records too) */
        for (int j = 0; j < SLT_N; j++)
            RECORD_FMT(slt_rid[j]) = (void *)slt_fns[j];
    if (kind == LIG_KIND)                       /* RIFT: LIGATURE's (FASCIA's records too) */
        for (int j = 0; j < LIG_N; j++)
            RECORD_FMT(lig_rid[j]) = (void *)lig_fns[j];
    if (kind == DGD_KIND)                       /* RIFT: DIGIDRUM's (FASCIA's records too) */
        for (int j = 0; j < DGD_N; j++)
            RECORD_FMT(dgd_rid[j]) = (void *)dgd_fns[j];
    if (kind == PLT_KIND)                       /* RIFT v0.17: PLATEAU's (FASCIA's records too) */
        for (int j = 0; j < PLT_N; j++)
            RECORD_FMT(plt_rid[j]) = (void *)plt_fns[j];
    if (kind == CTR_KIND)                       /* RIFT v0.20: CONTOUR's (FASCIA's records too) */
        for (int j = 0; j < CTR_N; j++)
            RECORD_FMT(ctr_rid[j]) = (void *)ctr_fns[j];
    if (kind == SPL_KIND)                       /* RIFT v0.25: SPALL's (FASCIA's records too) */
        for (int j = 0; j < SPL_N; j++)
            RECORD_FMT(spl_rid[j]) = (void *)spl_fns[j];
}

/* v0.48 (impbox, the owner: "exact dt2"): STRT, LEN and LOOP as the DT2's own controls.
 * Its 1.17 OS gives them fine-resolution records (range 0x7800 = 120.00, LEN's default
 * 120.00, the fine flag set), so the knob moves in 1/256 and the screen shows 0.00..120.00.
 * The DN2's own fine controls (FREQ, record 36) are the reference: while the active track is
 * ONESHOT (all three), STRETCH, REPITCH or BOUNCE (STRT and LEN), records 239/258/257 get
 * that range, default and flag, FREQ's value type (the 4 words at +4 of its runtime entry,
 * which the knob step 0x4011336e reads: 1/256 a count, push for whole steps) and FREQ's
 * two-decimal formatter (0x400e2ef6, generic); otherwise the stock words go back, so
 * WaveTone, GRID and SLICE see exactly what they had. To pull this out: drop the call above
 * (the records are never touched) and ctl_pos in dnfw.sampler.program (back to ctl). */
#define POS_RANGE 0x7800
#define FINE_REF 36u                            /* FREQ: stock's fine unipolar control */
#define REC_W(id) ((int *)(0x401F7F94u + 60u * (id)))
#define ENTRY_TYPE(id) ((u32 *)(0x4243325Cu + 68u * (id) + 4u))   /* the value type, 4 words */
static const u16 pos_ids[3] = {SMP_STRT_ID, SMP_LEN_ID, SMP_LOOP_ID};
static int pos_rec[3][3] __attribute__((section(".data")));   /* stock range, default, flag */
static u32 pos_type[3][4] __attribute__((section(".data")));
static void *pos_fmt[3] __attribute__((section(".data")));
static int pos_saved __attribute__((section(".data"))) = 0;
int smp_fine_on __attribute__((section(".data"))) = 0;   /* which of the three are fine now (bits) */

int smp_fine_mask(int kind)
{
    if (kind == SMP_KIND0)
        return 7;                               /* ONESHOT: STRT, LEN, LOOP */
    if (kind == SMP_STRETCH_KIND || kind == SMP_REPITCH_KIND || kind == SMP_BOUNCE_KIND)
        return 3;                               /* STRT, LEN */
    return 0;
}

void smp_fine(int kind)
{
    if (!pos_saved) {
        for (int k = 0; k < 3; k++) {
            int *r = REC_W(pos_ids[k]);
            pos_rec[k][0] = r[3];
            pos_rec[k][1] = r[4];
            pos_rec[k][2] = r[5];
            for (int j = 0; j < 4; j++)
                pos_type[k][j] = ENTRY_TYPE(pos_ids[k])[j];
            pos_fmt[k] = RECORD_FMT(pos_ids[k]);
        }
        pos_saved = 1;
    }
    int mask = smp_fine_mask(kind);
    for (int k = 0; k < 3; k++) {
        u32 id = pos_ids[k];
        int *r = REC_W(id);
        if (mask & (1 << k)) {
            r[3] = POS_RANGE;
            r[4] = id == SMP_LEN_ID ? POS_RANGE : 0;
            r[5] = REC_W(FINE_REF)[5];
            for (int j = 0; j < 4; j++)
                ENTRY_TYPE(id)[j] = ENTRY_TYPE(FINE_REF)[j];
            RECORD_FMT(id) = RECORD_FMT(FINE_REF);
        } else if (smp_fine_on & (1 << k)) {
            r[3] = pos_rec[k][0];
            r[4] = pos_rec[k][1];
            r[5] = pos_rec[k][2];
            for (int j = 0; j < 4; j++)
                ENTRY_TYPE(id)[j] = pos_type[k][j];
            if (RECORD_FMT(id) == RECORD_FMT(FINE_REF))
                RECORD_FMT(id) = pos_fmt[k];    /* (smp_formats has set GRID's/SLICE's own) */
        }
    }
    smp_fine_on = mask;
}
