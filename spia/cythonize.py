#!/usr/bin/env python3

# SPIA - Income annuity (SPIA and DIA) price calculator
# Copyright (C) 2021 Gordon Irlam
#
# This program may be licensed by you (at your option) under an Open
# Source, Free for Non-Commercial Use, or Commercial Use License.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is free for non-commercial use: you can use and modify it
# under the terms of the Creative Commons
# Attribution-NonCommercial-ShareAlike 4.0 International Public License
# (https://creativecommons.org/licenses/by-nc-sa/4.0/).
#
# A Commercial Use License is available in exchange for agreed
# remuneration.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from argparse import ArgumentParser
from os import chdir, environ
from setuptools import setup

from Cython.Build import cythonize

parser = ArgumentParser(description = 'Cythonize AIPlanner.')
parser.add_argument('--annotate', action = 'store_true', help = 'Produce a HTML annotation of the source code')
parser.add_argument('--no-optimize', action = 'store_false', dest = 'optimize', help = 'Suppress code optimization')
parser.add_argument('--force', action = 'store_true', help = 'Recompile irrespective of source code file dates')
parser.add_argument('--profile', action = 'store_true', help = 'Add profiling hooks')
parser.add_argument('--tempdir', default = '/tmp', help = 'Temporary directory to use for build')
args = parser.parse_args()

build_temp = args.tempdir + '/cythonize.build'

chdir('..')
for f in [
    'spia/income_annuity.py',
    'spia/life_table.py',
    'spia/test.py',
    'spia/yield_curve.py',
]:
    path = f.split('/')
    build_lib = '/'.join(path[:-2])
    if not args.optimize:
        environ['CFLAGS'] = '-O0'
    setup(
        script_name = 'setup.py',
        script_args = ['build_ext', '--build-temp', build_temp, '--build-lib', build_lib],
        ext_modules = cythonize(f,
            annotate = args.annotate,
            force = args.force,
            compiler_directives = {
                'binding': True,
                'embedsignature': True,
                'language_level': '3',
                'profile': args.profile,
            },
        ),
        zip_safe = False,
    )
