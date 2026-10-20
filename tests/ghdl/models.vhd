-- Behavioural VHDL models of the parts of the SoC that are built from vendor primitives. They stand for the
-- 27F512, 61F64x1 and 61F32x64 of the chip in the co-simulation with the emulator (cosim.py) : GHDL has no
-- RAMB18E1 / RAMB36E1 / PLLE2_BASE. They have the behaviour of the C models of src/hand (same ports, same
-- timing, READ_FIRST, one output latch per 16K block), so a difference between GHDL and the emulator comes from
-- the translated design, not from these parts.

library ieee;
use ieee.std_logic_1164.all;

package ROM_27F512_PKG is
    component ROM_27F512
        port
        (
            CLOCK         : in    std_logic;
            ROM_ENABLE    : in    std_logic;
            ADDRESS       : in    std_logic_vector(15 downto 0);
            DATA_OUTPUT   : out   std_logic_vector(7 downto 0);
            MRDY          : out   std_logic
        );
    end component;
end package ROM_27F512_PKG;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;

entity ROM_27F512 is
    port
    (
        CLOCK         : in    std_logic;
        ROM_ENABLE    : in    std_logic;
        ADDRESS       : in    std_logic_vector(15 downto 0);
        DATA_OUTPUT   : out   std_logic_vector(7 downto 0);
        MRDY          : out   std_logic
    );
end entity;

architecture BEHAVIOUR of ROM_27F512 is
    type MEM_T is array(0 to 65535) of std_logic_vector(7 downto 0);

    -- one hexadecimal byte per line in rom.hex (written by cosim.py)
    impure function LOAD return MEM_T is
        file F      : text open read_mode is "rom.hex";
        variable L  : line;
        variable M  : MEM_T := (others => x"FF");
        variable V  : std_logic_vector(7 downto 0);
        variable I  : integer := 0;
    begin
        while not endfile(F) and I < 65536 loop
            readline(F, L);
            hread(L, V);
            M(I) := V;
            I := I + 1;
        end loop;
        return M;
    end function;

    signal MEM   : MEM_T := LOAD;
    signal LATCH : std_logic_vector(7 downto 0) := (others => '0');
begin
    process(CLOCK) is
    begin
        if rising_edge(CLOCK) then
            if ROM_ENABLE = '1' then
                LATCH <= MEM(to_integer(unsigned(ADDRESS)));
            end if;
        end if;
    end process;
    DATA_OUTPUT <= LATCH when ROM_ENABLE = '1' else x"FF";
    MRDY <= '1';
end architecture;

library ieee;
use ieee.std_logic_1164.all;

package RAM_61F64x1_PKG is
    component   RAM_61F64x1
        port
        (
            MEMCLK          : in    std_logic;
            MEMCLK2         : in    std_logic;
            RW              : in    std_logic;
            RW2             : in    std_logic;
            ADDRESS         : in    std_logic_vector(15 downto 0);
            ADDRESS2        : in    std_logic_vector(15 downto 0);
            VALID_ADDR      : in    std_logic;
            VALID_ADDR2     : in    std_logic;
            DATA_IN         : in    std_logic;
            DATA_OUT        : out   std_logic;
            DATA_IN2        : in    std_logic;
            DATA_OUT2       : out   std_logic
        );
    end component;
end package RAM_61F64x1_PKG;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity RAM_61F64x1 is
    port
    (
        MEMCLK          : in    std_logic;
        MEMCLK2         : in    std_logic;
        RW              : in    std_logic;
        RW2             : in    std_logic;
        ADDRESS         : in    std_logic_vector(15 downto 0);
        ADDRESS2        : in    std_logic_vector(15 downto 0);
        VALID_ADDR      : in    std_logic;
        VALID_ADDR2     : in    std_logic;
        DATA_IN         : in    std_logic;
        DATA_OUT        : out   std_logic;
        DATA_IN2        : in    std_logic;
        DATA_OUT2       : out   std_logic
    );
end entity;

architecture BEHAVIOUR of RAM_61F64x1 is
    type MEM_T is array(0 to 65535) of std_logic;
    type LATCH_T is array(0 to 3) of std_logic;
    shared variable MEM : MEM_T := (others => '0');
    signal LATCH_A : LATCH_T := (others => '0');
    signal LATCH_B : LATCH_T := (others => '0');
begin
    -- one process for both ports : the two clocks may be the same signal, and port A goes first, as in the C model
    process(MEMCLK, MEMCLK2, ADDRESS, ADDRESS2) is
        variable A : integer;
    begin
        if rising_edge(MEMCLK) and VALID_ADDR = '1' then
            A := to_integer(unsigned(ADDRESS));
            LATCH_A(A / 16384) <= MEM(A);
            if RW = '1' then
                MEM(A) := DATA_IN;
            end if;
        end if;
        if rising_edge(MEMCLK2) and VALID_ADDR2 = '1' then
            A := to_integer(unsigned(ADDRESS2));
            LATCH_B(A / 16384) <= MEM(A);
            if RW2 = '1' then
                MEM(A) := DATA_IN2;
            end if;
        end if;
    end process;
    DATA_OUT  <= LATCH_A(to_integer(unsigned(ADDRESS(15 downto 14))));
    DATA_OUT2 <= LATCH_B(to_integer(unsigned(ADDRESS2(15 downto 14))));
end architecture;

library ieee;
use ieee.std_logic_1164.all;

package RAM_61F32x64_PKG is
    component   RAM_61F32x64
        port
        (
            RDCLK           : in    std_logic;
            WRCLK           : in    std_logic;
            WE              : in    std_logic;
            RDADDR          : in    std_logic_vector(8 downto 0);
            WRADDR          : in    std_logic_vector(8 downto 0);
            DATA_IN         : in    std_logic_vector(63 downto 0);
            DATA_OUT        : out   std_logic_vector(63 downto 0)
        );
    end component;
end package RAM_61F32x64_PKG;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity RAM_61F32x64 is
    port
    (
        RDCLK           : in    std_logic;
        WRCLK           : in    std_logic;
        WE              : in    std_logic;
        RDADDR          : in    std_logic_vector(8 downto 0);
        WRADDR          : in    std_logic_vector(8 downto 0);
        DATA_IN         : in    std_logic_vector(63 downto 0);
        DATA_OUT        : out   std_logic_vector(63 downto 0)
    );
end entity;

architecture BEHAVIOUR of RAM_61F32x64 is
    type MEM_T is array(0 to 511) of std_logic_vector(63 downto 0);
    shared variable MEM : MEM_T := (others => (others => '0'));
    signal OUTPUT : std_logic_vector(63 downto 0) := (others => '0');
begin
    process(RDCLK, WRCLK) is
    begin
        if rising_edge(RDCLK) then
            OUTPUT <= MEM(to_integer(unsigned(RDADDR)));
        end if;
        if rising_edge(WRCLK) and WE = '1' then
            MEM(to_integer(unsigned(WRADDR))) := DATA_IN;
        end if;
    end process;
    DATA_OUT <= OUTPUT;
end architecture;
