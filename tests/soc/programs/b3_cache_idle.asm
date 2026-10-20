; FINDINGS B3 : E stops while the core runs from its instruction cache, and the PTM (and every peripheral clocked
; on E) stops with it. Timer 1 of PTM 0 is started with a latch of 4 and its interrupt enabled, then the core loops.
;
; Loop A (below, default)  : BRA * -- no bus cycle, E stops, the timer never times out, the handler never runs
;                            (marker at $00001000 stays 0).
; Loop B (comment out A, uncomment B) : the loop reads a PTM register -- bus cycles keep E running, the timer times
;                            out, the interrupt is taken, the handler counts in the marker (non-zero).
; Same behaviour in GHDL (tests/ghdl/cosim.py : A = 63 bus cycles in 80 us, B = 680).
;
; Machine code assembled by hand (elf/b3_loopA.elf, elf/b3_loopB.elf), 32-bit mode as the gcc runtime.

PTM0    EQU     $FFFED000
MARKER  EQU     $00001000

        ORG     $FFFFF000
START:  LDMD    #$31                ; 32-bit mode
        LDS     #$FFFCFFF0          ; stack in the internal RAM
        LDA     #$00
        STA     MARKER              ; clear the marker (external memory)
        LDA     #$01
        STA     PTM0+1              ; CR2 bit 0 = 1 : address 0 is CR1
        LDA     #$01
        STA     PTM0+0              ; CR1 = 1 : all timers held in preset
        LDA     #$00
        STA     PTM0+2              ; latch of timer 1, MSB
        LDA     #$04
        STA     PTM0+3              ; latch of timer 1, LSB
        LDA     #$C2                ; CR1 of timer 1 : output enabled, IRQ enabled, SYSCLK, continuous, run
        STA     PTM0+0
        ANDCC   #$EF                ; unmask IRQ (one byte)
LOOPA:  BRA     LOOPA               ; loop A : executes from the cache, no bus cycle
;LOOPB: LDA     PTM0+1              ; loop B : a PTM read in the loop, bus cycles keep E running
;       BRA     LOOPB
        NOP                         ; some NOPs after the loop (16 in the ELFs)
        NOP

        ORG     $FFFFF200
HANDLER:
        LDA     MARKER
        ADDA    #$01
        STA     MARKER              ; count the interrupts
        LDA     PTM0+1              ; status
        LDA     PTM0+3              ; read of the LSB clears the flag of timer 1
        RTI

        ORG     $FFFFFFEA
        FDB     HANDLER             ; EIRQ21 = PTM 0
        ORG     $FFFFFFFE
        FDB     START               ; reset
        END
