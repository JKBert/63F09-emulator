/*
 * vwide : vectors wider than 64 bits.
 *
 * A value is a vs_w (little-endian words, up to VS_WIDE_WORDS * 64 bits) ; a signal is an array of
 * vs_sig, one per 64-bit word. The width is not part of the value : the operations that need it
 * (not, shifts, arithmetic) take it, and keep the bits above it at 0.
 */

#ifndef VWIDE_H
#define VWIDE_H

#include "vsim.h"

#define VS_WIDE_WORDS 8

typedef struct vs_w
{
    uint64_t    w[VS_WIDE_WORDS];
} vs_w;

/* Storage of a signal of NW words (2 <= NW <= VS_WIDE_WORDS). */
typedef struct { vs_sig w[2]; } vs_sigw2;
typedef struct { vs_sig w[3]; } vs_sigw3;
typedef struct { vs_sig w[4]; } vs_sigw4;
typedef struct { vs_sig w[5]; } vs_sigw5;
typedef struct { vs_sig w[6]; } vs_sigw6;
typedef struct { vs_sig w[7]; } vs_sigw7;
typedef struct { vs_sig w[8]; } vs_sigw8;

static inline vs_w vs_w_zero(void)
{
    vs_w r;
    int  i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        r.w[i] = 0;
    }
    return r;
}

static inline vs_w vs_w_from(uint64_t v)
{
    vs_w r = vs_w_zero();

    r.w[0] = v;
    return r;
}

static inline vs_w vs_w_from_signed(int64_t v, unsigned width)
{
    vs_w r = vs_w_zero();
    int  i;

    r.w[0] = (uint64_t) v;
    for (i = 1; i < VS_WIDE_WORDS; i++)
    {
        r.w[i] = v < 0 ? UINT64_MAX : 0;
    }
    (void) width;
    return r;
}

static inline uint64_t vs_w_u64(vs_w a)
{
    return a.w[0];
}

/* Clears the bits at and above `width`. */
static inline vs_w vs_w_trim(vs_w a, unsigned width)
{
    unsigned i, nw = (width + 63) / 64;

    for (i = nw; i < VS_WIDE_WORDS; i++)
    {
        a.w[i] = 0;
    }
    if (width % 64 != 0 && nw > 0)
    {
        a.w[nw - 1] &= (UINT64_C(1) << (width % 64)) - 1;
    }
    return a;
}

static inline vs_w vs_w_and(vs_w a, vs_w b)
{
    int i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        a.w[i] &= b.w[i];
    }
    return a;
}

static inline vs_w vs_w_or(vs_w a, vs_w b)
{
    int i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        a.w[i] |= b.w[i];
    }
    return a;
}

static inline vs_w vs_w_xor(vs_w a, vs_w b)
{
    int i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        a.w[i] ^= b.w[i];
    }
    return a;
}

static inline vs_w vs_w_not(vs_w a, unsigned width)
{
    int i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        a.w[i] = ~a.w[i];
    }
    return vs_w_trim(a, width);
}

static inline vs_w vs_w_shl(vs_w a, int64_t n, unsigned width)
{
    vs_w     r = vs_w_zero();
    int      i;
    unsigned ws, bs;

    if (n < 0 || n >= (int64_t) width)
    {
        return r;
    }
    ws = (unsigned) n / 64;
    bs = (unsigned) n % 64;
    for (i = VS_WIDE_WORDS - 1; i >= (int) ws; i--)
    {
        r.w[i] = a.w[i - ws] << bs;
        if (bs != 0 && i - (int) ws - 1 >= 0)
        {
            r.w[i] |= a.w[i - ws - 1] >> (64 - bs);
        }
    }
    return vs_w_trim(r, width);
}

static inline vs_w vs_w_shr(vs_w a, int64_t n)
{
    vs_w     r = vs_w_zero();
    int      i;
    unsigned ws, bs;

    if (n < 0 || n >= 64 * VS_WIDE_WORDS)
    {
        return r;
    }
    ws = (unsigned) n / 64;
    bs = (unsigned) n % 64;
    for (i = 0; i + (int) ws < VS_WIDE_WORDS; i++)
    {
        r.w[i] = a.w[i + ws] >> bs;
        if (bs != 0 && i + (int) ws + 1 < VS_WIDE_WORDS)
        {
            r.w[i] |= a.w[i + ws + 1] << (64 - bs);
        }
    }
    return r;
}

static inline vs_w vs_w_add(vs_w a, vs_w b, unsigned width)
{
    int      i;
    uint64_t carry = 0;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        uint64_t s = a.w[i] + b.w[i];
        uint64_t c1 = s < a.w[i];
        uint64_t s2 = s + carry;
        uint64_t c2 = s2 < s;

        a.w[i] = s2;
        carry = c1 | c2;
    }
    return vs_w_trim(a, width);
}

static inline vs_w vs_w_neg(vs_w a, unsigned width)
{
    return vs_w_add(vs_w_not(a, 64 * VS_WIDE_WORDS), vs_w_from(1), width);
}

static inline vs_w vs_w_sub(vs_w a, vs_w b, unsigned width)
{
    return vs_w_add(a, vs_w_neg(b, 64 * VS_WIDE_WORDS), width);
}

/* Product truncated to `width` bits (schoolbook on 32-bit limbs). */
static inline vs_w vs_w_mul(vs_w a, vs_w b, unsigned width)
{
    uint32_t x[2 * VS_WIDE_WORDS], y[2 * VS_WIDE_WORDS], z[2 * VS_WIDE_WORDS];
    vs_w     r;
    int      i, j;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        x[2 * i] = (uint32_t) a.w[i];
        x[2 * i + 1] = (uint32_t) (a.w[i] >> 32);
        y[2 * i] = (uint32_t) b.w[i];
        y[2 * i + 1] = (uint32_t) (b.w[i] >> 32);
    }
    for (i = 0; i < 2 * VS_WIDE_WORDS; i++)
    {
        z[i] = 0;
    }
    for (i = 0; i < 2 * VS_WIDE_WORDS; i++)
    {
        uint64_t carry = 0;

        for (j = 0; i + j < 2 * VS_WIDE_WORDS; j++)
        {
            uint64_t t = (uint64_t) x[i] * y[j] + z[i + j] + carry;

            z[i + j] = (uint32_t) t;
            carry = t >> 32;
        }
    }
    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        r.w[i] = (uint64_t) z[2 * i] | ((uint64_t) z[2 * i + 1] << 32);
    }
    return vs_w_trim(r, width);
}

static inline int vs_w_eq(vs_w a, vs_w b)
{
    int i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        if (a.w[i] != b.w[i])
        {
            return 0;
        }
    }
    return 1;
}

static inline int vs_w_ult(vs_w a, vs_w b)
{
    int i;

    for (i = VS_WIDE_WORDS - 1; i >= 0; i--)
    {
        if (a.w[i] != b.w[i])
        {
            return a.w[i] < b.w[i];
        }
    }
    return 0;
}

static inline int vs_w_is_zero(vs_w a)
{
    int i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        if (a.w[i] != 0)
        {
            return 0;
        }
    }
    return 1;
}

static inline vs_w vs_w_ones(unsigned width)
{
    vs_w r;
    int  i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        r.w[i] = UINT64_MAX;
    }
    return vs_w_trim(r, width);
}

static inline uint64_t vs_w_parity(vs_w a)
{
    uint64_t p = 0;
    int      i;

    for (i = 0; i < VS_WIDE_WORDS; i++)
    {
        p ^= vs_parity(a.w[i]);
    }
    return p;
}

/* Bit i, and the `width` bits from bit `lo` (as a wide value, then as a 64-bit one when width <= 64). */
static inline uint64_t vs_w_bit(vs_w a, unsigned i)
{
    return i < 64 * VS_WIDE_WORDS ? (a.w[i / 64] >> (i % 64)) & 1 : 0;
}

static inline vs_w vs_w_slice(vs_w a, unsigned lo, unsigned width)
{
    return vs_w_trim(vs_w_shr(a, lo), width);
}

/* a (wa bits) & b (wb bits) */
static inline vs_w vs_w_cat(vs_w a, vs_w b, unsigned wb)
{
    return vs_w_or(vs_w_shl(a, wb, 64 * VS_WIDE_WORDS), b);
}

/* Replaces the `width` bits of a from bit `lo` by the low bits of v. */
static inline vs_w vs_w_set(vs_w a, unsigned lo, unsigned width, vs_w v)
{
    vs_w m = vs_w_shl(vs_w_ones(width), lo, 64 * VS_WIDE_WORDS);

    return vs_w_or(vs_w_and(a, vs_w_not(m, 64 * VS_WIDE_WORDS)), vs_w_and(vs_w_shl(v, lo, 64 * VS_WIDE_WORDS), m));
}

/* Signals of NW words. */
static inline vs_w vs_w_get(const vs_sig *s, unsigned nw)
{
    vs_w     r = vs_w_zero();
    unsigned i;

    for (i = 0; i < nw; i++)
    {
        r.w[i] = s[i].cur;
    }
    return r;
}

static inline void vs_w_drive(vs_sig *s, unsigned nw, vs_w v)
{
    unsigned i;

    for (i = 0; i < nw; i++)
    {
        vs_drive(&s[i], v.w[i]);
    }
}

static inline void vs_w_register(vs_kernel *k, vs_sig *s, unsigned nw, vs_w v)
{
    unsigned i;

    for (i = 0; i < nw; i++)
    {
        vs_register_signal(k, &s[i], v.w[i]);
    }
}

/* Drives the `width` bits from bit `lo` of a wide signal ; the other bits keep what is being driven. */
static inline void vs_w_drive_bits(vs_sig *s, unsigned nw, unsigned lo, unsigned width, vs_w v)
{
    vs_w     nxt = vs_w_zero();
    unsigned i;

    for (i = 0; i < nw; i++)
    {
        nxt.w[i] = s[i].nxt;
    }
    nxt = vs_w_set(nxt, lo, width, v);
    for (i = 0; i < nw; i++)
    {
        vs_drive(&s[i], nxt.w[i]);
    }
}

#endif
