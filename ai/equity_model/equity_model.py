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
from math import ceil, exp, log, sqrt
from os import environ
from os.path import expanduser
from random import random, randrange
from statistics import mean, median, stdev

import numpy as np
from scipy.stats import skew, kurtosis, spearmanr

import pandas

from arch import arch_model

start_date = '1990-01-01'
    # Get weaker correlation between observed sigma_t and next year's monthly volatility if start from 1950.
    # Possibly because assets weren't priced as accurately back then.
    # Follow V-lab (https://vlab.stern.nyu.edu/analysis/VOL.SPX%3AIND-R.GJR-GARCH) and use 1990 as the starting date for analysis.
    # 29 years might not appear a very long time period over which to bootstrap returns.
    # However, these are monthly returns, not annual returns, and we only use them for the normalized stochastic shock, z_t, not the actual return.
    # We adjust the mean and volatility to match the longer historical record.
    # In summary, we use the recent era for volatility predictability, and the historical record for volatility level and returns.
end_date = '2018-12-31'

MEDIAN_ANALYSIS_YEARS = 2018 - 1950 + 1

BOOTSTRAP_BLOCK_YEARS = 5
    # Bootstrap based on a mean block size of 5 years (consider history as being made up of on average 5 year length blocks).

TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_PERIOD = 21
    # Monthly instead of daily model.
    # Need to compute returns monthly instead of daily for speed of simulation.
    # Use of an even faster quarterly model results in too large standard errors of GJR-GARCH model.
PERIODS_PER_YEAR = ceil(TRADING_DAYS_PER_YEAR / TRADING_DAYS_PER_PERIOD)

SCALE = 100 # Need to make greater than 1 if have a small TRADING_DAYS_PER_PERIOD so as to prevent optimizer failing to fit parameters properly.
    # mu and omega are scale dependent, whle alpha, gamma, and beta are scale independent.

home_dir = environ.get('AIPLANNER_HOME', expanduser('~/aiplanner'))
ticker_dir = home_dir + '/data/private/ticker'

sp500 = pandas.read_csv(ticker_dir + '/^SP500TR.csv') if start_date >= '1988-01-01' else pandas.read_csv(ticker_dir + '/^GSPC.csv')

mask = (start_date <= sp500['Date']) & (sp500['Date'] <= end_date)
sp500mask = sp500[mask]
sp500mask = sp500mask[::TRADING_DAYS_PER_PERIOD]
returns = SCALE * np.log(1 + sp500mask['Adj Close'].pct_change().dropna())

am = arch_model(returns, p=1, o=1, q=1, dist='StudentsT') # GJR-GARCH.
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
    w.writerows([[z] for z in z_hist])

print('Historically sigma_t has been higly predictive of following year volatility, and less so absolute return:')
hist_sigmas = sqrt(PERIODS_PER_YEAR) * res.conditional_volatility / SCALE
hist_vol = tuple(sqrt(PERIODS_PER_YEAR) * stdev(returns[i:i + PERIODS_PER_YEAR] / SCALE) for i in range(len(returns) - PERIODS_PER_YEAR))
hist_abs_ret = tuple(abs(sum(returns[i:i + PERIODS_PER_YEAR] - mu) / SCALE) for i in range(len(returns) - PERIODS_PER_YEAR))
print(mean(hist_vol), stdev(hist_vol))
print(mean(hist_sigmas), stdev(hist_sigmas))
print(np.corrcoef(hist_vol, hist_sigmas[:- PERIODS_PER_YEAR]))
print(spearmanr(hist_vol, hist_sigmas[:- PERIODS_PER_YEAR]))
print(np.corrcoef(hist_abs_ret, hist_sigmas[:- PERIODS_PER_YEAR]))
print(spearmanr(hist_abs_ret, hist_sigmas[:- PERIODS_PER_YEAR]))

# Set mu and omega to yield desired ret and vol.
mean_reversion_rate = 0.1
ret = 0.061 # Adjust to get 0.065 actual mean ret
vol = 0.159 # Adjust to get 0.174 actual vol
m = 1 + ret
mu = log(m / sqrt(1 + (vol / m) ** 2))
sigma = sqrt(log(1 + (vol / m) ** 2))
mu *= SCALE / PERIODS_PER_YEAR
sigma /= sqrt(PERIODS_PER_YEAR)
omega = SCALE ** 2 * (1 - alpha - gamma / 2 - beta) * sigma ** 2

num_simulated_rets = 100000
mean_bootstrap_block_size = BOOTSTRAP_BLOCK_YEARS * PERIODS_PER_YEAR
rets = []
obs_sigmas = []
exper_vol = []
exper_abs_ret = []
epsilon_t_1 = 0
sigma_t_1 = sqrt(omega / (1 - alpha - gamma / 2 - beta))
log_above_trend = 0
z_t_1 = epsilon_t_1 / sigma_t_1
sigma2_t_1 = sigma_t_1 ** 2
i = randrange(len(z_hist))
p = 0
ret = 0
retl = []
while len(rets) < num_simulated_rets:
    sigma2_t = omega + ((alpha + gamma * int(z_t_1 < 0)) * z_t_1 ** 2 + beta) * sigma2_t_1
    sigma_t = sqrt(sigma2_t)
    z_t = z_hist[i]
    r_t = mu + sigma_t * z_t
    r_t /= SCALE
    log_above_trend += r_t - mu / SCALE
    log_reversion = - mean_reversion_rate / PERIODS_PER_YEAR * log_above_trend
    log_above_trend += log_reversion
    r_t += log_reversion
    ret += r_t
    retl.append(r_t)
    p += 1
    if p >= PERIODS_PER_YEAR:
        rets.append(ret)
        obs_sigmas.append(sqrt(PERIODS_PER_YEAR) * sigma_t / SCALE)
        exper_vol.append(sqrt(PERIODS_PER_YEAR) * stdev(retl))
        exper_abs_ret.append(abs(sum(retl) - mu / SCALE))
        p = 0
        ret = 0
        retl = []
    z_t_1 = z_t
    sigma2_t_1 = sigma2_t
    if random() < 1 / mean_bootstrap_block_size:
        i = randrange(len(z_hist))
    else:
        i += 1
        if i == len(z_hist):
            i = 0

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
print(np.corrcoef(exper_abs_ret[1:], obs_sigmas[:-1]))
print(spearmanr(exper_abs_ret[1:], obs_sigmas[:-1]))
print(np.corrcoef(exper_vol[1:], obs_sigmas[:-1]))
print(spearmanr(exper_vol[1:], obs_sigmas[:-1]))
print(np.corrcoef(exper_vol[1:], exper_vol[:-1]))
print(spearmanr(exper_vol[1:], exper_vol[:-1]))

# Target values:
#           mean  stdev  auto corr  skew    kurtosis  vol-sigma corr
#      ret   6.5% 17.4%                                               from Credit-Suisse Yearbook
#  log ret                  0.00   -0.90      4.10        0.48        from analyze_volatility.py; except vol-sigma corr from this script
#  log vol    -     -       0.40                                      from analyze_volatility.py
#
# Measured simulated values:
#           mean  stdev  auto corr  skew    kurtosis
#      ret   6.5% 17.4%
#  log ret                  0.05   -1.16      5.10        0.44
#  log vol    -     -       0.39
#
# Larger measured negative skew and kurtosis is a result of using 1990 as the starting point.
# The target auto corr, skew, and kurtosis target values are based on using 1950 as the starting point.
# There has been more negative skew and kurtosis since then than over the longer history.
