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
from random import normalvariate, random, randrange, uniform
from statistics import mean

from gym_fin.envs.returns import Returns

class ReturnsEquity(Returns):

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

        self.t = randrange(len(self.z_hist))

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

        ret = 0
        for _ in range(round(self.time_period * self.periods_per_year)):
            z_t = self.z_hist[self.t]
            epsilon_t = self.sigma_t * z_t
            r_t = self.period_mu + epsilon_t
            self.log_above_trend += self.price_exaggeration * epsilon_t
            log_reversion = - self.period_mean_reversion_rate * self.log_above_trend
            self.log_above_trend += log_reversion
            r_t += log_reversion
            ret += r_t
            if random() < 1 / (self.bootstrap_years * self.periods_per_year):
                self.t = randrange(len(self.z_hist))
            else:
                self.t = (self.t + 1) % len(self.z_hist)
            z_t_1 = z_t
            sigma2_t_1 = self.sigma_t ** 2
            sigma2_t = self.omega + ((self.alpha + self.gamma * int(z_t_1 < 0)) * z_t_1 ** 2 + self.beta) * sigma2_t_1
            self.sigma_t = sqrt(sigma2_t)

        sample = exp(ret)

        self.log_price_noise = normalvariate(0, self.price_noise_sigma)

        return sample

    def observe(self):

        obs_above_trend = exp(self.log_above_trend + self.log_price_noise)
        obs_sigma_level = sqrt(self.periods_per_year) * self.sigma_t / self.sigma

        return (obs_above_trend, obs_sigma_level)
