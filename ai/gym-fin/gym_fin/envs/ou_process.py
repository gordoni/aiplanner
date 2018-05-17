# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, sqrt
from random import normalvariate

class OUProcess(object):
    '''Ornstein-Uhlenbeck process.'''

    def __init__(self, time_period, rev, sigma, *, mu = 0, x = None, norm = None):
        '''Time period time_period, reversion rate theta, mean mu, initial x, initial stochastic shock norm.'''

        self.time_period = time_period
        self._rev = rev
        self._sigma = sigma
        self._mu = mu
        self.next_x = mu if x == None else x

        return self.step(norm = norm)

    def step(self, *, norm = None):
        '''Step the process under stochastic shock norm (generated if not
        supplied), and return the stochastic shock.

        '''

        if norm == None:
            norm = normalvariate(0, 1)
        self.norm = norm

        self.x = self.next_x

        # By https://en.wikipedia.org/wiki/Hull%E2%80%93White_model one-factor model r(t) distribution for theta constant:
        erd = exp(- self._rev * self.time_period)
        self.next_x = self.x * erd + self._mu * (1 - erd) + self._sigma * sqrt((1 - erd ** 2) / (2 * self._rev)) * norm
