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

from ai.gym_fin.asset_allocation import AssetAllocation
from ai.gym_fin.bonds import BondsSet
from ai.gym_fin.defined_benefit import DefinedBenefit
from ai.gym_fin.fin_params import FinParams
from ai.gym_fin.policies import Policy
from ai.gym_fin.taxes import Taxes
from ai.gym_fin.utility import Utility

def make_asset_allocation(**kwargs):
    
    return AssetAllocation(**kwargs)

def make_bonds_set(**kwargs):
    
    return BondsSet(**kwargs)

def make_defined_benefit(*args, **kwargs):
    
    return DefinedBenefit(*args, **kwargs)

def make_fin_params(params_dict):
    
    return FinParams(params_dict)

def make_policy(*args):
    
    return Policy(*args)

def make_taxes(*args):
    
    return Taxes(*args)

def make_utility(*args):
    
    return Utility(*args)
