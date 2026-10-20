/* Addresses of the 63F09 SoC as the core sees them (32 bits) : the physical address is 0xF followed by these 32 bits
 * (SoC.vhd). Register layouts are those of the headers of the VHDL files. */

#ifndef SOC_H
#define SOC_H

#define ROM_BASE        0xFFFF0000UL    /* ROM 27F512, 64 KiB, vectors in 0xFFFFFFC0 - 0xFFFFFFFF */
#define INTRAM_BASE     0xFFFC0000UL    /* internal RAM 61F512, 64 KiB */
#define EXTRAM_BASE     0x00000000UL    /* external bus (the emulator provides 16 MiB at physical 0xF00000000) */

#define PIA_BASE        0xFFFEF000UL    /* 2 bytes each, 5 PIAs */
#define ACIA0_BASE      0xFFFEE000UL    /* 4 bytes each */
#define ACIA1_BASE      0xFFFEE004UL
#define PTM0_BASE       0xFFFED000UL    /* 8 bytes each */
#define PTM1_BASE       0xFFFED008UL
#define SPI_BASE        0xFFFEC000UL
#define TWI_BASE        0xFFFEB000UL
#define BAC_BASE        0xFFFEA000UL
#define WDG_BASE        0xFFFE9000UL
#define MMU_BASE(n)     (0xFFFD0000UL + 0x1000UL * (n))

#define REG8(a)         (*(volatile unsigned char *) (a))

/* ACIA 63F50 : +0 status (read) / control (write), +1 data, +2 and +3 divisor of SYSCLK (16 bits).
 * Status : bit 0 receive data ready, bit 1 transmit buffer empty. Control 0x03 resets, 0x15 is 8N1 with /16.
 * The rate is 24 MHz / ((divisor + 1) * N), N = 1, 16 or 64 (control register) : a divisor of 12 with /16 gives
 * 115384 bauds, 0.16 % from 115200, the default of --acia (13 gives 107142). */
#define ACIA_STATUS(b)  REG8((b) + 0)
#define ACIA_CONTROL(b) REG8((b) + 0)
#define ACIA_DATA(b)    REG8((b) + 1)
#define ACIA_DIV_HI(b)  REG8((b) + 2)
#define ACIA_DIV_LO(b)  REG8((b) + 3)
#define ACIA_RDRF       0x01
#define ACIA_TDRE       0x02

#endif
