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
from math import exp
from os.path import expanduser
from sys import stdin

from spia import YieldCurve

def update(root_dir, write_stdout):

    now = datetime.utcnow()
    now_date = now.date().isoformat()

    real_yield_curve = YieldCurve('real', now_date)
    real_short_rate = exp(real_yield_curve.spot(0)) - 1
    real_date = datetime.strptime(real_yield_curve.yield_curve_date, '%Y-%m-%d')

    nominal_yield_curve = YieldCurve('nominal', now_date)
    nominal_short_rate = exp(nominal_yield_curve.spot(0)) - 1
    nominal_date = datetime.strptime(nominal_yield_curve.yield_curve_date, '%Y-%m-%d')

    if write_stdout:
        print(real_short_rate, real_yield_curve.yield_curve_date)
        print(nominal_short_rate, nominal_yield_curve.yield_curve_date)

    now = datetime.utcnow()
    assert now - timedelta(days = 7) < real_date <= now
    assert now - timedelta(days = 7) < nominal_date <= now

    if not write_stdout:
        try:
            f = open(root_dir + '/market-data.json')
            data = loads(f.read())
        except IOError:
            data = {}
        data['real_short_rate'] = real_short_rate
        data['real_short_rate_date'] = real_yield_curve.yield_curve_date
        data['nominal_short_rate'] = nominal_short_rate
        data['nominal_short_rate_date'] = nominal_yield_curve.yield_curve_date
        with open(root_dir + '/market-data.json', 'w') as f:
            print(dumps(data, indent = 4, sort_keys = True), file = f)

def main():

    parser = ArgumentParser()

    parser.add_argument('--root-dir', default = '~/aiplanner-data/webroot/apiserver')
    parser.add_argument('--stdout', action = 'store_true', default = False)

    args = parser.parse_args()

    update(expanduser(args.root_dir), args.stdout)

if __name__ == '__main__':
    main()
