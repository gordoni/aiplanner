#!/usr/bin/gnuplot

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

set datafile separator ","
set terminal svg dynamic size 800,400

set xlabel "age"
set ylabel "investments"
set yrange [0:1000000]
set format y "%.1s%c"

set xrange [64.999:100.001]
set zlabel "annual consumption"
set zrange [0:*]
set format z "%.1s%c"
set output "plot2-consume.svg"
splot "run.opal.ssa_40_plus_3_female-iid_bonds.plot/opal-linear.csv" using 1:2:8 with lines title "stochastic dynamic programming", \
    "aiplanner.ssa_40_plus_3_female-iid_bonds-seed0.tf/aiplanner-linear.csv" using 1:2:3 with lines title "AIPlanner seed 0", \
    "aiplanner.ssa_40_plus_3_female-iid_bonds-seed1.tf/aiplanner-linear.csv" using 1:2:3 with lines title "AIPlanner seed 1"

set xrange [39.999:100.001]
set zlabel "stocks"
set zrange [0:100]
set format z "%g%%"
set output "plot2-stocks.svg"
splot "run.opal.ssa_40_plus_3_female-iid_bonds.plot/opal-linear.csv" using 1:2:($8 * 100) with lines "stochastic dynamic programming", \
    "aiplanner.ssa_40_plus_3_female-iid_bonds-seed0.tf/aiplanner-linear.csv" using 1:2:($9 * 100) with lines title "AIPlanner seed 0", \
    "aiplanner.ssa_40_plus_3_female-iid_bonds-seed1.tf/aiplanner-linear.csv" using 1:2:($9 * 100) with lines title "AIPlanner seed 1"
