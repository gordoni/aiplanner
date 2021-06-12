# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from enum import Enum

import cython

from ai.gym_fin.asset_classes import AssetClasses

@cython.cclass
class AssetAllocation:

    def __init__(self, **kwargs):

        self.aa = [None] * len(AssetClasses)
        for ac, v in kwargs.items():
            self.aa[AssetClasses[ac.upper()].value] = v

    def clone(self):

        c = AssetAllocation()
        c.aa = list(self.aa)

        return c

    def sum(self):

        s: cython.double
        s = 0
        for v in self.aa:
            if v is not None:
                val: cython.double
                val = v
                s += val

        return s

    def classes(self):

        l = []
        for ac in AssetClasses:
            if self.aa[ac.value] is not None:
                l.append(ac.name.lower())

        return l

    def as_list(self):

        l = []
        for ac in AssetClasses:
            if self.aa[ac.value] is not None:
                l.append(self.aa[ac.value])

        return l

    def __str__(self):

        return str(self.as_list())
