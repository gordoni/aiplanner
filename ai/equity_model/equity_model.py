#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

# Determine GJR_GARCH parameters, write out standardized residuals, and simulate and evaluate equity model.

from csv import writer
from math import exp, log, sqrt
from os import environ
from os.path import expanduser
from random import normalvariate, random, randrange, seed
from statistics import mean, median, stdev

import numpy as np
from scipy.stats import skew, kurtosis, spearmanr

import pandas

from arch import arch_model

start_date = '1970-01-01'
    # Get weaker correlation between observed sigma_t and next year's monthly volatility if start from 1950, the earliest date for which we have data.
    # Possibly because assets weren't priced as accurately back then due to the paucity of computers.
    # Get stronger correlation if follow V-lab (https://vlab.stern.nyu.edu/analysis/VOL.SPX%3AIND-R.GJR-GARCH) and use 1990 as the starting date for analysis.
    # The problem with using 1990 as the starting date is it represents a 29 year period with 2 major crashes, which is more frequent than usual.
    # This leads to excessive skew and kurtosis.
    # So we compromise and use 1970 as the starting date.
    # We adjust the mean and volatility to match the longer historical record.
    # In summary, we use 1970 on for volatility predictability, and the longer historical record for volatility level and returns.
end_date = '2018-12-31'

MEDIAN_ANALYSIS_YEARS = 2018 - 1950 + 1

BOOTSTRAP = True
    # If no bootstrap, use normal residuals.
BOOTSTRAP_BLOCK_YEARS = 0
    # Bootstrap based on a mean block size of this many years (consider history as being made up of on average this many year length blocks).
    # Don't bootstrap with a non-zero block size, or else observed volatility - future return correlation will be at the mercy of the historical time period chosen.

TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_PERIOD = 21
    # Monthly instead of daily model.
    # Need to compute returns monthly instead of daily for speed of simulation.
    # Use of an even faster quarterly model results in too large standard errors of GJR-GARCH model.
PERIODS_PER_YEAR = round(TRADING_DAYS_PER_YEAR / TRADING_DAYS_PER_PERIOD)

SCALE = 100 # Need to make greater than 1 if have a small TRADING_DAYS_PER_PERIOD so as to prevent optimizer failing to fit parameters properly.
    # mu and omega are scale dependent, while alpha, gamma, and beta are scale independent.

home_dir = environ.get('AIPLANNER_HOME', expanduser('~/aiplanner'))
ticker_dir = home_dir + '/data/private/ticker'

sp500 = pandas.read_csv(ticker_dir + '/^SP500TR.csv') if start_date >= '1988-01-01' else pandas.read_csv(ticker_dir + '/^GSPC.csv')

mask = (start_date <= sp500['Date']) & (sp500['Date'] <= end_date)
sp500mask = sp500[mask]
sp500mask = sp500mask[::TRADING_DAYS_PER_PERIOD]
returns = SCALE * np.log(1 + sp500mask['Adj Close'].pct_change().dropna())

am = arch_model(returns, p=1, o=1, q=1, dist='Normal') # GJR-GARCH.
res = am.fit()
print(res.summary())
params = res.params
mu = params['mu']
omega = params['omega']
alpha = params['alpha[1]']
gamma = params['gamma[1]']
beta = params['beta[1]']

#print(res.resid[-3:]) # epsilon_t = sigma_t x z_t
#print(res.conditional_volatility[-3:]) # sigma_t
z_hist = tuple(res.resid / res.conditional_volatility)

with open('standardized_residuals.csv', 'w') as f:
    w = writer(f)
    w.writerows([[z, sqrt(PERIODS_PER_YEAR) * v / SCALE] for z, v in zip(z_hist, res.conditional_volatility)])

print('Historically sigma_t has been higly predictive of following year volatility:')
hist_sigmas = sqrt(PERIODS_PER_YEAR) * res.conditional_volatility / SCALE
hist_vol = tuple(sqrt(PERIODS_PER_YEAR) * stdev(returns[i:i + PERIODS_PER_YEAR] / SCALE) for i in range(len(returns) - PERIODS_PER_YEAR))
print(mean(hist_vol), stdev(hist_vol))
print(mean(hist_sigmas), stdev(hist_sigmas))
print(np.corrcoef(hist_vol, hist_sigmas[:- PERIODS_PER_YEAR]))
print(spearmanr(hist_vol, hist_sigmas[:- PERIODS_PER_YEAR]))

seed(0)

# Set mu and omega to yield desired ret and vol.
mean_reversion_rate = 0.1 # Rough estimate
exaggeration = 0.7 # Adjust to get reasonable looking above_trend.csv plot
mu = 0.065 # Adjust to get 0.065 actual mean ret
sigma = 0.160 # Adjust to get 0.174 actual vol
mu *= SCALE / PERIODS_PER_YEAR
sigma /= sqrt(PERIODS_PER_YEAR)
omega = SCALE ** 2 * (1 - alpha - gamma / 2 - beta) * sigma ** 2

num_simulated_rets = 1000000
num_trace_years = 1000
mean_bootstrap_block_size = BOOTSTRAP_BLOCK_YEARS * PERIODS_PER_YEAR
rets = []
obs_sigmas = []
exper_vol = []
above_trend = []
epsilon_t_1 = 0
sigma_t_1 = sqrt(omega / (1 - alpha - gamma / 2 - beta))
log_index = [0]
log_trend = [0]
sigma_periodic = [sqrt(PERIODS_PER_YEAR) * sigma_t_1 / SCALE]
log_above_trend = 0
z_t_1 = epsilon_t_1 / sigma_t_1
sigma2_t_1 = sigma_t_1 ** 2
i = randrange(len(z_hist))
p = 0
ret = 0
retl = []
returns = 0
while returns < num_simulated_rets:
    sigma2_t = omega + ((alpha + (gamma if z_t_1 < 0 else 0)) * z_t_1 ** 2 + beta) * sigma2_t_1
    sigma_t = sqrt(sigma2_t)
    z_t = z_hist[i] if BOOTSTRAP else normalvariate(0, 1)
    epsilon_t = sigma_t * z_t
    r_t = mu - sigma2_t / (2 * SCALE) + epsilon_t
    r_t /= SCALE
    log_above_trend += exaggeration * epsilon_t / SCALE
    log_reversion = - mean_reversion_rate / PERIODS_PER_YEAR * log_above_trend
    log_above_trend += log_reversion
    r_t += log_reversion
    ret += r_t
    retl.append(r_t)
    if len(log_index) <= num_trace_years * PERIODS_PER_YEAR:
        log_index.append(log_index[-1] + r_t)
        log_trend.append(log_index[-1] - log_above_trend)
        sigma_periodic.append(sqrt(PERIODS_PER_YEAR) * sigma_t / SCALE)
    p += 1
    if p >= PERIODS_PER_YEAR:
        rets.append(ret)
        obs_sigmas.append(sqrt(PERIODS_PER_YEAR) * sigma_t / SCALE)
        exper_vol.append(sqrt(PERIODS_PER_YEAR) * stdev(retl))
        above_trend.append(exp(log_above_trend))
        returns += 1
        retl = []
        ret = 0
        p = 0
    z_t_1 = z_t
    sigma2_t_1 = sigma2_t
    if BOOTSTRAP:
        if random() * mean_bootstrap_block_size < 1:
            i = randrange(len(z_hist))
        else:
            i += 1
            if i == len(z_hist):
                i = 0

with open('index.csv', 'w') as f:
    w = writer(f)
    for t, (index, trend, s) in enumerate(zip(log_index, log_trend, sigma_periodic)):
        w.writerow([t / PERIODS_PER_YEAR, index, trend, s])

at_hist = {}
density = 20
for at in above_trend:
    key = (at * density + 0.5) // 1 / density
    try:
        at_hist[key] += density / len(above_trend)
    except KeyError:
        at_hist[key] = density / len(above_trend)
with open('above_trend.csv', 'w') as f:
    w = writer(f)
    for at in sorted(at_hist):
        w.writerow([at, at_hist[at]])

print('Simulated returns (actual, log, and median log per sample; log ret corr):')
non_log_rets = tuple(exp(ret) for ret in rets)
print(mean(non_log_rets), stdev(non_log_rets), skew(non_log_rets), kurtosis(non_log_rets, fisher = False))
print(mean(rets), stdev(rets), skew(rets), kurtosis(rets, fisher = False))
rs = [rets[i * MEDIAN_ANALYSIS_YEARS:(i + 1) * MEDIAN_ANALYSIS_YEARS] for i in range(len(rets) // MEDIAN_ANALYSIS_YEARS)]
print(median((mean(r) for r in rs)), median((stdev(r) for r in rs)), median((skew(r) for r in rs)), median((kurtosis(r, fisher = False) for r in rs)))
print(np.corrcoef(rets[1:], rets[:-1]))
print(spearmanr(rets[1:], rets[:-1]))

print('Simulated volatility predictability:')
print(mean(exper_vol), stdev(exper_vol))
print(mean(obs_sigmas), stdev(obs_sigmas))
print(np.corrcoef(exper_vol[1:], obs_sigmas[:-1]))
print(spearmanr(exper_vol[1:], obs_sigmas[:-1]))
print(np.corrcoef(exper_vol[1:], exper_vol[:-1]))
print(spearmanr(exper_vol[1:], exper_vol[:-1]))

print('Return volatility correlation:')
print(np.corrcoef(rets[1:], obs_sigmas[:-1]))
print(spearmanr(rets[1:], obs_sigmas[:-1]))

# Target values:
#           mean  stdev  auto corr  skew    kurtosis  vol-sigma corr  ret-sigma corr
#      ret   6.5% 17.4%                                                               from Credit-Suisse Yearbook
#  log ret                  0.00   -0.92      4.12                       unknown      from analyze_volatility.py; ecept ret-sigma corr
#  log vol    -     -       0.40                          0.39                        from analyze_volatility.py; except vol-sigma corr from this script
#
# Measured simulated values:
#           mean  stdev  auto corr  skew    kurtosis
#      ret   6.5% 17.4%
#  log ret                  0.06   -0.97      4.84                       -0.07
#  log vol    -     -       0.38                          0.46
