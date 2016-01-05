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
    (0.94, 26635, 25679, 'gamma=6', {'gamma': 6}),
    (1, 21244, 21444, 'p=100k', {'p': 100000}),
    (0.91, 43162, 41103, 'p=500k', {'p': 500000}),
    (1, 27801, 27490, 'stocks=8.7%+/-20%', {'equity_ret_pct': 8.7, 'equity_vol_pct': 20}),
    (0.85, 27176, 26925, 'bonds=3.2%+/-4%', {'bonds_ret_pct': 3.2, 'bonds_vol_pct': 4}),
    (1, 32130, 26597, 'age=90, le_add=3, p=100k', {'age': 90, 'le_add': 4.5, 'p': 100000}),
    (0.91, 36427, 37849, 'age=50, p=500k', {'age': 50, 'p': 500000, 'db': (db('self', 50, 15000), )}),
    (1, float('nan'), 40215, 'age=50, retire=65, accumulate=3000*1.07^y', {'age': 50, 'retirement_age': 65, 'contribution': 3000, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.95, float('nan'), 68013, 'age=25, retire=65, accumulate=500*1.07^y', {'age': 25, 'retirement_age': 65, 'contribution': 500, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.82, 43577, 40435, 'desired=40k, p=500k', {'desired_income': 40000, 'p': 500000}),
    (1, 26276, 26467, 'female', {'sex': 'female'}),
    (1, 55449, 57664, 'sex2=female, p=500k', {'sex2': 'female', 'age2': 65, 'p': 500000, 'db': (db('self', 65, 15000), db('spouse', 65, 15000))}),
    (0.75, 67078, 63082, 'p=1000k', {'p': 1000000}),
    (0.52, 44227, 41113, 'p=1000k, db=10', {'p': 1000000, 'db': (db('self', 65, 10), )}),
    (1, 74091, 74815, 'p=1000k, gamma=2', {'p': 1000000, 'gamma': 2}),
    (0.53, 60945, 57206, 'p=1000k, gamma=6', {'p': 1000000, 'gamma': 6}),
    (0.68, 68304, 64715, 'p=1000k, stocks=8.7%+/-20%', {'p': 1000000, 'equity_ret_pct': 8.7, 'equity_vol_pct': 20}),
    (0.50, 68992, 67043, 'p=1000k, bonds=3.2%+/-4%', {'p': 1000000, 'bonds_ret_pct': 3.2, 'bonds_vol_pct': 4}),
    (0.81, 77220, 60815, 'p=500k, age=90, le_add=3', {'age': 90, 'le_add': 3, 'p': 500000, }),
    (0.61, 109182, 111104, 'p=2500k, age=50', {'age': 50, 'p': 2500000, }),
    (0.70, float('nan'), 94490, 'p=1000k, age=50, retire=65, accumulate=3000*1.07^y', {'p': 1000000, 'age': 50, 'retirement_age': 65, 'contribution': 3000, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.74, float('nan'), 112048, 'p=500k, age=25, retire=65, accumulate=500*1.07^y', {'p': 500000, 'age': 25, 'retirement_age': 65, 'contribution': 500, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (1, 143435, 175466, 'p=2500k, desired=40k', {'desired_income': 40000, 'p': 2500000}),
    (0.76, 63660, 61290, 'p=1000k, sex=female', {'p': 1000000, 'sex': 'female'}),
    (0.72, 142201, 142307, 'p=2500k, sex2=female', {'p': 2500000, 'sex2': 'female', 'age2': 65, 'db': (db('self', 65, 15000), db('spouse', 65, 15000))}),
    (0.63, 135476, 126446, 'p=2500k', {'p': 2500000}),
)

overs = []
for test in tests:
    stocks, consume, metric_combined, desc, params = test
    alloc = Alloc()
    default = alloc.default_alloc_params()
    params = dict(dict(default, date='2015-12-31', expense_pct=0, purchase_income_annuity=False, desired_income=1000000, \
        age=65, retirement_age=50, p=200000), **params)
    results = alloc.compute_results(params)
    over_aa = results['calc'][0]['aa_equity'] - stocks
    over_consume = float(results['calc'][0]['consume'].replace(',', '')) / consume - 1
    if not isnan(over_consume):
        overs.append(over_consume)
    print "{stocks:>4.0%} {calc[0][aa_equity]:>4.0%} {over_aa:>4.0%} {calc[1][aa_equity]:>4.0%}-{calc[2][aa_equity]:<4.0%} {consume:>7,.0f} {metric_combined:>7,.0f} {calc[0][consume]:>7} {over_consume:>4.0%} {calc[1][consume]:>7}-{calc[2][consume]:<7} {desc}".format(stocks=stocks, consume=consume, metric_combined=metric_combined, desc=desc, over_aa=over_aa, over_consume=over_consume, **results)
print 'mean over-consume {:.0%}'.format(sum(overs) / len(overs))
