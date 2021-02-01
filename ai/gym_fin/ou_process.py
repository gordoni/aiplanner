# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, sqrt

import numpy as np

import cython

@cython.cclass
class OUProcess:
    '''Ornstein-Uhlenbeck process.'''

    def __init__(self, time_period, rev, sigma, *, mu = 0, x = None, norm = None):
        '''Time period time_period, reversion rate theta, mean mu, initial x, initial stochastic shock norm.'''

        self.time_period = time_period
        self._rev = rev
        self._sigma = sigma

        self._e = exp(1)
        self._last_randnorm = 0

        self.reset(mu = mu, x = x, norm = norm)

    @cython.locals(mu = cython.double)
    def reset(self, mu, x, norm):
        '''Reset the process to mean mu, initial x, initial stochastic shock norm.'''

        self._mu = mu

        self.next_x = self._mu if x is None else x

        self.step(norm = norm)

    def step(self, *, norm = None):
        '''Step the process under stochastic shock norm (generated if not supplied).'''

        if norm is None:
            if self._last_randnorm == 0:
                self._randnorm = np.random.normal(0, 1, size = 10000).tolist() # Numpy randnorms are fast.
                    # .tolist() prevents slow np.ndarray indexing and prevents np.float64 values from propagating.
                self._last_randnorm = len(self._randnorm)
            self._last_randnorm -= 1
            self.norm = self._randnorm[self._last_randnorm]
        else:
            self.norm = norm

        self.x = self.next_x

        # By https://en.wikipedia.org/wiki/Hull%E2%80%93White_model one-factor model r(t) distribution for theta constant:
        erd = self._e ** (- self._rev * self.time_period)
        sr: cython.double
        sr = sqrt((1 - erd ** 2) / (2 * self._rev))
        self.next_x = self.x * erd + self._mu * (1 - erd) + self._sigma * sr * self.norm
