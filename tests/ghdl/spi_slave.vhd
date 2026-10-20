-- The SPI slave of the co-simulation : same behaviour as src/soc/spi_slave.c (mode 0, selected by SS0, answers each
-- byte with the byte received before it, 0xA5 for the first one).
library ieee;
use ieee.std_logic_1164.all;

entity SPI_SLAVE is
    port
    (
        SS      : in    std_logic;
        SCLK    : in    std_logic;
        MOSI    : in    std_logic;
        MISO    : inout std_logic
    );
end entity;

architecture BEHAVIOUR of SPI_SLAVE is
    signal PULL : std_logic := '0';
begin
    MISO <= '0' when PULL = '1' else 'Z';

    process(SS, SCLK) is
        variable RX   : std_logic_vector(7 downto 0) := (others => '0');
        variable TX   : std_logic_vector(7 downto 0) := (others => '0');
        variable LAST : std_logic_vector(7 downto 0) := x"A5";
        variable CNT  : integer := 0;

        procedure PRESENT is
        begin
            if TX(7 - CNT) = '0' then
                PULL <= '1';
            else
                PULL <= '0';
            end if;
        end procedure;
    begin
        if falling_edge(SS) then
            CNT := 0;
            RX := (others => '0');
            TX := LAST;
            PRESENT;
        elsif to_x01(SS) /= '0' then
            PULL <= '0';
        elsif rising_edge(SCLK) then
            RX := RX(6 downto 0) & to_x01(MOSI);
            CNT := CNT + 1;
            if CNT = 8 then
                LAST := RX;
            end if;
        elsif falling_edge(SCLK) then
            if CNT = 8 then
                CNT := 0;
                TX := LAST;
                RX := (others => '0');
            end if;
            PRESENT;
        end if;
    end process;
end architecture;
