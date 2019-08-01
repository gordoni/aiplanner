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

set datafile separator ','
set terminal svg dynamic size 800,400 name "AIPlanner"

set xlabel "consumption"
set xrange [0:*]
set xtics 0, 100, 1

set ylabel "probability"
set yrange [0:*]
unset ytics

set output 'risk_aversion_pdf.svg'
plot \
    'risk_aversion_6_pdf.csv' using 1:2 with lines title 'RRA coefficient = 6.0', \
    'risk_aversion_3_pdf.csv' using 1:2 with lines title 'RRA coefficient = 3.0', \
    'risk_aversion_1.5_pdf.csv' using 1:2 with lines title 'RRA coefficient = 1.5'
