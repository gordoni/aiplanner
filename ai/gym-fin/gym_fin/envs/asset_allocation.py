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

    def __init__(self, *, stocks = None, real_bonds = None, nominal_bonds = None, iid_bonds = None, bills = None):

        self.stocks = stocks
        self.real_bonds = real_bonds
        self.nominal_bonds = nominal_bonds
        self.iid_bonds = iid_bonds
        self.bills = bills

        s = 0
        if stocks:
            s += stocks
        if real_bonds:
            s += real_bonds
        if nominal_bonds:
            s += nominal_bonds
        if iid_bonds:
            s += iid_bonds
        if bills:
            s += bills
        assert abs(s - 1) < 1e-15

    def __str__(self):

        s = ''
        for a in (self.stocks, self.real_bonds, self.nominal_bonds, self.iid_bonds, self.bills):
            if a != None:
                if s:
                    s += ', ' + str(a)
                else:
                    s = str(a)

        return '[' + s + ']'
