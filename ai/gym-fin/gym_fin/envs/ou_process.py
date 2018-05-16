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
    '''
    Ornstein-Uhlenbeck process.
    '''

    def __init__(self, rev, sigma, *, mu = 0, x = None):
        '''
        Reversion rate theta, mean mu, initial x.
        '''

        self._rev = rev
        self._sigma = sigma
        self._mu = mu
        self._x = mu if x == None else x
        self._t = 0

    def step(self, delta):

        # By https://en.wikipedia.org/wiki/Hull%E2%80%93White_model one-factor model r(t) distribution for theta constant:
        erd = exp(- self._rev * delta)

        self._x = normalvariate(self._x * erd + self._mu * (1 - erd), self._sigma * sqrt((1 - erd ** 2) / (2 * self._rev)))

        self._t += delta

    @property
    def x(self):
        return self._x

    @property
    def t(self):
        return self._t
