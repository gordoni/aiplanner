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

set datafile separator ','

set terminal pngcairo transparent size 400,300

set xlabel 'maturity (years)'
set xrange [0:30]
set format x '%g'

set ylabel 'yield'
set yrange [-2:10]
set format y '%g%%'

set output 'yield-curves.png'
plot \
    'nominal.csv' using 1:($2 * 100) with lines title 'nominal yield curve', \
    'real.csv' using 1:($2 * 100) with lines title 'real yield curve'
