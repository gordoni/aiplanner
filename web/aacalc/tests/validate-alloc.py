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
    (1, 27319, 26837, 'default', {}),
    (float('nan'), 15000, 15000, 'p=0', {'p': 0}),
    (0.53, 8767, 8126, 'db=10', {'db': (db('self', 65, 10), )}),
    (1, 26769, 28404, 'gamma=2', {'gamma': 2}),
    (0.94, 26643, 25761, 'gamma=6', {'gamma': 6}),
    (1, 21242, 21444, 'p=100k', {'p': 100000}),
    (0.92, 43181, 41078, 'p=500k', {'p': 500000}),
    (1, 27804, 27487, 'stocks=8.7%+/-20%', {'equity_ret_pct': 8.7, 'equity_vol_pct': 20}),
    (0.85, 27184, 26925, 'bonds=3.2%+/-4%', {'bonds_ret_pct': 3.2, 'bonds_vol_pct': 4}),
    (1, 32132, 26597, 'age=90, le_add=3, p=100k', {'age': 90, 'le_add': 3, 'p': 100000}),
    (0.95, 36476, 37755, 'age=50, p=500k', {'age': 50, 'p': 500000, 'db': (db('self', 50, 15000), )}),
    (1, float('nan'), 40093, 'age=50, retire=65, accumulate=3000*1.07^y', {'age': 50, 'retirement_age': 65, 'contribution': 3000, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.97, float('nan'), 68878, 'age=25, retire=65, accumulate=500*1.07^y', {'age': 25, 'retirement_age': 65, 'contribution': 500, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.83, 43596, 40391, 'desired=40k, p=500k', {'desired_income': 40000, 'p': 500000}),
    (1, 26278, 26466, 'female', {'sex': 'female'}),
    (1, 55464, 57661, 'sex2=female, p=500k', {'sex2': 'female', 'age2': 65, 'p': 500000, 'db': (db('self', 65, 15000), db('spouse', 65, 15000))}),
    (0.77, 67040, 62926, 'p=1000k', {'p': 1000000}),
    (0.53, 43762, 40553, 'p=1000k, db=10', {'p': 1000000, 'db': (db('self', 65, 10), )}),
    (1, 74092, 74815, 'p=1000k, gamma=2', {'p': 1000000, 'gamma': 2}),
    (0.54, 60699, 56835, 'p=1000k, gamma=6', {'p': 1000000, 'gamma': 6}),
    (0.69, 68232, 64490, 'p=1000k, stocks=8.7%+/-20%', {'p': 1000000, 'equity_ret_pct': 8.7, 'equity_vol_pct': 20}),
    (0.50, 69003, 67044, 'p=1000k, bonds=3.2%+/-4%', {'p': 1000000, 'bonds_ret_pct': 3.2, 'bonds_vol_pct': 4}),
    (0.81, 77213, 60813, 'p=500k, le_add=3, age=90', {'age': 90, 'le_add': 3, 'p': 500000, }),
    (0.64, 107958, 108740, 'p=2500k, age=50', {'age': 50, 'p': 2500000, }),
    (0.72, float('nan'), 92445, 'p=1000k, age=50, retire=65, accumulate=3000*1.07^y', {'p': 1000000, 'age': 50, 'retirement_age': 65, 'contribution': 3000, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (0.76, float('nan'), 108217, 'p=500k, age=25, retire=65, accumulate=500*1.07^y', {'p': 500000, 'age': 25, 'retirement_age': 65, 'contribution': 500, 'contribution_growth_pct': 7, 'contribution_vol_pct': 1}),
    (1, 143324, 175404, 'p=2500k, desired=40k', {'desired_income': 40000, 'p': 2500000}),
    (0.77, 63619, 61158, 'p=1000k, sex=female', {'p': 1000000, 'sex': 'female'}),
    (0.73, 141995, 141880, 'p=2500k, sex2=female', {'p': 2500000, 'sex2': 'female', 'age2': 65, 'db': (db('self', 65, 15000), db('spouse', 65, 15000))}),
    (0.64, 135068, 125689, 'p=2500k', {'p': 2500000}),
)

for test in tests:
    stocks, consume, metric_combined, desc, params = test
    alloc = Alloc()
    default = alloc.default_alloc_params()
    params = dict(dict(default, date='2015-12-31', expense_pct=0, purchase_income_annuity=False, desired_income=1000000, \
                       contribution_vol_pct=1, \
                       equity_ret_pct=7.2, equity_vol_pct=17.0, \
                       bonds_ret_pct=0.8, bonds_vol_pct=4.0, equity_bonds_corr_pct=7.0, \
                       age=65, retirement_age=50, db=(db('self', 65, 15000), ), p=200000, gamma=4), **params)
    results = alloc.compute_results(params, 'aa')
    over_aa = results['calc'][0]['aa_equity'] - stocks
    over_consume = float(results['calc'][0]['consume'].replace(',', '')) / consume - 1
    print "{stocks:>4.0%} {calc[0][aa_equity]:>4.0%} {over_aa:>4.0%} {calc[1][aa_equity]:>4.0%}-{calc[2][aa_equity]:<4.0%} {consume:>7,.0f} {metric_combined:>7,.0f} {calc[0][consume]:>7} {over_consume:>4.0%} {calc[1][consume]:>7}-{calc[2][consume]:<7} {desc}".format(stocks=stocks, consume=consume, metric_combined=metric_combined, desc=desc, over_aa=over_aa, over_consume=over_consume, **results)
