#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import ceil, exp, floor, log, sqrt

from scipy.stats import lognorm

stocks = (0.6, 0.8, 1.0)

# Credit Suisse Yearbook 2020.
stock_m = 1.066
stock_vol = 0.174
bond_m = 1.0 - 0.006 # 2020-12-31 20 year TIPS.
bond_vol = 0.109

stock_mu = log(stock_m / sqrt(1 + (stock_vol / stock_m) ** 2))
stock_sigma = sqrt(log(1 + (stock_vol / stock_m) ** 2))
bond_mu = log(bond_m / sqrt(1 + (bond_vol / bond_m) ** 2))
bond_sigma = sqrt(log(1 + (bond_vol / bond_m) ** 2))

f_max = 2
f_steps = 1000
step = f_max / f_steps

print('stock p5 p1')
for stock in stocks:

    mu = stock * stock_mu + (1 - stock) * bond_mu
    sigma = sqrt((stock * stock_sigma) ** 2 + ((1 - stock) * bond_sigma) ** 2)

    with open('risk_tolerance_' + str(stock) + '_pdf.csv', 'w') as f:
        for i in range(ceil(f_max * f_steps)):
            R = i / f_steps
            Z = R
            p = lognorm.pdf(Z, sigma, scale = exp(mu)) * step
            f.write('%f,%f\n' % (R - 1, p))
    p5 = lognorm.ppf(0.05, sigma, scale = exp(mu))
    p1 = lognorm.ppf(0.01, sigma, scale = exp(mu))
    print(stock, mu, sigma, 1 - p5, 1 - p1)
