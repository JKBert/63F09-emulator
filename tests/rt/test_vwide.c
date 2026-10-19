/* Unit test of the wide vector operations against the native 128-bit arithmetic of the compiler. */

#include <stdio.h>
#include <stdlib.h>

#include "vwide.h"

typedef unsigned __int128 u128;

static uint64_t rnd64(void)
{
    return ((uint64_t) rand() << 40) ^ ((uint64_t) rand() << 20) ^ (uint64_t) rand() ^ ((uint64_t) rand() << 60);
}

static vs_w to_w(u128 v)
{
    vs_w r = vs_w_zero();

    r.w[0] = (uint64_t) v;
    r.w[1] = (uint64_t) (v >> 64);
    return r;
}

static u128 from_w(vs_w w)
{
    return ((u128) w.w[1] << 64) | w.w[0];
}

static u128 mask128(unsigned width)
{
    return width >= 128 ? ~(u128) 0 : (((u128) 1 << width) - 1);
}

#define CHECK(cond) do { if (!(cond)) { printf("FAIL %s:%d : %s\n", __FILE__, __LINE__, #cond); fails++; } } while (0)

int main(void)
{
    int      fails = 0, n;

    srand(1);
    for (n = 0; n < 20000; n++)
    {
        u128     a = ((u128) rnd64() << 64) | rnd64();
        u128     b = ((u128) rnd64() << 64) | rnd64();
        unsigned width = 65 + (unsigned) (rand() % 64);
        unsigned lo = (unsigned) (rand() % 100), sw = 1 + (unsigned) (rand() % 60);
        int64_t  sh = rand() % 140;
        u128     m = mask128(width);

        a &= m;
        b &= m;
        CHECK(from_w(vs_w_add(to_w(a), to_w(b), width)) == ((a + b) & m));
        CHECK(from_w(vs_w_sub(to_w(a), to_w(b), width)) == ((a - b) & m));
        CHECK(from_w(vs_w_mul(to_w(a), to_w(b), width)) == ((a * b) & m));
        CHECK(from_w(vs_w_and(to_w(a), to_w(b))) == (a & b));
        CHECK(from_w(vs_w_or(to_w(a), to_w(b))) == (a | b));
        CHECK(from_w(vs_w_xor(to_w(a), to_w(b))) == (a ^ b));
        CHECK(from_w(vs_w_not(to_w(a), width)) == (~a & m));
        CHECK(from_w(vs_w_neg(to_w(a), width)) == ((~a + 1) & m));
        CHECK(from_w(vs_w_shl(to_w(a), sh, width)) == (sh >= (int64_t) width ? 0 : ((a << sh) & m)));
        CHECK(from_w(vs_w_shr(to_w(a), sh)) == (sh >= 128 ? 0 : (a >> sh)));
        CHECK(vs_w_eq(to_w(a), to_w(b)) == (a == b));
        CHECK(vs_w_ult(to_w(a), to_w(b)) == (a < b));
        CHECK(vs_w_bit(to_w(a), lo) == (uint64_t) ((a >> lo) & 1));
        CHECK(from_w(vs_w_slice(to_w(a), lo, sw)) == ((a >> lo) & mask128(sw)));
        CHECK(vs_w_parity(to_w(a)) == (uint64_t) __builtin_parityll((uint64_t) a ^ (uint64_t) (a >> 64)));
        if (lo + sw <= 128)
        {
            u128 v = b & mask128(sw);
            u128 expect = (a & ~(mask128(sw) << lo)) | (v << lo);

            CHECK(from_w(vs_w_set(to_w(a), lo, sw, to_w(v))) == expect);
        }
    }
    /* signed helpers, against the native signed 128-bit arithmetic */
    for (n = 0; n < 20000; n++)
    {
        unsigned width = 65 + (unsigned) (rand() % 63);
        u128     m = mask128(width);
        u128     a = (((u128) rnd64() << 64) | rnd64()) & m;
        u128     b = (((u128) rnd64() << 64) | rnd64()) & m;
        __int128 sa = (__int128) (a << (128 - width)) >> (128 - width);
        __int128 sb = (__int128) (b << (128 - width)) >> (128 - width);
        int64_t  sh = rand() % 140;

        CHECK(vs_w_slt(to_w(a), to_w(b), width) == (sa < sb));
        CHECK(from_w(vs_w_sext(to_w(a), width)) == (u128) sa);
        CHECK(from_w(vs_w_sar(to_w(a), sh, width)) == (((u128) (sh >= 127 ? (sa < 0 ? (__int128) -1 : 0) : (sa >> sh))) & m));
    }
    printf(fails ? "vwide: %d FAILURES\n" : "vwide: OK\n", fails);
    return fails != 0;
}
