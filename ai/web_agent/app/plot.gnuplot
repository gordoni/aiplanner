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

set terminal pngcairo transparent size 400,300

set xlabel 'annual spending'
set xrange [0:100000]
set format x '$%.0s%c'

set ylabel 'annual well-being'
set yrange [-10:0]
unset ytics

set output 'static/utility.png'
plot ((x / 100000) ** (1 - 3) - 1) / (1 - 3) notitle
