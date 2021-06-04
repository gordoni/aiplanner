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

set xlabel "annual consumption"
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

set yrange [0:100]
set format y "%g%%"

set xlabel "annual consumption"
set output prefix . "-consume-cdf.svg"
plot prefix . "-consume-cdf.csv" using 1:($2 * 100) with lines notitle lt rgb "blue"

set xlabel "residual estate"
set output prefix . "-estate-cdf.svg"
plot prefix . "-estate-cdf.csv" using 1:($2 * 100) with lines notitle lt rgb "blue"

set xlabel "age self"
set xrange [age_low:age_high]
set format x "%.0f"

set ylabel "annual consumption"
set yrange [0:consume_high]
set format y "%.1s%c"
set output prefix . "-consume-cr.svg"
plot prefix . "-consume-cr0.95.csv" with filledcurves title '95% confidence region' lt rgb "yellow", \
    prefix . "-consume-cr0.80.csv" with filledcurves title '80% confidence region' lt rgb "blue", \

set ylabel "annual consumption"
set yrange [0:consume_high]
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
if (couple) plot prefix . "-alive.csv" using 1:(($2 + $3) * 100) with lines title 'alive either' lt rgb "blue", \
    prefix . "-alive.csv" using 1:($2 * 100) with lines title 'alive couple' lt rgb "green", \
    prefix . "-alive.csv" using 1:($3 * 100) with lines title 'alive single' lt rgb "red"
if (!couple) plot prefix . "-alive.csv" using 1:($3 * 100) with lines title 'alive single' lt rgb "red"
