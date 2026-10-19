-- Declarations of the Xilinx primitives instantiated by the 63F09 sources, for analysis only.
-- Generated from the instantiations (tools/vhdl2c) ; the behaviour is modelled in C by hand.

library ieee;
use ieee.std_logic_1164.all;

package vcomponents is
    component BUFG
        port
        (
            I : in std_logic;
            O : out std_logic
        );
    end component;
    component BUFHCE
        generic
        (
            CE_TYPE : string := "SYNC"
        );
        port
        (
            CE : in std_logic;
            I : in std_logic;
            O : out std_logic
        );
    end component;
    component IOBUF
        generic
        (
            SLEW : string := "SLOW"
        );
        port
        (
            I : in std_logic;
            IO : inout std_logic;
            O : out std_logic;
            T : in std_logic
        );
    end component;
    component OBUF
        port
        (
            I : in std_logic;
            O : out std_logic
        );
    end component;
    component PLLE2_BASE
        generic
        (
            BANDWIDTH : string := "OPTIMIZED";
            CLKFBOUT_MULT : integer := 5;
            CLKFBOUT_PHASE : real := 0.0;
            CLKIN1_PERIOD : real := 0.0;
            CLKOUT0_DIVIDE : integer := 1;
            CLKOUT0_DUTY_CYCLE : real := 0.5;
            CLKOUT0_PHASE : real := 0.0;
            CLKOUT1_DIVIDE : integer := 1;
            CLKOUT1_DUTY_CYCLE : real := 0.5;
            CLKOUT1_PHASE : real := 0.0;
            DIVCLK_DIVIDE : integer := 1;
            REF_JITTER1 : real := 0.0;
            STARTUP_WAIT : string := "FALSE"
        );
        port
        (
            CLKFBIN : in std_logic;
            CLKIN1 : in std_logic;
            PWRDWN : in std_logic;
            RST : in std_logic;
            CLKFBOUT : out std_logic;
            CLKOUT0 : out std_logic;
            CLKOUT1 : out std_logic;
            LOCKED : out std_logic
        );
    end component;
    component RAMB18E1
        generic
        (
            DOA_REG : integer := 0;
            DOB_REG : integer := 0;
            RAM_MODE : string := "TDP";
            RDADDR_COLLISION_HWCONFIG : string := "DELAYED_WRITE";
            READ_WIDTH_A : integer := 0;
            READ_WIDTH_B : integer := 0;
            SIM_COLLISION_CHECK : string := "ALL";
            SRVAL_A : std_logic_vector(17 downto 0) := (others => '0');
            SRVAL_B : std_logic_vector(17 downto 0) := (others => '0');
            WRITE_MODE_A : string := "WRITE_FIRST";
            WRITE_MODE_B : string := "WRITE_FIRST";
            WRITE_WIDTH_A : integer := 0;
            WRITE_WIDTH_B : integer := 0
        );
        port
        (
            ADDRARDADDR : in std_logic_vector(13 downto 0);
            ADDRBWRADDR : in std_logic_vector(13 downto 0);
            CLKARDCLK : in std_logic;
            CLKBWRCLK : in std_logic;
            DIADI : in std_logic_vector(15 downto 0);
            DIBDI : in std_logic_vector(15 downto 0);
            DIPADIP : in std_logic_vector(1 downto 0);
            DIPBDIP : in std_logic_vector(1 downto 0);
            DOADO : out std_logic_vector(15 downto 0);
            DOBDO : out std_logic_vector(15 downto 0);
            DOPADOP : out std_logic_vector(1 downto 0);
            DOPBDOP : out std_logic_vector(1 downto 0);
            ENARDEN : in std_logic;
            ENBWREN : in std_logic;
            REGCEAREGCE : in std_logic;
            REGCEB : in std_logic;
            RSTRAMARSTRAM : in std_logic;
            RSTRAMB : in std_logic;
            RSTREGARSTREG : in std_logic;
            RSTREGB : in std_logic;
            WEA : in std_logic_vector(1 downto 0);
            WEBWE : in std_logic_vector(3 downto 0)
        );
    end component;
    component RAMB36E1
        generic
        (
            DOA_REG : integer := 0;
            DOB_REG : integer := 0;
            EN_ECC_READ : boolean := false;
            EN_ECC_WRITE : boolean := false;
            RAM_EXTENSION_A : string := "NONE";
            RAM_EXTENSION_B : string := "NONE";
            RAM_MODE : string := "TDP";
            RDADDR_COLLISION_HWCONFIG : string := "DELAYED_WRITE";
            READ_WIDTH_A : integer := 0;
            READ_WIDTH_B : integer := 0;
            SIM_COLLISION_CHECK : string := "ALL";
            WRITE_MODE_A : string := "WRITE_FIRST";
            WRITE_MODE_B : string := "WRITE_FIRST";
            WRITE_WIDTH_A : integer := 0;
            WRITE_WIDTH_B : integer := 0;
            INIT_00 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_01 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_02 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_03 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_04 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_05 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_06 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_07 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_08 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_09 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_0A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_0B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_0C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_0D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_0E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_0F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_10 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_11 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_12 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_13 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_14 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_15 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_16 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_17 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_18 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_19 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_1A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_1B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_1C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_1D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_1E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_1F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_20 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_21 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_22 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_23 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_24 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_25 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_26 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_27 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_28 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_29 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_2A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_2B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_2C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_2D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_2E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_2F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_30 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_31 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_32 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_33 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_34 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_35 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_36 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_37 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_38 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_39 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_3A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_3B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_3C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_3D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_3E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_3F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_40 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_41 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_42 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_43 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_44 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_45 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_46 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_47 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_48 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_49 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_4A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_4B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_4C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_4D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_4E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_4F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_50 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_51 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_52 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_53 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_54 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_55 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_56 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_57 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_58 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_59 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_5A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_5B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_5C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_5D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_5E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_5F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_60 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_61 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_62 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_63 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_64 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_65 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_66 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_67 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_68 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_69 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_6A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_6B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_6C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_6D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_6E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_6F : std_logic_vector(255 downto 0) := (others => '0');
            INIT_70 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_71 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_72 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_73 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_74 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_75 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_76 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_77 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_78 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_79 : std_logic_vector(255 downto 0) := (others => '0');
            INIT_7A : std_logic_vector(255 downto 0) := (others => '0');
            INIT_7B : std_logic_vector(255 downto 0) := (others => '0');
            INIT_7C : std_logic_vector(255 downto 0) := (others => '0');
            INIT_7D : std_logic_vector(255 downto 0) := (others => '0');
            INIT_7E : std_logic_vector(255 downto 0) := (others => '0');
            INIT_7F : std_logic_vector(255 downto 0) := (others => '0')
        );
        port
        (
            ADDRARDADDR : in std_logic_vector(15 downto 0);
            ADDRBWRADDR : in std_logic_vector(15 downto 0);
            CASCADEINA : in std_logic;
            CASCADEINB : in std_logic;
            CASCADEOUTA : out std_logic;
            CASCADEOUTB : out std_logic;
            CLKARDCLK : in std_logic;
            CLKBWRCLK : in std_logic;
            DIADI : in std_logic_vector(31 downto 0);
            DIBDI : in std_logic_vector(31 downto 0);
            DIPADIP : in std_logic_vector(3 downto 0);
            DIPBDIP : in std_logic_vector(3 downto 0);
            DOADO : out std_logic_vector(31 downto 0);
            DOBDO : out std_logic_vector(31 downto 0);
            DOPADOP : out std_logic_vector(3 downto 0);
            DOPBDOP : out std_logic_vector(3 downto 0);
            ENARDEN : in std_logic;
            ENBWREN : in std_logic;
            INJECTDBITERR : in std_logic;
            INJECTSBITERR : in std_logic;
            REGCEAREGCE : in std_logic;
            REGCEB : in std_logic;
            RSTRAMARSTRAM : in std_logic;
            RSTRAMB : in std_logic;
            RSTREGARSTREG : in std_logic;
            RSTREGB : in std_logic;
            WEA : in std_logic_vector(3 downto 0);
            WEBWE : in std_logic_vector(7 downto 0)
        );
    end component;
end package vcomponents;

library ieee;
use ieee.std_logic_1164.all;

entity BUFG is
    port
    (
        I : in std_logic;
        O : out std_logic
    );
end entity BUFG;

architecture stub of BUFG is
begin
end architecture stub;

library ieee;
use ieee.std_logic_1164.all;

entity BUFHCE is
    generic
    (
        CE_TYPE : string := "SYNC"
    );
    port
    (
        CE : in std_logic;
        I : in std_logic;
        O : out std_logic
    );
end entity BUFHCE;

architecture stub of BUFHCE is
begin
end architecture stub;

library ieee;
use ieee.std_logic_1164.all;

entity IOBUF is
    generic
    (
        SLEW : string := "SLOW"
    );
    port
    (
        I : in std_logic;
        IO : inout std_logic;
        O : out std_logic;
        T : in std_logic
    );
end entity IOBUF;

architecture stub of IOBUF is
begin
end architecture stub;

library ieee;
use ieee.std_logic_1164.all;

entity OBUF is
    port
    (
        I : in std_logic;
        O : out std_logic
    );
end entity OBUF;

architecture stub of OBUF is
begin
end architecture stub;

library ieee;
use ieee.std_logic_1164.all;

entity PLLE2_BASE is
    generic
    (
        BANDWIDTH : string := "OPTIMIZED";
        CLKFBOUT_MULT : integer := 5;
        CLKFBOUT_PHASE : real := 0.0;
        CLKIN1_PERIOD : real := 0.0;
        CLKOUT0_DIVIDE : integer := 1;
        CLKOUT0_DUTY_CYCLE : real := 0.5;
        CLKOUT0_PHASE : real := 0.0;
        CLKOUT1_DIVIDE : integer := 1;
        CLKOUT1_DUTY_CYCLE : real := 0.5;
        CLKOUT1_PHASE : real := 0.0;
        DIVCLK_DIVIDE : integer := 1;
        REF_JITTER1 : real := 0.0;
        STARTUP_WAIT : string := "FALSE"
    );
    port
    (
        CLKFBIN : in std_logic;
        CLKIN1 : in std_logic;
        PWRDWN : in std_logic;
        RST : in std_logic;
        CLKFBOUT : out std_logic;
        CLKOUT0 : out std_logic;
        CLKOUT1 : out std_logic;
        LOCKED : out std_logic
    );
end entity PLLE2_BASE;

architecture stub of PLLE2_BASE is
begin
end architecture stub;

library ieee;
use ieee.std_logic_1164.all;

entity RAMB18E1 is
    generic
    (
        DOA_REG : integer := 0;
        DOB_REG : integer := 0;
        RAM_MODE : string := "TDP";
        RDADDR_COLLISION_HWCONFIG : string := "DELAYED_WRITE";
        READ_WIDTH_A : integer := 0;
        READ_WIDTH_B : integer := 0;
        SIM_COLLISION_CHECK : string := "ALL";
        SRVAL_A : std_logic_vector(17 downto 0) := (others => '0');
        SRVAL_B : std_logic_vector(17 downto 0) := (others => '0');
        WRITE_MODE_A : string := "WRITE_FIRST";
        WRITE_MODE_B : string := "WRITE_FIRST";
        WRITE_WIDTH_A : integer := 0;
        WRITE_WIDTH_B : integer := 0
    );
    port
    (
        ADDRARDADDR : in std_logic_vector(13 downto 0);
        ADDRBWRADDR : in std_logic_vector(13 downto 0);
        CLKARDCLK : in std_logic;
        CLKBWRCLK : in std_logic;
        DIADI : in std_logic_vector(15 downto 0);
        DIBDI : in std_logic_vector(15 downto 0);
        DIPADIP : in std_logic_vector(1 downto 0);
        DIPBDIP : in std_logic_vector(1 downto 0);
        DOADO : out std_logic_vector(15 downto 0);
        DOBDO : out std_logic_vector(15 downto 0);
        DOPADOP : out std_logic_vector(1 downto 0);
        DOPBDOP : out std_logic_vector(1 downto 0);
        ENARDEN : in std_logic;
        ENBWREN : in std_logic;
        REGCEAREGCE : in std_logic;
        REGCEB : in std_logic;
        RSTRAMARSTRAM : in std_logic;
        RSTRAMB : in std_logic;
        RSTREGARSTREG : in std_logic;
        RSTREGB : in std_logic;
        WEA : in std_logic_vector(1 downto 0);
        WEBWE : in std_logic_vector(3 downto 0)
    );
end entity RAMB18E1;

architecture stub of RAMB18E1 is
begin
end architecture stub;

library ieee;
use ieee.std_logic_1164.all;

entity RAMB36E1 is
    generic
    (
        DOA_REG : integer := 0;
        DOB_REG : integer := 0;
        EN_ECC_READ : boolean := false;
        EN_ECC_WRITE : boolean := false;
        RAM_EXTENSION_A : string := "NONE";
        RAM_EXTENSION_B : string := "NONE";
        RAM_MODE : string := "TDP";
        RDADDR_COLLISION_HWCONFIG : string := "DELAYED_WRITE";
        READ_WIDTH_A : integer := 0;
        READ_WIDTH_B : integer := 0;
        SIM_COLLISION_CHECK : string := "ALL";
        WRITE_MODE_A : string := "WRITE_FIRST";
        WRITE_MODE_B : string := "WRITE_FIRST";
        WRITE_WIDTH_A : integer := 0;
        WRITE_WIDTH_B : integer := 0;
        INIT_00 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_01 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_02 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_03 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_04 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_05 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_06 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_07 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_08 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_09 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_0A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_0B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_0C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_0D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_0E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_0F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_10 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_11 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_12 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_13 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_14 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_15 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_16 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_17 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_18 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_19 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_1A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_1B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_1C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_1D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_1E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_1F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_20 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_21 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_22 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_23 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_24 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_25 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_26 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_27 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_28 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_29 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_2A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_2B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_2C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_2D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_2E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_2F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_30 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_31 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_32 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_33 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_34 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_35 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_36 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_37 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_38 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_39 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_3A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_3B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_3C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_3D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_3E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_3F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_40 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_41 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_42 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_43 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_44 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_45 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_46 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_47 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_48 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_49 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_4A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_4B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_4C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_4D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_4E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_4F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_50 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_51 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_52 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_53 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_54 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_55 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_56 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_57 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_58 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_59 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_5A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_5B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_5C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_5D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_5E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_5F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_60 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_61 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_62 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_63 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_64 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_65 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_66 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_67 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_68 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_69 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_6A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_6B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_6C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_6D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_6E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_6F : std_logic_vector(255 downto 0) := (others => '0');
        INIT_70 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_71 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_72 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_73 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_74 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_75 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_76 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_77 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_78 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_79 : std_logic_vector(255 downto 0) := (others => '0');
        INIT_7A : std_logic_vector(255 downto 0) := (others => '0');
        INIT_7B : std_logic_vector(255 downto 0) := (others => '0');
        INIT_7C : std_logic_vector(255 downto 0) := (others => '0');
        INIT_7D : std_logic_vector(255 downto 0) := (others => '0');
        INIT_7E : std_logic_vector(255 downto 0) := (others => '0');
        INIT_7F : std_logic_vector(255 downto 0) := (others => '0')
    );
    port
    (
        ADDRARDADDR : in std_logic_vector(15 downto 0);
        ADDRBWRADDR : in std_logic_vector(15 downto 0);
        CASCADEINA : in std_logic;
        CASCADEINB : in std_logic;
        CASCADEOUTA : out std_logic;
        CASCADEOUTB : out std_logic;
        CLKARDCLK : in std_logic;
        CLKBWRCLK : in std_logic;
        DIADI : in std_logic_vector(31 downto 0);
        DIBDI : in std_logic_vector(31 downto 0);
        DIPADIP : in std_logic_vector(3 downto 0);
        DIPBDIP : in std_logic_vector(3 downto 0);
        DOADO : out std_logic_vector(31 downto 0);
        DOBDO : out std_logic_vector(31 downto 0);
        DOPADOP : out std_logic_vector(3 downto 0);
        DOPBDOP : out std_logic_vector(3 downto 0);
        ENARDEN : in std_logic;
        ENBWREN : in std_logic;
        INJECTDBITERR : in std_logic;
        INJECTSBITERR : in std_logic;
        REGCEAREGCE : in std_logic;
        REGCEB : in std_logic;
        RSTRAMARSTRAM : in std_logic;
        RSTRAMB : in std_logic;
        RSTREGARSTREG : in std_logic;
        RSTREGB : in std_logic;
        WEA : in std_logic_vector(3 downto 0);
        WEBWE : in std_logic_vector(7 downto 0)
    );
end entity RAMB36E1;

architecture stub of RAMB36E1 is
begin
end architecture stub;

