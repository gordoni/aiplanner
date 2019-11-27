#!/usr/bin/gnuplot

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

set datafile separator ","
set terminal svg dynamic size 800,400 name "AIPlanner"

set key top left

set xlabel "year"
set xrange [0:100]
set format x "%g"
set ylabel "log scale"
set yrange [*:*]

set output "index.svg"
plot "index.csv" using 1:2 with lines title "index", \
    "index.csv" using 1:3 with lines title "fair value"

set key top right

set xlabel "year"
set xrange [0:10]
set format x "%g"
set ylabel "sigma"
set yrange [0:*]

set output "index-sigma.svg"
plot "index.csv" using 1:4 with lines notitle

set xlabel "price / fair value"
set xrange [0:2]
set format x "%g"
set ylabel "probability"
set yrange [0:*]

set output "above_trend.svg"
plot "above_trend.csv" using 1:2 with lines notitle
