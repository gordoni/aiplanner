# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

# Have Cython cimport problems if ReturnsIID and ReturnsEquity are defined in separate files.

from csv import reader
from math import exp, log, sqrt
from random import expovariate,  lognormvariate, normalvariate, uniform
from statistics import mean,stdev

import numpy as np

import cython

@cython.cclass
class Returns:

    def reset(self):

        assert False

    def sample(self):

        assert False

    def observe(self):

        return (1, 1)

@cython.cclass
class ReturnsIID(Returns):

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

        sample = lognormvariate(self.period_mu, self.period_sigma)

        return sample

z_hist = None
sigma_hist = None
sigma_average = -1

@cython.cclass
class ReturnsEquity(Returns):

    def __init__(self, params, std_res_fname):

        global z_hist, sigma_hist, sigma_average

        self.params = params

        assert self.params.stocks_sigma_level_type != 'invalid'

        self.bootstrap = self.params.stocks_model == 'bootstrap'

        if z_hist is None:
            if self.bootstrap or self.params.stocks_sigma_level_type == 'sample':
                with open(std_res_fname) as f:
                    r = reader(f)
                    data = tuple(r)
                z_hist = tuple(float(d[0]) for d in data)
                sigma_hist = tuple(float(d[1]) for d in data)
                sigma_average = sqrt(mean(sigma ** 2 for sigma in sigma_hist))
            else:
                z_hist = (0.0, ) # Dummy.

        self.bootstrap_years = self.params.stocks_bootstrap_years
        self.sigma_max = self.params.stocks_sigma_max
        self.mu = self.params.stocks_mu
        self.sigma = min(self.params.stocks_sigma, self.sigma_max)
        self.alpha = self.params.stocks_alpha
        self.gamma = self.params.stocks_gamma
        self.beta = self.params.stocks_beta
        self.price_exaggeration = self.params.stocks_price_exaggeration
        self.price_low = self.params.stocks_price_low
        self.price_high = self.params.stocks_price_high
        assert self.price_low != -1
        assert self.price_high != -1
        self.price_noise_sigma = self.params.stocks_price_noise_sigma
        self.mean_reversion_rate = self.params.stocks_mean_reversion_rate
        self.standard_error = self.params.stocks_standard_error if self.params.returns_standard_error else 0.0
        self.time_period = self.params.time_period

        self.e = exp(1) # Cython - self.e ** x which uses the C pow function is faster than calling the Python exp(x).

        self.periods_per_year = 12 # Alpha, gamma, and beta would need to change if alter this.
        self.sigma_period = self.sigma / sqrt(self.periods_per_year)
        self.sigma_max /= sqrt(self.periods_per_year)
        self.omega = (1 - self.alpha - self.gamma / 2 - self.beta) * self.sigma ** 2 / self.periods_per_year

        self.block_size = 0
        while self.block_size == 0:
            self.block_size = 1 if self.bootstrap_years == 0 else round(expovariate(1 / (self.bootstrap_years * self.periods_per_year)))
        self.t = np.random.randint(len(sigma_hist))

        self.last_randint = 0
        self.last_randnorm = 0

        if self.params.stocks_sigma_level_type == 'sample':
            # Allow to run through resets. Better than using sigma_hist on each reset as sigma_hist isn't an exact representation of the GJR-GARCH sigma distribution.
            self.sigma_t = sigma_hist[self.t] / sigma_average * self.sigma_period
            self._set_price() # Price also runs through resets.

        self.reset()

    def reset(self):

        if self.params.stocks_sigma_level_type == 'average':
            self.sigma_t = self.sigma_period
        elif self.params.stocks_sigma_level_type == 'value':
            assert self.params.stocks_sigma_level_value != -1
            self.sigma_t = self.params.stocks_sigma_level_value * self.sigma_period

        mu = normalvariate(self.mu, self.standard_error)
        self.period_mu = mu / self.periods_per_year
        self.period_mean_reversion_rate = self.mean_reversion_rate / self.periods_per_year

        if self.params.stocks_sigma_level_type != 'sample':
            self._set_price()

    def _set_price(self):

        self.log_price_noise = normalvariate(0, self.price_noise_sigma)
        self.log_above_trend = uniform(log(self.price_low), log(self.price_high))
        self.log_above_trend -= self.log_price_noise

    def sample(self):
        '''Sample the returns, also of necessity steps the returns.'''

        ret: cython.double; len_z_hist: cython.int; periods: cython.int; z_t: cython.double

        global z_hist, sigma_hist, sigma_average

        ret = 0
        sigma2_t = self.sigma_t ** 2
        len_z_hist = len(z_hist)
        periods = int(self.time_period * self.periods_per_year + 0.5)
        for _ in range(periods):
            while self.block_size == 0:
                if self.last_randint == 0:
                    self.randints = np.random.randint(len_z_hist, size = 10000).tolist() # Numpy randints are fast.
                        # .tolist() prevents slow np.ndarray indexing and prevents np.int64 values from propagating.
                    self.last_randint = len(self.randints)
                self.last_randint -= 1
                self.t = self.randints[self.last_randint]
                self.block_size = 1 if self.bootstrap_years == 0 else int(expovariate(1 / (self.bootstrap_years * self.periods_per_year)) + 0.5)
            z_t = z_hist[self.t] if self.bootstrap else normalvariate(0, 1)
            if self.bootstrap:
                self.t = (self.t + 1) % len_z_hist
                self.block_size -= 1
            epsilon_t = self.sigma_t * z_t
            r_t = self.period_mu - sigma2_t / 2 + epsilon_t
            self.log_above_trend += self.price_exaggeration * epsilon_t
            log_reversion = - self.period_mean_reversion_rate * self.log_above_trend
            self.log_above_trend += log_reversion
            r_t += log_reversion
            ret += r_t
            z_t_1 = z_t
            sigma2_t_1 = sigma2_t
            sigma2_t = self.omega + ((self.alpha + (self.gamma if z_t_1 < 0 else 0)) * z_t_1 ** 2 + self.beta) * sigma2_t_1
            self.sigma_t = sigma2_t ** 0.5
            if self.sigma_t > self.sigma_max:
                self.sigma_t = self.sigma_max
                sigma2_t = self.sigma_t ** 2

        sample = self.e ** ret

        if self.last_randnorm == 0:
            self.randnorm = np.random.normal(0, self.price_noise_sigma, size = 10000).tolist() # Numpy randnorms are fast.
                # .tolist() prevents slow np.ndarray indexing and prevents np.float64 values from propagating.
            self.last_randnorm = len(self.randnorm)
        self.last_randnorm -= 1
        self.log_price_noise = self.randnorm[self.last_randnorm]

        return sample

    def observe(self):

        obs_above_trend = self.e ** (self.log_above_trend + self.log_price_noise)
        obs_sigma_level = self.sigma_t / self.sigma_period

        return obs_above_trend, obs_sigma_level

def _report(name, rets):

    avg = mean(rets) - 1
    vol = stdev(rets)
    geomean = exp(mean(log(r) for r in rets)) - 1
    stderr = vol / sqrt(len(rets) - 1)

    print('    {:16s}  {:5.2%} +/- {:6.2%} (geometric {:5.2%}; stderr {:5.2%})'.format(name, avg, vol, geomean, stderr))

def yields_report(name, returns, *, duration, time_period, stepper, sample_size = 10000):

    ylds = []
    for _ in range(sample_size):
        ylds.append(returns.discount_rate(duration))
        stepper.step()

    _report(name, ylds)

def returns_report(name, sampler, *, stepper = None, resetter = None, time_period = None, sample_count = 1000, sample_skip = 100, sample_length = 100):

    assert not (stepper and resetter)

    rets = []
    for _ in range(sample_count):
        if stepper:
            stepper.reset()
        elif resetter:
            resetter.reset()
        # Skip samples influenced by initial market data.
        for _ in range(sample_skip):
            sampler()
            if stepper:
                stepper.step()
        for _ in range(sample_length):
            rets.append(sampler() ** (1 / time_period))
            if stepper:
                stepper.step()

    _report(name, rets)
