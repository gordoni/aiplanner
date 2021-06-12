# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from enum import Enum

class AssetClasses(Enum):

    STOCKS = 0
    REAL_BONDS = 1
    NOMINAL_BONDS = 2
    IID_BONDS = 3
