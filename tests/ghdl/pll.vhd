-- Behavioural architecture of PLLE2_BASE for the co-simulation : same behaviour as src/hand/plle2_base.c.
-- The outputs have the period  PERIOD(CLKIN1) * DIVCLK_DIVIDE * CLKOUTn_DIVIDE / CLKFBOUT_MULT, start on the
-- second rising edge of CLKIN1 (the period is measured between the first two) and LOCKED rises 8 CLKIN1 periods
-- later. cosim.py puts this text in place of the empty architecture of the UNISIM stub.
architecture stub of PLLE2_BASE is
    signal P   : time := 0 ps;
    signal RUN : boolean := false;
begin
    MEASURE : process
        variable T1 : time;
    begin
        wait until rising_edge(CLKIN1);
        T1 := now;
        wait until rising_edge(CLKIN1);
        P <= now - T1;
        RUN <= true;
        wait;
    end process;

    OUT0 : process
        variable H : time;
        variable V : std_logic := '0';
    begin
        CLKOUT0 <= '0';
        wait until RUN;
        H := (P * DIVCLK_DIVIDE * CLKOUT0_DIVIDE) / (2 * CLKFBOUT_MULT);
        loop
            V := not V;
            CLKOUT0 <= V;
            wait for H;
        end loop;
    end process;

    OUT1 : process
        variable H : time;
        variable V : std_logic := '0';
    begin
        CLKOUT1 <= '0';
        wait until RUN;
        H := (P * DIVCLK_DIVIDE * CLKOUT1_DIVIDE) / (2 * CLKFBOUT_MULT);
        loop
            V := not V;
            CLKOUT1 <= V;
            wait for H;
        end loop;
    end process;

    LOCK : process
    begin
        LOCKED <= '0';
        CLKFBOUT <= '0';
        wait until RUN;
        wait for P * 8;
        LOCKED <= '1';
        wait;
    end process;
end architecture stub;
