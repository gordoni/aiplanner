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

    page = stdin.read() if read_stdin else urlopen('https://www.wsj.com/market-data/stocks/peyields').read().decode('utf-8')

    date, trailing, forward = search('Other Indexes.*?<tr[^>]*><th[^>]*></th><th[^>]*>(\d+/\d+/\d{2})[^<]*</th><th[^>]*>Year ago[^<]*</th><th[^>]*>Estimate.*?<tr[^>]*><td[^>]*>S&amp;P 500 Index</td><td[^>]*>(\d+.\d+)[^<]*</td><td[^>]*>\d+.\d+</td><td[^>]*>(\d+.\d+)', page).groups()
    date = datetime.strptime(date, '%m/%d/%y')
    trailing = float(trailing)
    forward = float(forward)
    date_str = date.date().isoformat()

    if write_stdout:
        print(date_str, trailing ,forward)

    # Estimate of current observed stock market price to fair price.
    # For 1950-2017 the harmonic mean S&P 500 P/E ratio (not CAPE) was 14.85 (based on Shiller's data).

    # Take harmonic mean of trailing and forward S&P 500 P/E. Serves as a reasonable rough estimate most of the time.
    level = (1 / ((1 / trailing + 1 / forward) / 2)) / 14.85

    now = datetime.utcnow()
    assert now - timedelta(days = 14) < date <= now
    assert 0.4 < level < 4.0

    if write_stdout:
        print(level)
    else:
        try:
            f = open(root_dir + '/market-data.json')
            data = loads(f.read())
        except IOError:
            data = {}
        data['stocks_price'] = level
        data['stocks_price_date'] = date_str
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
