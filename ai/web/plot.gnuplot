#!/usr/bin/gnuplot

set datafile separator ","
set terminal svg dynamic size 800,400

prefix = "`echo $AIPLANNER_FILE_PREFIX`"
if (prefix eq "") prefix = "aiplanner"

set xlabel "annual consumption"
set xrange [0:*]
set format x "%.1s%c"
set ylabel "probability"
set yrange [0:*]
unset ytics
set output prefix . "-consume-pdf.svg"
plot prefix . "-consume-pdf.csv" with lines smooth csplines notitle lt 2
set ytics

set xlabel "age"
set xrange [*:100]

set ylabel "annual consumption"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-consume.svg"
plot prefix . "-trace.csv" using 1:($2 == 1 ? $6 : NaN) with lines title 'couple' lt 2, \
    prefix . "-trace.csv" using 1:($3 == 1 ? $6 : NaN) with lines title 'single' lt 1

set ylabel "non-investment income"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-gi.svg"
plot prefix . "-trace.csv" using 1:($2 == 1 ? $4 : NaN) with lines title 'couple' lt 2, \
    prefix . "-trace.csv" using 1:($3 == 1 ? $4 : NaN) with lines title 'single' lt 1

set ylabel "investments"
set yrange [0:*]
set format y "%.1s%c"
set output prefix . "-paths-p.svg"
plot prefix . "-trace.csv" using 1:($2 == 1 ? $5 : NaN) with lines title 'couple' lt 2, \
    prefix . "-trace.csv" using 1:($3 == 1 ? $5 : NaN) with lines title 'single' lt 1
