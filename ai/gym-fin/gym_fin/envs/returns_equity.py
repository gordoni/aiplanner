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
        self.price_low = self.params.stocks_price_low
        self.price_high = self.params.stocks_price_high
        self.price_noise_sigma = self.params.stocks_price_noise_sigma
        self.mean_reversion_rate = self.params.stocks_mean_reversion_rate
        self.standard_error = self.params.stocks_standard_error
        self.time_period = self.params.time_period

        self.periods_per_year = 12 # Alpha, gamma, and beta would need to change if alter this.
        self.omega = (1 - self.alpha - self.gamma / 2 - self.beta) * self.sigma ** 2 / self.periods_per_year

        self.reset()

    def reset(self):

        i = randrange(len(self.z_hist))

        if self.params.stocks_previous_epsilon_type == 'sample':
            epsilon_t_1 = self.sigma_hist[i] * self.z_hist[i]
        elif self.params.stocks_previous_epsilon_type == 'average':
            epsilon_t_1 = 0
        else:
            epsilon_t_1 = self.params.stocks_previous_epsilon_value

        if self.params.stocks_previous_sigma_type == 'sample':
            sigma = self.sigma_hist[i]
        elif self.params.stocks_previous_sigma_type == 'average':
            sigma = self.sigma_average
        else:
            sigma = self.params.stocks_previous_sigma_value
        sigma_t_1 = sigma / sqrt(self.periods_per_year)

        self.z_t_1 = epsilon_t_1 / sigma_t_1
        self.sigma2_t_1 = sigma_t_1 ** 2
        self.i = randrange(len(self.z_hist))

        self.log_price_noise = normalvariate(0, self.price_noise_sigma)

        mu = normalvariate(self.mu, self.standard_error)
        self.period_mu = mu / self.periods_per_year
        above_trend = uniform(self.price_low, self.price_high)
        self.log_above_trend = log(above_trend) - self.log_price_noise
        self.period_mean_reversion_rate = self.mean_reversion_rate / self.periods_per_year

    def sample(self):
        '''Sample the returns, also of necessity steps the returns.'''

        ret = 0
        for _ in range(round(self.time_period * self.periods_per_year)):
            sigma2_t = self.omega + ((self.alpha + self.gamma * int(self.z_t_1 < 0)) * self.z_t_1 ** 2 + self.beta) * self.sigma2_t_1
            sigma_t = sqrt(sigma2_t)
            z_t = self.z_hist[self.i]
            r_t = self.period_mu + sigma_t * z_t
            self.log_above_trend += r_t - self.period_mu
            log_reversion = - self.period_mean_reversion_rate * self.log_above_trend
            self.log_above_trend += log_reversion
            r_t += log_reversion
            ret += r_t
            self.z_t_1 = z_t
            self.sigma2_t_1 = sigma2_t
            if random() < 1 / (self.bootstrap_years * self.periods_per_year):
                self.i = randrange(len(self.z_hist))
            else:
                self.i = (self.i + 1) % len(self.z_hist)

        sample = exp(ret)

        self.log_price_noise = normalvariate(0, self.price_noise_sigma)

        return sample

    def observe(self):

        obs_above_trend = exp(self.log_above_trend + self.log_price_noise)

        sigma2_t = self.omega + ((self.alpha + self.gamma * int(self.z_t_1 < 0)) * self.z_t_1 ** 2 + self.beta) * self.sigma2_t_1
        obs_sigma = sqrt(self.periods_per_year * sigma2_t)

        return (obs_above_trend, obs_sigma)
