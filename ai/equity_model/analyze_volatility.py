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

# Analyze log return volatility auto correlation on a precise calender basis.

from csv import reader, writer
from datetime import datetime
from math import exp, log, sqrt
from os import environ
from os.path import expanduser
from random import choice, lognormvariate, normalvariate
from statistics import mean, median, stdev

import numpy as np
from scipy.stats import kurtosis, skew, spearmanr

home_dir = environ.get('AIPLANNER_HOME', expanduser('~/aiplanner'))
ticker_dir = home_dir + '/data/private/ticker'

# Annual volatility computed using daily volatility values
with open(ticker_dir + '/^GSPC.csv') as f:
    r = reader(f)
    next(r) # Skip header.
    daily_vols = []
    daily = []
    daily_year = []
    year = None
    prev_adj_close = None
    for date, open_price, high, low, close, adj_close, volume in r:
        y, m, d = date.split('-')
        adj_close = float(adj_close)
        if not year:
            year = y
        try:
            ret = log(adj_close) - log(prev_adj_close)
        except TypeError:
            continue
        finally:
            prev_adj_close = adj_close
        if y != year:
            daily_vols.append(stdev(daily_year) * sqrt(252)) # 252 trading days per year.
            year = y
            daily.extend(daily_year)
            daily_year = []
        daily_year.append(ret)

# Annual volatility computed using weekly volatility values
with open(ticker_dir + '/^GSPC.csv') as f:
    r = reader(f)
    next(r) # Skip header.
    weekly_vols = []
    weekly = []
    weekly_year =[]
    year = None
    prev_weekday = 0
    prev_week_adj_close = None
    for date, open_price, high, low, close, adj_close, volume in r:
        y, m, d = date.split('-')
        adj_close = float(adj_close)
        if not year:
            year = y
        if datetime.strptime(date, '%Y-%m-%d').weekday() < prev_weekday:
            try:
                ret = log(prev_adj_close) - log(prev_week_adj_close)
                weekly_year.append(ret)
            except TypeError:
                pass
            prev_week_adj_close = prev_adj_close
        prev_weekday = datetime.strptime(date, '%Y-%m-%d').weekday()
        prev_adj_close = adj_close
        if y != year:
            weekly_vols.append(stdev(weekly_year) * sqrt(52))
            year = y
            weekly.extend(weekly_year)
            weekly_year = []

# Annual volatility computed using monthly volatility values
with open(ticker_dir + '/^GSPC.csv') as f:
    r = reader(f)
    next(r) # Skip header.
    monthly_vols = []
    monthly = []
    monthly_year = []
    year = None
    prev_day = '0'
    prev_month_adj_close = None
    for date, open_price, high, low, close, adj_close, volume in r:
        y, m, d = date.split('-')
        adj_close = float(adj_close)
        if not year:
            year = y
        if int(d) < int(prev_day):
            try:
                ret = log(prev_adj_close) - log(prev_month_adj_close)
                monthly_year.append(ret)
            except TypeError:
                pass
            prev_month_adj_close = prev_adj_close
        prev_day = d
        prev_adj_close = adj_close
        if y != year:
            monthly_vols.append(stdev(monthly_year) * sqrt(12))
            year = y
            monthly.extend(monthly_year)
            monthly_year = []

# Annual volatility computed using annual volatility values
with open(ticker_dir + '/^GSPC.csv') as f:
    r = reader(f)
    next(r) # Skip header.
    yearly = []
    prev_month = '13'
    prev_year_adj_close = None
    for date, open_price, high, low, close, adj_close, volume in r:
        y, m, d = date.split('-')
        adj_close = float(adj_close)
        if int(m) < int(prev_month):
            try:
                ret = log(prev_adj_close) - log(prev_year_adj_close)
                yearly.append(ret)
            except TypeError:
                pass
            prev_year_adj_close = prev_adj_close
        prev_month = m
        prev_adj_close = adj_close

def save_and_report(fname, rets, vols, save_length):

    current_vol = vols[:-1]
    next_vol = vols[1:]

    #with open(fname, 'w') as o:
    #    w = writer(o)
    #    w.writerows(zip(current_vol[:save_length], next_vol[:save_length]))

    print(fname[:-4])

    print(mean(rets), stdev(rets), skew(rets), kurtosis(rets, fisher=False)) # Pearson's kurtosis; normal distribution has a kurtosis of 3.
    print(mean(vols), stdev(vols))

    print(np.corrcoef(current_vol, next_vol))
    print(spearmanr(current_vol, next_vol))

# Historial volatility correlation
save_and_report('daily.csv', daily, daily_vols, len(daily_vols) - 1)
save_and_report('weekly.csv', weekly, weekly_vols, len(weekly_vols) - 1)
save_and_report('monthly.csv', monthly, monthly_vols, len(monthly_vols) - 1)
print('yearly')
print(mean(yearly), stdev(yearly), skew(yearly), kurtosis(yearly, fisher = False))
print('yearly log ret corr')
print(np.corrcoef(yearly[:-1], yearly[1:]))
print(spearmanr(yearly[:-1], yearly[1:]))

print('return volatility correlation')
print(np.corrcoef(yearly[1:], daily_vols[:-1]))

# Observed log ret results:
#           mean  stdev  auto corr  skew    kurtosis
# annual     7.1% 16.2%    -0.07   -0.90      4.10
#
# Observed log vol results:
#           mean  stdev  auto corr
# daily     14.0%  6.2%     0.47
# weekly    13.8%  5.4%     0.45
# monthly   13.1%  5.3%     0.29
# annual    16.2%   -        -
#
# Sumamrized log vol results:
#           14.0%  5.6%     0.40
#
# Target values:
#      ret   6.5% 17.4%                                from Credit-Suisse Yearbook
#  log ret                  0.00   -0.90      4.10
#  log vol    -     -       0.40
# Scale up because total global market is more volatile than the S&P 500.
