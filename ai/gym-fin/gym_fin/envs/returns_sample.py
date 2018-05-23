# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp
from random import choice, normalvariate

class ReturnsSample(object):

    def __init__(self, returns, duration, standard_error, *, stepper, time_period, sample_size = 100000):
        # Need a large sample size to avoid introducing any returns bias due to large standard deviation of returns.

        self.standard_error = standard_error
        self.time_period = time_period

        buffer = []
        for _ in range(sample_size):
            buffer.append(returns.sample(duration))
            stepper.step()
        self.buffer = tuple(buffer)

        self.reset()

    def reset(self):

        self.adjust = exp(normalvariate(0, self.standard_error) * self.time_period)

    def sample(self):

        return choice(self.buffer) * self.adjust
