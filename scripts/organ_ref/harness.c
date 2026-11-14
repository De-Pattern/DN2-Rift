/* Ravel's ORGAN (rv_synth.c organ_note/organ_render, unchanged), compiled natively at 48 kHz and
 * 32-sample blocks: the reference RIFT's port is checked against. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rv_dsp.h"
#define RV_FS 48000
#define RV_SUB 32
enum { TP_S0, TP_S1, TP_S2, TP_S3, TP_S4, TP_S5, TP_S6, TP_S7, TP_S8, TP_S9, TP_S10, TP_S11, TP_S12, TP_S13, TP_S14, TP_S15 };
typedef struct { float ph[8], dly[8], cents[8], t, chiff, air_lp, wind, wind_v, trem_ph; svf_t ch; uint32_t ns; } organ_t;
typedef struct { uint32_t rng; union { organ_t og; } e; } voice_t;
#include "organ_body.c"
/* usage: harness SEED NOTE SECONDS s0..s15  -> raw float32 samples on stdout (the engine's buffer,
 * before Ravel's voice_post: no envelope, filter or trim) */
int main(int argc, char **argv)
{
    if (argc < 20) { fprintf(stderr, "usage: harness seed note seconds s0..s15\n"); return 2; }
    voice_t v; memset(&v, 0, sizeof v);
    v.rng = (uint32_t)strtoul(argv[1], 0, 0);
    float note = (float)atof(argv[2]), secs = (float)atof(argv[3]), eff[16], buf[RV_SUB];
    for (int k = 0; k < 16; k++) eff[k] = (float)atof(argv[4 + k]);
    float f = note_hz(note);
    organ_note(&v, eff);
    int blocks = (int)(secs * RV_FS / RV_SUB);
    for (int b = 0; b < blocks; b++) {
        organ_render(&v, eff, f, buf, RV_SUB);
        fwrite(buf, sizeof(float), RV_SUB, stdout);
    }
    return 0;
}
