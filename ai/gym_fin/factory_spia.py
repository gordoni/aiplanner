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
# Namely we can't directly perform any the imports below in fin.py because fin.pxd needs to cimport the same imports causing a conflict.

from spia import IncomeAnnuity, LifeTable, YieldCurve

def make_income_annuity(*args, **kwargs):
    
    return IncomeAnnuity(*args, **kwargs)

def make_life_table(*args, **kwargs):
    
    return LifeTable(*args, **kwargs)

def make_yield_curve(*args, **kwargs):
    
    return YieldCurve(*args, **kwargs)
