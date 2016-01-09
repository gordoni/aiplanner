#!/usr/bin/python

# AACalc - Asset Allocation Calculator
# Copyright (C) 2016 Gordon Irlam
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os import getenv
from sys import path

path.append('../web/aacalc')

from spia import LifeTable, Scenario, YieldCurve

prefix = getenv('OPAL_FILE_PREFIX', 'opal')

with open(prefix + '-lmbonds-params.py') as f:
    params = eval(f.read())

life_table_params = params['life_table']
life_table2_params = params['life_table2']
yield_curve_params = params['yield_curve']
scenario_params = params['scenario']

with open(prefix + '-lmbonds.csv', 'w') as f:

    for year in range(0, params['years']):

        life_table = LifeTable(**life_table_params)
        life_table2 = LifeTable(**life_table2_params) if life_table2_params != None else None

        yield_curve_real = YieldCurve(**yield_curve_params)
        yield_curve_zero = YieldCurve(**dict(yield_curve_params, interest_rate = 'fixed'))

        date_str = str(params['now_year'] + year) + '-01-01'
        scenario = Scenario(yield_curve_zero, life_table1 = life_table, life_table2 = life_table2, date_str = date_str, **scenario_params)
        bonds_initial = scenario.price()
        scenario = Scenario(yield_curve_real, life_table1 = life_table, life_table2 = life_table2, date_str = date_str, **scenario_params)
        scenario.price()
        lm_bonds_ret = bonds_initial / scenario.discount_single_year - 1
        import sys
        print >> f, "%d,%f" % (year,lm_bonds_ret)

        life_table_params['age'] += 1
        if life_table2_params:
            life_table2_params['age'] += 1

        scenario_params['payout_delay'] = max(0, scenario_params['payout_delay'] - 12)
