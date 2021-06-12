# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, isnan, log

import cython

@cython.cclass
class Utility:

    def __init__(self, gamma, floor, consume_charitable, consume_charitable_utility_factor, consume_charitable_gamma, consume_charitable_discount_rate):

        self.gamma = gamma
        self.consume_charitable = consume_charitable
        self.consume_charitable_utility_factor = consume_charitable_utility_factor
        self.consume_charitable_gamma = consume_charitable_gamma
        self.consume_charitable_discount_rate = consume_charitable_discount_rate

        self.utility_scale = 1 # Temporary scale for inverse().
        self.crra_utility_base = self.crra_utility(self.gamma, self.consume_charitable)
        self.crra_utility_charitable = self.crra_utility(self.consume_charitable_gamma, self.consume_charitable)
        self.marginal_utility_factor = self.consume_charitable_utility_factor * self.consume_charitable ** (self.consume_charitable_gamma - self.gamma)

        self.utility_scale = floor / self.inverse(-1) # Make utility(consume_floor) = -1.
        self.crra_utility_base = self.crra_utility(self.gamma, self.consume_charitable)
        self.crra_utility_charitable = self.crra_utility(self.consume_charitable_gamma, self.consume_charitable)
        self.marginal_utility_factor = self.consume_charitable_utility_factor * \
            (self.consume_charitable / self.utility_scale) ** (self.consume_charitable_gamma - self.gamma)

    @cython.locals(gamma = cython.double, c = cython.double)
    def crra_utility(self, gamma, c):

        if c == 0 and gamma >= 1:
            return float('-inf')

        if gamma == 1:
            return log(c / self.utility_scale)
        else:
            return (c / self.utility_scale) ** (1 - gamma) / (1 - gamma)
                # Incompatible with gamma=1, because not shifted so that utility(utility_scale) = 0.
                # We do not shift to avoid losing any possible floating point precision.

    @cython.locals(c = cython.double, t = cython.double)
    def utility(self, c, t = 0):

        u: cython.double

        if c <= self.consume_charitable:
            u = self.crra_utility(self.gamma, c)
        else:
            u = self.crra_utility_base + self.marginal_utility_factor * \
                (self.crra_utility(self.consume_charitable_gamma, c) - self.crra_utility_charitable) * (1 - self.consume_charitable_discount_rate) ** t

        return u

    @cython.locals(gamma = cython.double, u = cython.double)
    def crra_inverse(self, gamma, u):

        if u == float('-inf') and gamma >= 1:
            return 0

        if gamma == 1:
            return exp(u) * self.utility_scale
        else:
            return (u * (1 - gamma)) ** (1 / (1 - gamma)) * self.utility_scale

    @cython.locals(u = cython.double)
    def inverse(self, u):

        c: cython.double

        if u <= self.crra_utility_base:
            c = self.crra_inverse(self.gamma, u)
        elif isnan(u):
            c = float('nan')
        else:
            c = self.crra_inverse(self.consume_charitable_gamma, self.crra_utility_charitable + (u - self.crra_utility_base) / self.marginal_utility_factor)

        return c
