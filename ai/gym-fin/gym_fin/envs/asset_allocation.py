# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

class AssetAllocation(object):

    def __init__(self, *, fractional = True, **kwargs):

        self.aa = {**kwargs}

        if fractional:

            assert abs(sum(self.aa.values()) - 1) < 1e-15

    def __str__(self):

        s = ''
        for ac in ('stocks', 'real_bonds', 'nominal_bonds', 'iid_bonds', 'bills'):
            if ac in self.aa:
                if s:
                    s += ', ' + str(self.aa[ac])
                else:
                    s = str(self.aa[ac])

        return '[' + s + ']'
