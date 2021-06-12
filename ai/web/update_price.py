#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019-2021 Gordon Irlam
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
from math import isnan
from os import remove
from os.path import expanduser
from re import sub
from sys import stdin
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

import pandas as pd

def update(root_dir, read_stdin, write_stdout):

    data = stdin.buffer.read() if read_stdin else urlopen('https://us.spindices.com/documents/additional-material/sp-500-eps-est.xlsx').read()
    tmp = NamedTemporaryFile(suffix = '.xlsx', delete = False)
    try:
        tmp.write(data)
        tmp.close()
        df = pd.read_excel(tmp.name, keep_default_na = False)
    finally:
        remove(tmp.name)

    table = df.values
    q_dates = []
    q_earn = []
    seen_estimates = False
    seen_actuals = False
    for i, row in enumerate(table):
        if row[0] == 'Date' or row[0] == 'Data as of the close of:':
            try:
                date = datetime.strptime(row[3], '%m/%d/%Y')
            except TypeError:
                date = row[3]
            date_str = date.date().isoformat()
        elif row[0] == 'S&P 500 close of:':
            price = row[3]
        elif row[0] == 'ESTIMATES':
            seen_estimates = True
            assert table[i - 5][3] == 'AS REPORTED'
            assert table[i - 3][3] == 'PER SHR'
        elif row[0] == 'ACTUALS':
            seen_actuals = True
        elif row[0] == '':
            if seen_actuals:
                break
        elif seen_estimates:
            try:
                q_date = sub(r'^(\d+)[^\d]+(\d+)[^\d]+(\d+).*$', r'\1/\2/\3', row[0])
            except TypeError:
                q_date = row[0]
            else:
                q_date = datetime.strptime(q_date, '%m/%d/%Y')
            q_date_str = q_date.date().isoformat()
            q_dates.insert(0, q_date_str)
            q_earn.insert(0, row[3])

    for i, q_date in enumerate(q_dates):
        if q_date > date_str:
            break

    trailing = price / sum(q_earn[i - 4:i])
    forward = price / sum(q_earn[i:i + 4])

    if write_stdout:
        print(date_str, trailing, forward)

    # Estimate of current observed stock market price to fair price.
    # For 1950-2019 the harmonic mean S&P 500 P/E ratio (not CAPE) was 14.99 (based on Shiller's data).

    # Take harmonic mean of trailing and forward S&P 500 P/E. Serves as a reasonable rough estimate most of the time.
    level = (1 / ((1 / trailing + 1 / forward) / 2)) / 14.99

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
        if data.get('stocks_price_date', '2000-01-01') <= date_str:
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
