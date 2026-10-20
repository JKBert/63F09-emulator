-- Test bench of SoC09 for the co-simulation with the emulator : clock, reset, and a memory on the external bus (EXT0).
-- It prints one line per cycle of the external bus, in the same format as `soc63f09 --trace-bus` :
--   ext A=<hex 9> mask=<hex 2> R|W D=<hex 16>
-- ext.hex holds the content of the external memory (one byte per line, from physical address F00000000).

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;

use work.MUX_74F150_PKG.all;
use work.SoC09_PKG.all;

entity tb_soc is
end entity;

architecture sim of tb_soc is
    constant EXT_SIZE : integer := 65536;
    type EXT_T is array(0 to EXT_SIZE - 1) of std_logic_vector(7 downto 0);

    impure function LOAD return EXT_T is
        file F      : text open read_mode is "ext.hex";
        variable L  : line;
        variable M  : EXT_T := (others => x"00");
        variable V  : std_logic_vector(7 downto 0);
        variable I  : integer := 0;
    begin
        while not endfile(F) and I < EXT_SIZE loop
            readline(F, L);
            hread(L, V);
            M(I) := V;
            I := I + 1;
        end loop;
        return M;
    end function;

    signal EXTAL, RESET_n                       : std_logic := '0';
    signal E, BA, BS, RW_n, Q, VMA              : std_logic;
    signal ADDR                                 : std_logic_vector(35 downto 3);
    signal DATA                                 : std_logic_vector(63 downto 0);
    signal BYTE_MASK                            : std_logic_vector(7 downto 0);
    signal CPUCLK, SYSCLK, MEMCLK, FIC          : std_logic;
    signal PIA_PORT_DATA                        : std_logic_matrix(0 to 4)(7 downto 0);
    signal PIA_C1                               : std_logic_vector(0 to 4) := (others => '0');
    signal PIA_C2                               : std_logic_vector(0 to 4);
    signal ACIA_RX                              : std_logic_vector(0 to 1) := "11";
    signal ACIA_TX, ACIA_RTS_n                  : std_logic_vector(0 to 1);
    signal ACIA_CTS_n, ACIA_DCD_n               : std_logic_vector(0 to 1) := "00";
    signal PTM_O                                : std_logic_matrix(0 to 1)(1 to 3);
    signal PTM_C_n                              : std_logic_matrix(0 to 1)(1 to 3) := (others => "111");
    signal PTM_G_n                              : std_logic_matrix(0 to 1)(1 to 3) := (others => "000");
    signal SPI_MISO, SPI_MOSI, SPI_SCLK         : std_logic;
    signal SPI_SS                               : std_logic_vector(15 downto 0) := (others => '1');
    signal TWI_SDA, TWI_SCL                     : std_logic := '1';
begin
    EXTAL <= not EXTAL after 20850 ps;                          -- 24 MHz (41.7 ns : the PLL divides it exactly)
    RESET_n <= '1' after 417 ns;                                -- ten periods

    DUT : SoC09
    port map
    (
        EXTAL => EXTAL, RESET_n => RESET_n, NMI_n => '1', FIRQ_n => '1', IRQ_n => '1',
        MRDY => '1', DMA_BREQ_n => '1', HALT_n => '1',
        E => E, BA => BA, BS => BS, RW_n => RW_n, Q => Q,
        ADDR => ADDR, DATA => DATA, EXT_EIRQ_n => x"FF",
        CPUCLK => CPUCLK, SYSCLK => SYSCLK, MEMCLK => MEMCLK, FIC => FIC, VMA => VMA, BYTE_MASK => BYTE_MASK,
        PIA_PORT_DATA => PIA_PORT_DATA, PIA_C1 => PIA_C1, PIA_C2 => PIA_C2,
        ACIA_RX => ACIA_RX, ACIA_TX => ACIA_TX, ACIA_RTS_n => ACIA_RTS_n,
        ACIA_CTS_n => ACIA_CTS_n, ACIA_DCD_n => ACIA_DCD_n,
        PTM_O => PTM_O, PTM_C_n => PTM_C_n, PTM_G_n => PTM_G_n,
        SPI_MISO => SPI_MISO, SPI_MOSI => SPI_MOSI, SPI_SS => SPI_SS, SPI_SCLK => SPI_SCLK,
        TWI_SDA => TWI_SDA, TWI_SCL => TWI_SCL
    );

    -- the companion : 64-bit lines, the lane of a byte is given by BYTE_MASK. The data pins are driven on a read
    -- (all ones when nothing is read) and released during a write, when the SoC drives them.
    COMPANION : process(ADDR, E, RW_n, VMA, BA, DATA) is
        variable MEM  : EXT_T := LOAD;
        variable BASE : integer;
        variable V    : std_logic_vector(63 downto 0);
        variable L    : line;
        variable A36  : std_logic_vector(35 downto 0);
    begin
        BASE := to_integer(unsigned(ADDR(15 downto 3))) * 8;
        if ADDR(35 downto 16) /= x"F0000" then
            BASE := -1;
        end if;
        if RW_n = '0' then
            DATA <= (others => 'Z');
        elsif VMA = '1' then
            V := (others => '1');
            if BASE >= 0 then
                for I in 0 to 7 loop
                    V(8 * I + 7 downto 8 * I) := MEM(BASE + I);
                end loop;
            end if;
            DATA <= V;
        else
            DATA <= (others => '1');
        end if;
        if falling_edge(E) and VMA = '1' and BA = '0' then
            write(L, string'("ext A="));
            A36 := std_logic_vector'(ADDR & "000");
            hwrite(L, A36);
            write(L, string'(" mask="));
            hwrite(L, BYTE_MASK);
            if RW_n = '1' then
                write(L, string'(" R D="));
            else
                write(L, string'(" W D="));
            end if;
            hwrite(L, DATA);
            writeline(output, L);
            if RW_n = '0' and BASE >= 0 then
                for I in 0 to 7 loop
                    if BYTE_MASK(I) = '1' then
                        MEM(BASE + I) := DATA(8 * I + 7 downto 8 * I);
                    end if;
                end loop;
            end if;
        end if;
    end process;

    -- the transmit lines of the ACIAs : instant (ps) and level of each change
    TXLOG : process(ACIA_TX) is
        variable L : line;
    begin
        write(L, string'("tx "));
        write(L, now / 1 ps);
        write(L, string'(" "));
        write(L, std_logic'image(ACIA_TX(0)));
        write(L, string'(" "));
        write(L, std_logic'image(ACIA_TX(1)));
        writeline(output, L);
    end process;

    CLKLOG : process(E, SYSCLK, CPUCLK, MEMCLK) is
        variable L : line;
    begin
        write(L, string'("clk "));
        write(L, now / 1 ps);
        write(L, string'(" E="));
        write(L, std_logic'image(E));
        write(L, string'(" SYSCLK="));
        write(L, std_logic'image(SYSCLK));
        write(L, string'(" CPUCLK="));
        write(L, std_logic'image(CPUCLK));
        write(L, string'(" MEMCLK="));
        write(L, std_logic'image(MEMCLK));
        writeline(output, L);
    end process;

    -- ACIA 0 seen from outside, sampled every nanosecond (VHDL-2008 external names)
    A0LOG : process is
        variable L    : line;
        variable LAST : string(1 to 160) := (others => ' ');
        variable S, T, C : std_logic_vector(7 downto 0);
        variable TC : std_logic_vector(5 downto 0);
        variable CC, CD : std_logic_vector(15 downto 0);
        variable BD, AR, TR, TXC, TXCD, TXCE : std_logic;
        variable CUR  : line;
    begin
        wait for 100 ps;
        S := << signal .tb_soc.dut.acia0.status_reg : std_logic_vector(7 downto 0) >>;
        T := << signal .tb_soc.dut.acia0.tx_data_reg : std_logic_vector(7 downto 0) >>;
        C := << signal .tb_soc.dut.acia0.control_reg : std_logic_vector(7 downto 0) >>;
        TC := << signal .tb_soc.dut.acia0.txclkcnt : std_logic_vector(5 downto 0) >>;
        CC := << signal .tb_soc.dut.acia0.clockcnt : std_logic_vector(15 downto 0) >>;
        CD := << signal .tb_soc.dut.acia0.clockdiv : std_logic_vector(15 downto 0) >>;
        BD := << signal .tb_soc.dut.acia0.txbdclk : std_logic >>;
        AR := << signal .tb_soc.dut.acia0.ac_rst : std_logic >>;
        TR := << signal .tb_soc.dut.acia0.tx_rst : std_logic >>;
        TXC := << signal .tb_soc.dut.acia0.txc : std_logic >>;
        TXCD := << signal .tb_soc.dut.acia0.txcdel : std_logic >>;
        TXCE := << signal .tb_soc.dut.acia0.txcedge : std_logic >>;
        write(CUR, string'(" rst="));
        write(CUR, std_logic'image(AR) & std_logic'image(TR) & std_logic'image(TXC) & std_logic'image(TXCD) & std_logic'image(TXCE));
        write(CUR, string'(" txclkcnt="));
        hwrite(CUR, "00" & TC);
        write(CUR, string'(" clockcnt="));
        hwrite(CUR, CC);
        write(CUR, string'(" clockdiv="));
        hwrite(CUR, CD);
        write(CUR, string'(" txbdclk="));
        write(CUR, std_logic'image(BD));
        write(CUR, string'(" status="));
        hwrite(CUR, S);
        write(CUR, string'(" txdata="));
        hwrite(CUR, T);
        write(CUR, string'(" control="));
        hwrite(CUR, C);
        if CUR.all /= LAST(1 to CUR.all'length) then
            LAST(1 to CUR.all'length) := CUR.all;
            write(L, string'("acia "));
            write(L, now / 1 ps);
            write(L, CUR.all);
            writeline(output, L);
        end if;
        deallocate(CUR);
    end process;
end architecture;
