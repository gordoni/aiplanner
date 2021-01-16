#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from argparse import ArgumentParser
from distutils.core import setup
from distutils.extension import Extension
from os import chdir
from os.path import expanduser

from Cython.Build import cythonize

# If properly Cythonized model would gain perhaps a 5 fold speed up.

parser = ArgumentParser(description = 'Cythonize AIPlanner.')
parser.add_argument('--annotate', action = 'store_true', help = 'Produce a HTML annotation of the source code')
parser.add_argument('--force', action = 'store_true', help = 'Recompile irrespective of source code file dates')
parser.add_argument('--profile', action = 'store_true', help = 'Add profiling hooks')
args = parser.parse_args()

build_temp = expanduser('~/aiplanner-data/build')

setup(
    script_name = 'setup.py',
    script_args = ['build_ext', '--inplace', '--build-temp', build_temp],
    ext_modules = cythonize(
        [
            Extension('ai.gym_fin.fin', sources = ['gym_fin/fin.pyx']),
            Extension('ai.gym_fin.returns', sources = ['gym_fin/returns.pyx']),
            Extension('ai.gym_fin.returns_equity', sources = ['gym_fin/returns_equity.pyx']),
        ],
        include_path = ['.', 'gym_fin'],
        annotate = args.anotate,
        force = args.force,
        compiler_directives = {
            'binding' = True,
            'embedsignature' = True,
            'profile': args.profile,
        }
    )
)
