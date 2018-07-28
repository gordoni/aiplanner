#!/usr/bin/gnuplot

set datafile separator ","
set terminal svg dynamic size 800,400

prefix = "`echo $AIPLANNER_FILE_PREFIX`"
if (prefix eq "") prefix = "aiplanner"

set output prefix . "-paths-gi.svg"
plot prefix . "-data.csv" using 1:2 with lines notitle

set output prefix . "-paths-p.svg"
plot prefix . "-data.csv" using 1:3 with lines notitle

set output prefix . "-paths-consume.svg"
plot prefix . "-data.csv" using 1:4 with lines notitle
