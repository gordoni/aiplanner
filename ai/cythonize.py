#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from distutils.core import setup
from distutils.extension import Extension
from os import chdir
from os.path import expanduser

from Cython.Build import cythonize

# Cython is not currently used.
# If properly Cythonized model would gain perhaps a 5 fold speed up.
# But for a 256x256 fcnet without a GPU 80-90% of training time is spent training the neural network, not stepping/reseting the model.

build_temp = expanduser('~/aiplanner-data/build')

chdir('gym-fin')
setup(
    script_name = 'setup.py',
    script_args = ['build_ext', '--inplace', '--build-temp', build_temp],
    ext_modules = cythonize([
        Extension('ai.gym_fin.fin', sources = ['gym_fin/fin.pyx']),
        Extension('ai.gym_fin.returns', sources = ['gym_fin/returns.pyx']),
        Extension('ai.gym_fin.returns_equity', sources = ['gym_fin/returns_equity.pyx']),
    ], include_path = ['.', 'gym_fin'], annotate = True, force = False, compiler_directives = {'profile': True})
)
