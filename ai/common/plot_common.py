# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from os import chmod, stat
from stat import S_IXUSR, S_IXGRP, S_IXOTH
from subprocess import CalledProcessError, run

def plot_common(api, result_dir, results, results_dir):

    s = ''
    for result in sorted(results, key = lambda r: r.get('rra', 0), reverse = True):
        if not result['error']:
            aid = result['aid']
            if s:
                s += ', '
            s += '"' + results_dir + '/' + aid + '/seed_all/aiplanner-consume-pdf.csv" with lines title "'
            s += ('low' if result['rra'] < 2 else 'moderate' if result['rra'] < 4 else 'high') + ' risk aversion" lt rgb "'
            s += ('red' if result['rra'] < 2 else 'blue' if result['rra'] < 4 else 'green') + '"'

    if s:
        plot_filename = result_dir + '/plot-common.gnuplot'
        with open(plot_filename, 'w') as f:
            f.write('''#!/usr/bin/gnuplot

set datafile separator ","
set terminal svg dynamic size 800,400 name "AIPlanner"

set xlabel "annual consumption"
set xrange [0:*]
set format x "%.1s%c"
set ylabel "probability"
set yrange [0:*]
unset ytics

set output "''' + result_dir + '''/consume-pdf.svg"
plot ''' + s + '\n')

        st = stat(plot_filename)
        chmod(plot_filename, st.st_mode | S_IXUSR | S_IXGRP | S_IXOTH)
        try:
            run([plot_filename], check = True)
        except CalledProcessError:
            assert False, 'Error ploting common results.'
