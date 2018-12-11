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
set terminal gif notransparent size 800,600

prefix = "`echo $AIPLANNER_PREFIX`"
timesteps = "`echo $AIPLANNER_TIMESTEPS`"

set xlabel "age"
set ylabel "investments"
set yrange [0:1000000]
set format y "%.1s%c"

set xrange [65.999:100.001]
set zlabel "consumption"
set zrange [0:200000]
set format z "%.0s%c"
set output prefix . "-consume" . timesteps . ".gif"
splot prefix . "-linear" . timesteps . ".csv" using 1:2:3 every :2 with lines title "AIPlanner timestep " . timesteps

set xrange [40:100.001]
set yrange [33333:1000000] # AIPlanner aa may vary randomly at zero.
set ytics 200000
set zlabel "stocks"
set zrange [0:100]
set format z "%g%%"
set output prefix . "-stocks" . timesteps . ".gif"
splot prefix . "-linear" . timesteps . ".csv" using 1:2:($9 * 100) every :2 with lines title "AIPlanner timestep " . timesteps
