-- The I2C EEPROM of the co-simulation : same behaviour as src/soc/i2c_eeprom.c (24C02-like, 256 bytes, no timing).
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity I2C_EEPROM is
    generic
    (
        ADDR7   : std_logic_vector(6 downto 0) := "1010000"
    );
    port
    (
        SDA     : inout std_logic;
        SCL     : in    std_logic
    );
end entity;

architecture BEHAVIOUR of I2C_EEPROM is
    type MEM_T is array(0 to 255) of std_logic_vector(7 downto 0);
    type PHASE_T is (IDLE, ADDRESS, WORD, WDATA, RDATA);
    signal PULL : std_logic := '0';
begin
    SDA <= '0' when PULL = '1' else 'Z';

    process(SDA, SCL) is
        variable MEM     : MEM_T := (others => x"FF");
        variable PHASE   : PHASE_T := IDLE;
        variable NEXT_P  : PHASE_T := IDLE;
        variable CNT     : integer := 0;
        variable SHIFT   : std_logic_vector(7 downto 0) := (others => '0');
        variable PTR     : integer := 0;
        variable TX      : std_logic_vector(7 downto 0) := (others => '0');
        variable MACK    : boolean := false;
        variable ACK     : boolean;

        procedure DRIVE(K : integer) is
        begin
            if TX(7 - K) = '1' then
                PULL <= '0';
            else
                PULL <= '1';
            end if;
        end procedure;
    begin
        if to_x01(SCL) = '1' and falling_edge(SDA) then
            PHASE := ADDRESS;
            CNT := 0;
            SHIFT := (others => '0');
            PULL <= '0';
        elsif to_x01(SCL) = '1' and rising_edge(SDA) then
            PHASE := IDLE;
            PULL <= '0';
        elsif PHASE /= IDLE then
            if rising_edge(SCL) then
                if CNT < 8 and PHASE /= RDATA then
                    SHIFT := SHIFT(6 downto 0) & to_x01(SDA);
                elsif CNT = 8 and PHASE = RDATA then
                    MACK := to_x01(SDA) = '0';
                end if;
                CNT := CNT + 1;
            elsif falling_edge(SCL) then
                if PHASE /= RDATA and CNT = 8 then
                    ACK := false;
                    case PHASE is
                        when ADDRESS =>
                            if SHIFT(7 downto 1) = ADDR7 then
                                ACK := true;
                                if SHIFT(0) = '1' then
                                    NEXT_P := RDATA;
                                else
                                    NEXT_P := WORD;
                                end if;
                            end if;
                        when WORD =>
                            PTR := to_integer(unsigned(SHIFT));
                            ACK := true;
                            NEXT_P := WDATA;
                        when others =>
                            MEM(PTR) := SHIFT;
                            PTR := (PTR + 1) mod 256;
                            ACK := true;
                            NEXT_P := WDATA;
                    end case;
                    if ACK then
                        PULL <= '1';
                    else
                        PHASE := IDLE;
                    end if;
                elsif PHASE /= RDATA and CNT = 9 then
                    PULL <= '0';
                    CNT := 0;
                    SHIFT := (others => '0');
                    PHASE := NEXT_P;
                    if PHASE = RDATA then
                        TX := MEM(PTR);
                        DRIVE(0);
                    end if;
                elsif PHASE = RDATA then
                    if CNT >= 1 and CNT <= 7 then
                        DRIVE(CNT);
                    elsif CNT = 8 then
                        PULL <= '0';
                    elsif CNT = 9 then
                        CNT := 0;
                        if MACK then
                            PTR := (PTR + 1) mod 256;
                            TX := MEM(PTR);
                            DRIVE(0);
                        else
                            PHASE := IDLE;
                            PULL <= '0';
                        end if;
                    end if;
                end if;
            end if;
        end if;
    end process;
end architecture;
