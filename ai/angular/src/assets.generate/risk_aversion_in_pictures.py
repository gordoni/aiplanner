#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import ceil, exp, floor, log, sqrt

from scipy.stats import lognorm

gammas = (1, 1.5, 3, 6)

# Credit Suisse Yearbook 2017.
m = 1.065
vol = 0.174
r = 1.008

stock_mu = log(m / sqrt(1 + (vol / m) ** 2))
stock_sigma = sqrt(log(1 + (vol / m) ** 2))

print('mu sigma', stock_mu, stock_sigma)

sharpe = (stock_mu - log(r)) / stock_sigma

print('sharpe', sharpe)

f_max = 2
f_steps = 1000
step = f_max / f_steps

print('gamma pi mean stdev')
for gamma in gammas:
    # Merton's stock fraction:
    pi = (stock_mu - log(r)) / (gamma * stock_sigma ** 2)
    # So:
    #     mu = pi * stock_mu + (1 - pi) * log(r)
    #     sigma = pi * stock_sigma
    # Or:
    mu = sharpe ** 2 / gamma + log(r)
    sigma = sharpe / gamma
    mu -= log(r) # Normalize returns, so that mean for gamma = inf is 1.
    # Consider consumption C(1) at timestep t = 1 for the simple discrete case of T = 1 and fixed remaining wealth after t = 0 of W(0) * (1 - c(0)) = 1.
    # Fraction consumed at timestep 1:
    # c(1) = 1
    with open('risk_aversion_' + str(gamma) + '_pdf.csv', 'w') as f:
        for i in range(ceil(f_max * f_steps)):
            C1 = i / f_steps
            # Consume C(1) at t = 1 if C(1) = W(1) * c(1) = W(1) = W(0) * (1 - c(0)) * Z = Z.
            Z = C1
            p = lognorm.pdf(Z, sigma, scale = exp(mu)) * step
            f.write('%f,%f\n' % (C1, p))
    mn = exp(mu + sigma ** 2 / 2)
    sd = sqrt(exp(sigma ** 2) - 1) * mn
    print(gamma, pi, mn, sd)
