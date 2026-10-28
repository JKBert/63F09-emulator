-- The Xilinx primitives instantiated by the 63F09 sources : their declarations (derived from the generics and
-- ports the sources use) and, for the simple buffers, the behaviour of the UNISIM models, so that GHDL can
-- simulate the design. The behaviour of these primitives is modelled in C by hand (src/hand).

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
    component BUFGCE
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
    component BUFGCTRL
        generic
        (
            INIT_OUT : integer := 0;
            PRESELECT_I0 : boolean := false;
            PRESELECT_I1 : boolean := false
        );
        port
        (
            CE0 : in std_logic;
            CE1 : in std_logic;
            I0 : in std_logic;
            I1 : in std_logic;
            IGNORE0 : in std_logic;
            IGNORE1 : in std_logic;
            S0 : in std_logic;
            S1 : in std_logic;
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
    component OBUFT
        generic
        (
            SLEW : string := "SLOW"
        );
        port
        (
            I : in std_logic;
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

architecture sim of BUFG is
begin
    O <= I;
end architecture sim;

library ieee;
use ieee.std_logic_1164.all;

entity BUFGCE is
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
end entity BUFGCE;

architecture sim of BUFGCE is
    signal ce_latch : std_logic := '0';
begin
    -- as the BUFHCE : CE is latched while the clock is low, so that the output never glitches
    process(I, CE)
    begin
        if I = '0' then
            ce_latch <= CE;
        end if;
    end process;
    O <= I and ce_latch;
end architecture sim;

library ieee;
use ieee.std_logic_1164.all;

entity BUFGCTRL is
    generic
    (
        INIT_OUT : integer := 0;
        PRESELECT_I0 : boolean := false;
        PRESELECT_I1 : boolean := false
    );
    port
    (
        CE0 : in std_logic;
        CE1 : in std_logic;
        I0 : in std_logic;
        I1 : in std_logic;
        IGNORE0 : in std_logic;
        IGNORE1 : in std_logic;
        S0 : in std_logic;
        S1 : in std_logic;
        O : out std_logic
    );
end entity BUFGCTRL;

architecture sim of BUFGCTRL is
begin
    -- behavioural model (the IGNOREx inputs and the CEx latches are not modelled : the 63F09 sources tie them to '1' and
    -- drive S0 / S1 from a register that only changes while the clocks are idle) : S1 selects I1, else S0 selects I0, else the
    -- previous selection is kept (PRESELECT_I1 / PRESELECT_I0 / INIT_OUT give the initial one)
    process(I0, I1, S0, S1, CE0, CE1)
        variable sel1 : boolean := PRESELECT_I1;
    begin
        if S1 = '1' and CE1 = '1' then
            sel1 := true;
        elsif S0 = '1' and CE0 = '1' then
            sel1 := false;
        end if;
        if sel1 then
            O <= I1;
        else
            O <= I0;
        end if;
    end process;
end architecture sim;

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

architecture sim of BUFHCE is
    signal ce_latch : std_logic := '0';
begin
    process(I, CE)
    begin
        if I = '0' then
            ce_latch <= CE;
        end if;
    end process;
    O <= I and ce_latch;
end architecture sim;

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

architecture sim of IOBUF is
begin
    IO <= I when T = '0' else 'Z';
    O <= to_x01(IO);                 -- a pad has a level : a pull-up (H) reads as 1
end architecture sim;

library ieee;
use ieee.std_logic_1164.all;

entity OBUFT is
    generic
    (
        SLEW : string := "SLOW"
    );
    port
    (
        I : in std_logic;
        O : out std_logic;
        T : in std_logic
    );
end entity OBUFT;

architecture sim of OBUFT is
begin
    O <= I when T = '0' else 'Z';
end architecture sim;

library ieee;
use ieee.std_logic_1164.all;

entity OBUF is
    port
    (
        I : in std_logic;
        O : out std_logic
    );
end entity OBUF;

architecture sim of OBUF is
begin
    O <= I;
end architecture sim;

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

