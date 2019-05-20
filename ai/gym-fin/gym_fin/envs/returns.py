# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, log, sqrt
from random import lognormvariate, normalvariate
from statistics import mean, stdev

class Returns(object):

    def __init__(self, ret, vol, standard_error, time_period):

        self.ret = ret
        self.vol = vol
        self.standard_error = standard_error
        self.time_period = time_period

        self.reset()

    def reset(self):

        m = 1 + self.ret
        self.mu = log(m / sqrt(1 + (self.vol / m) ** 2))
        self.sigma = sqrt(log(1 + (self.vol / m) ** 2))

        mu = normalvariate(self.mu, self.standard_error)

        self.period_mu = mu * self.time_period
        self.period_sigma = self.sigma * sqrt(self.time_period)

    def sample(self):
        '''Sample the returns, also of necessity steps the returns.'''

        sample = lognormvariate(self.period_mu, self.period_sigma) # Caution: If switch to using numpy need to get/set numpy state in evaluator.py:evaluate().

        return sample

    def observe(self):

        return (1, 1)

def _report(name, rets):

    avg = mean(rets) - 1
    vol = stdev(rets)
    geomean = exp(mean(log(r) for r in rets)) - 1
    stderr = vol / sqrt(len(rets) - 1)

    print('    {:16s}  {:5.2%} +/- {:6.2%} (geometric {:5.2%}; stderr {:5.2%})'.format(name, avg, vol, geomean, stderr))

def yields_report(name, returns, *, duration, time_period, stepper, sample_size = 10000):

    ylds = []
    for _ in range(sample_size):
        ylds.append(exp(returns.spot(duration)))
        stepper.step()

    _report(name, ylds)

def returns_report(name, returns, *, time_period, stepper = None, sample_count = 1000, sample_skip=100, sample_length=100, **kwargs):

    rets = []
    for _ in range(sample_count):
        returns.reset()
        if stepper:
            stepper.reset()
        # Skip samples influenced by initial market data.
        for _ in range(sample_skip):
            returns.sample(**kwargs)
            if stepper:
                stepper.step()
        for _ in range(sample_length):
            rets.append(returns.sample(**kwargs) ** (1 / time_period))
            if stepper:
                stepper.step()

    _report(name, rets)
