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
#from distutils.core import setup
#from distutils.extension import Extension
from os import chdir, environ
from os.path import expanduser
from setuptools import Extension, setup

from Cython.Build import cythonize

# If properly Cythonized model would gain perhaps a 5 fold speed up.

parser = ArgumentParser(description = 'Cythonize AIPlanner.')
parser.add_argument('--annotate', action = 'store_true', help = 'Produce a HTML annotation of the source code')
parser.add_argument('--no-optimize', action = 'store_false', dest = 'optimize', help = 'Suppress code optimization')
parser.add_argument('--force', action = 'store_true', help = 'Recompile irrespective of source code file dates')
parser.add_argument('--profile', action = 'store_true', help = 'Add profiling hooks')
parser.add_argument('--tempdir', default = '/tmp', help = 'Temporary directory to use for build')
args = parser.parse_args()

build_temp = args.tempdir + '/cythonize.build'

aiplanner_home = expanduser('~/aiplanner')
chdir(aiplanner_home)

for f in [
    'ai/gym_fin/asset_allocation.py',
    'ai/gym_fin/bonds.py',
    'ai/gym_fin/defined_benefit.py',
    'ai/gym_fin/fin.py',
    'ai/gym_fin/fin_params.py',
    'ai/gym_fin/ou_process.py',
    'ai/gym_fin/policies.py',
    'ai/gym_fin/returns_equity.py',
    'ai/gym_fin/taxes.py',
    'ai/gym_fin/utility.py',
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
