#!/usr/bin/python

import os
import sys

from math import isnan

path = '/home/ubuntu/aacalc/web'
if path not in sys.path:
    sys.path.append(path)

path = '/home/ubuntu/aacalc/web/project'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from aacalc.views.alloc import Alloc

def db(who, age, amount):
    return {
        'description': 'Social Security',
        'who': who,
        'age': age,
        'amount': amount,
        'inflation_indexed': True,
        'period_certain' : 0,
        'joint_type': 'survivor',
        'joint_payout_pct': 0,
    }

tests = (
    (1, 27317, 26837, 'default', {}),
    (1, 15000, 15000, 'p=0', {'p': 0}),
    (0.52, 8861, 8237, 'db=10', {'db': (db('self', 65, 10), )}),
    (1, 26769, 28404, 'gamma=2', {'gamma': 2}),
    (0.94, 26639, 25679, 'gamma=6', {'gamma': 6}),
    (1, 21244, 21444, 'p=100k', {'p': 100000}),
    (0.91, 43164, 41105, 'p=500k', {'p': 500000}),
    (1, 27801, 27490, 'stocks=8.7%+/-20%', {'equity_ret_pct': 8.7, 'equity_vol_pct': 20}),
    (0.88, 27212, 26901, 'bonds=3.2%+/-10%', {'bonds_ret_pct': 3, 'bonds_vol_pct': 10}),
    (1, 32130, 26597, 'age=90, le_add=3, p=100k', {'age': 90, 'le_add': 4.5, 'p': 100000}),
    (0.96, 36500, 37763, 'age=50, p=500k', {'age': 50, 'p': 500000, 'db': (db('self', 50, 15000), )}),
    (1, float('nan'), 40133, 'age=50, retire=65, accumulate=3000*1.07^y', {'age': 50, 'retirement_age': 65, 'contribution': 3000, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.82, 43583, 40436, 'desired=40k, p=500k', {'desired_income': 40000, 'p': 500000}),
    (1, 26276, 26468, 'female', {'sex': 'female'}),
    (1, 55449, 57665, 'sex2=female, p=500k', {'sex2': 'female', 'age2': 65, 'p': 500000, 'db': (db('self', 65, 15000), db('spouse', 65, 15000))}),
    (0.75, 67058, 63087, 'p=1000k', {'p': 1000000}),
    (0.52, 44228, 41116, 'p=1000k, db=10', {'p': 1000000, 'db': (db('self', 65, 10), )}),
    (1, 74084, 74815, 'p=1000k, gamma=2', {'p': 1000000, 'gamma': 2}),
    (0.53, 60936, 57208, 'p=1000k, gamma=6', {'p': 1000000, 'gamma': 6}),
    (0.68, 68327, 64719, 'p=1000k, stocks=8.7%+/-20%', {'p': 1000000, 'equity_ret_pct': 8.7, 'equity_vol_pct': 20}),
    (0.61, 68435, 65733, 'p=1000k, bonds=3.2%+/-10%', {'p': 1000000, 'bonds_ret_pct': 3.2, 'bonds_vol_pct': 10}),
    (0.78, 77211, 60684, 'p=500k, le_add=3, age=90', {'age': 90, 'le_add': 3, 'p': 500000, }),
    (0.65, 108004, 108980, 'p=2500k, age=50', {'age': 50, 'p': 2500000, }),
    (0.75, float('nan'), 92364, 'p=1000k, age=50, retire=65, accumulate=3000*1.07^y', {'p': 1000000, 'age': 50, 'retirement_age': 65, 'contribution': 3000, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (1, 143453, 175468, 'p=2500k, desired=40k', {'desired_income': 40000, 'p': 2500000}),
    (0.76, 63643, 61295, 'p=1000k, sex=female', {'p': 1000000, 'sex': 'female'}),
    (0.72, 142120, 142320, 'p=2500k, sex2=female', {'p': 2500000, 'sex2': 'female', 'age2': 65, 'db': (db('self', 65, 15000), db('spouse', 65, 15000))}),
    (0.63, 135458, 126456, 'p=2500k', {'p': 2500000}),
)

overs = []
for test in tests:
    stocks, consume, metric_combined, desc, params = test
    alloc = Alloc()
    default = alloc.default_alloc_params()
    params = dict(dict(default, date='2015-12-31', expense_pct=0, purchase_income_annuity=False, desired_income=1000000, \
        age=65, retirement_age=50, p=200000), **params)
    results = alloc.compute_results(params)
    over = float(results['calc'][0]['consume'].replace(',', '')) / consume - 1
    if not isnan(over):
        overs.append(over)
    print "{stocks:>4.0%} {calc[0][aa_equity]:>4.0%} {calc[1][aa_equity]:>4.0%}-{calc[2][aa_equity]:<4.0%} {consume:>7,.0f} {metric_combined:>7,.0f} {calc[0][consume]:>7} {over:>4.0%} {calc[1][consume]:>7}-{calc[2][consume]:<7} {desc}".format(stocks=stocks, consume=consume, metric_combined=metric_combined, desc=desc, over=over, **results)
print 'mean over-consume {:.0%}'.format(sum(overs) / len(overs))
