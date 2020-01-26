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

from argparse import ArgumentParser
from datetime import datetime, timedelta
from json import dumps, loads
from os.path import expanduser
from re import search
from sys import stdin
from urllib.request import urlopen

def update(root_dir, read_stdin, write_stdout):

    page = stdin.read() if read_stdin else urlopen('https://docs.google.com/spreadsheets/d/1ZsyjisPp59vllL3JdHniK10t_2edj6Z-UxlpY8u_9yE/export?format=csv').read().decode('utf-8')

    vix_str, date_str = search('VIX,(\d+\.\d+),,(\d{4}-\d{2}-\d{2})', page).groups()
    vix = float(vix_str)
    date = datetime.strptime(date_str, '%Y-%m-%d')

    if write_stdout:
        print(date_str, vix)

    # Estimate of current observed monthly annualized stock market volatility relative to long term average.
    # For 1950-2108 the daily volatility of log returns of the S&P 500 was 14.0.
    #
    # VIX is a measure of the expected volatility of the S&P 500 over the next month rather than the current volatility, but hopefully this is close enough.
    level = vix / 14.0

    now = datetime.utcnow()
    assert now - timedelta(days = 7) < date <= now
    assert 0.5 < level < 5.0

    if write_stdout:
        print(level)
    else:
        try:
            f = open(root_dir + '/market-data.json')
            data = loads(f.read())
        except IOError:
            data = {}
        data['stocks_volatility'] = level
        data['stocks_volatility_date'] = date_str
        with open(root_dir + '/market-data.json', 'w') as f:
            print(dumps(data, indent = 4, sort_keys = True), file = f)

def main():

    parser = ArgumentParser()

    parser.add_argument('--root-dir', default = '~/aiplanner-data/webroot/apiserver')
    parser.add_argument('--stdin', action = 'store_true', default = False)
    parser.add_argument('--stdout', action = 'store_true', default = False)

    args = parser.parse_args()

    update(expanduser(args.root_dir), args.stdin, args.stdout)

if __name__ == '__main__':
    main()
