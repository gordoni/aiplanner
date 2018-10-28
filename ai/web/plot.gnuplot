#!/usr/bin/gnuplot

set datafile separator ","
set terminal svg dynamic size 800,400

prefix = "`echo $AIPLANNER_FILE_PREFIX`"
if (prefix eq "") prefix = "aiplanner"

set xlabel "age"
set xrange [*:100]

set ylabel "non-investment income"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-gi.svg"
plot prefix . "-data.csv" using 1:($2 == 1 ? $4 : NaN) with lines title 'couple' lt 2, \
    prefix . "-data.csv" using 1:($3 == 1 ? $4 : NaN) with lines title 'single' lt 1

set ylabel "investments"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-p.svg"
plot prefix . "-data.csv" using 1:($2 == 1 ? $5 : NaN) with lines title 'couple' lt 2, \
    prefix . "-data.csv" using 1:($3 == 1 ? $5 : NaN) with lines title 'single' lt 1

set ylabel "consumption"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-consume.svg"
plot prefix . "-data.csv" using 1:($2 == 1 ? $6 : NaN) with lines title 'couple' lt 2, \
    prefix . "-data.csv" using 1:($3 == 1 ? $6 : NaN) with lines title 'single' lt 1
