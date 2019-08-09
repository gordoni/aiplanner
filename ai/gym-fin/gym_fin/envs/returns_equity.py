# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from csv import reader
from math import exp, log, sqrt
from random import expovariate, normalvariate, randrange, uniform
from statistics import mean

import cython

from gym_fin.envs.returns import Returns # Needs to be cimport if using Cython.

@cython.cclass
class ReturnsEquity(Returns):
    params: object
    z_hist: cython.double[:]
    sigma_hist: cython.double[:]
    sigma_average: cython.double
    bootstrap_years: cython.double
    mu: cython.double
    sigma: cython.double
    alpha: cython.double
    gamma: cython.double
    beta: cython.double
    price_exaggeration: cython.double
    price_low: cython.double
    price_high: cython.double
    price_noise_sigma: cython.double
    mean_reversion_rate: cython.double
    standard_error: cython.double
    time_period: cython.double
    periods_per_year: cython.double
    omega: cython.double
    block_size: cython.int
    sigma_t: cython.double

    period_mu: cython.double
    period_mean_reversion_rate: cython.double
    log_price_noise: cython.double
    log_above_trend: cython.double
    t: cython.int

    def __init__(self, params, std_res_fname):

        self.params = params

        assert self.params.stocks_sigma_level_type != 'invalid'

        with open(std_res_fname) as f:
            r = reader(f)
            data = tuple(r)
        self.z_hist = tuple(float(d[0]) for d in data)
        self.sigma_hist = tuple(float(d[1]) for d in data)
        self.sigma_average = sqrt(mean(sigma ** 2 for sigma in self.sigma_hist))

        self.bootstrap_years = self.params.stocks_bootstrap_years
        self.mu = self.params.stocks_mu
        self.sigma = self.params.stocks_sigma
        self.alpha = self.params.stocks_alpha
        self.gamma = self.params.stocks_gamma
        self.beta = self.params.stocks_beta
        self.price_exaggeration = self.params.stocks_price_exaggeration
        self.price_low = self.params.stocks_price_low
        self.price_high = self.params.stocks_price_high
        self.price_noise_sigma = self.params.stocks_price_noise_sigma
        self.mean_reversion_rate = self.params.stocks_mean_reversion_rate
        self.standard_error = self.params.stocks_standard_error
        self.time_period = self.params.time_period

        self.periods_per_year = 12 # Alpha, gamma, and beta would need to change if alter this.
        self.omega = (1 - self.alpha - self.gamma / 2 - self.beta) * self.sigma ** 2 / self.periods_per_year

        self.block_size = 0

        if self.params.stocks_sigma_level_type == 'sample':
            # Allow to run through resets. Better than using sigma_hist on each reset as sigma_hist isn't an exact representation of the GJR-GARCH sigma distribution.
            self.sigma_t = self.sigma_hist[self.t] / self.sigma_average * self.sigma / sqrt(self.periods_per_year)
            self._set_price() # Price also runs through resets.

        self.reset()

    def reset(self):

        if self.params.stocks_sigma_level_type == 'average':
            self.sigma_t = self.sigma / sqrt(self.periods_per_year)
        elif self.params.stocks_sigma_level_type == 'value':
            self.sigma_t = self.params.stocks_sigma_level_value * self.sigma / sqrt(self.periods_per_year)

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
        ret: cython.double
        len_z_hist: cython.int
        z_t: cython.double

        ret = 0
        len_z_hist = len(self.z_hist)
        for _ in range(round(self.time_period * self.periods_per_year)):
            while self.block_size == 0:
                self.t = randrange(len(self.z_hist))
                self.block_size = round(expovariate(1 / (self.bootstrap_years * self.periods_per_year)))
            z_t = self.z_hist[self.t]
            epsilon_t = self.sigma_t * z_t
            r_t = self.period_mu + epsilon_t
            self.log_above_trend += self.price_exaggeration * epsilon_t
            log_reversion = - self.period_mean_reversion_rate * self.log_above_trend
            self.log_above_trend += log_reversion
            r_t += log_reversion
            ret += r_t
            self.t = (self.t + 1) % len_z_hist
            self.block_size -= 1
            z_t_1 = z_t
            sigma2_t_1 = self.sigma_t ** 2
            sigma2_t = self.omega + ((self.alpha + (self.gamma if z_t_1 < 0 else 0)) * z_t_1 ** 2 + self.beta) * sigma2_t_1
            self.sigma_t = sigma2_t ** 0.5

        sample = exp(ret)

        self.log_price_noise = normalvariate(0, self.price_noise_sigma)

        return sample

    def observe(self):

        obs_above_trend = exp(self.log_above_trend + self.log_price_noise)
        obs_sigma_level = sqrt(self.periods_per_year) * self.sigma_t / self.sigma

        return (obs_above_trend, obs_sigma_level)
