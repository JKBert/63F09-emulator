library ieee;
use ieee.std_logic_1164.all;
use std.textio.all;

entity tb_clk is
end entity tb_clk;

architecture sim of tb_clk is
    signal RESET_n  : std_logic := '0';
    signal MRDY     : std_logic := '0';
    signal TICK     : std_logic := '0';
    signal E, Q, C  : std_logic;
begin
    DUT : entity work.CLK_63F75
    port map (RESET_n => RESET_n, MRDY => MRDY, TICK => TICK, E => E, Q => Q, C => C);

    process
        file     stim   : text open read_mode is "stim.txt";
        file     result : text open write_mode is "ghdl.out";
        variable l      : line;
        variable r, m   : integer;

        procedure dump is
            variable o  : line;
        begin
            write(o, to_string(E) & " " & to_string(Q) & " " & to_string(C));
            writeline(result, o);
        end procedure;
    begin
        wait for 1 ns;
        while not endfile(stim) loop
            readline(stim, l);
            read(l, r);
            read(l, m);
            if r = 1 then RESET_n <= '1'; else RESET_n <= '0'; end if;
            if m = 1 then MRDY <= '1'; else MRDY <= '0'; end if;
            TICK <= '0';
            wait for 5 ns;
            dump;
            TICK <= '1';
            wait for 5 ns;
            dump;
        end loop;
        wait;
    end process;
end architecture sim;
