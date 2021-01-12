#!/usr/bin/gnuplot

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

set datafile separator ","
set terminal svg dynamic size 800,400 name "AIPlanner"

prefix = "`echo $AIPLANNER_FILE_PREFIX`"
if (prefix eq "") prefix = "aiplanner"

set xlabel "annual retirement consumption"
set xrange [0:*]
set format x "%.1s%c"
set ylabel "probability"
set yrange [0:*]
unset ytics

set output prefix . "-consume-pdf.svg"
plot prefix . "-consume-pdf.csv" with lines notitle lt rgb "blue"

set xlabel "residual estate"
set output prefix . "-estate-pdf.svg"
plot prefix . "-estate-pdf.csv" with lines notitle lt rgb "blue"

set ytics

set xlabel "age self"
set xrange [*:110]

set ylabel "annual consumption"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-consume.svg"
plot prefix . "-paths.csv" using 1:($2 == 1 ? $6 : NaN) with lines title 'example paths couple' lt rgb "green", \
    prefix . "-paths.csv" using 1:($3 == 1 ? $6 : NaN) with lines title 'example paths single' lt rgb "red"

set ylabel "net guaranteed income"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-gi.svg"
plot prefix . "-paths.csv" using 1:($2 == 1 ? $4 : NaN) with lines title 'example paths couple' lt rgb "green", \
    prefix . "-paths.csv" using 1:($3 == 1 ? $4 : NaN) with lines title 'example paths single' lt rgb "red"

set ylabel "investments"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-p.svg"
plot prefix . "-paths.csv" using 1:($2 == 1 ? $5 : NaN) with lines title 'example paths couple' lt rgb "green", \
    prefix . "-paths.csv" using 1:($3 == 1 ? $5 : NaN) with lines title 'example paths single' lt rgb "red"

set ylabel "stocks / investments"
set yrange [0:100]
set format y "%g%%"
set output prefix . "-paths-stocks.svg"
plot prefix . "-paths.csv" using 1:($2 == 1 ? $9 * 100 : NaN) with lines title 'example paths couple' lt rgb "green", \
    prefix . "-paths.csv" using 1:($3 == 1 ? $9 * 100 : NaN) with lines title 'example paths single' lt rgb "red"

set ylabel "probability"
set yrange [0:100]
set format y "%g%%"
set output prefix . "-alive.svg"
plot prefix . "-alive.csv" using 1:(($2 + $3) * 100) with lines title 'alive either' lt rgb "blue", \
    prefix . "-alive.csv" using 1:($2 * 100) with lines title 'alive couple' lt rgb "green", \
    prefix . "-alive.csv" using 1:($3 * 100) with lines title 'alive single' lt rgb "red"
