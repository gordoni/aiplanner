# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

# This file exists to work around a Cython bug.
# Namely we can't directly perform any the imports below in bonds.py because bonds.pxd needs to cimport the same imports causing a conflict.

from ai.gym_fin.ou_process import OUProcess

def make_ou_process(*args, **kwargs):
    
    return OUProcess(*args, **kwargs)
