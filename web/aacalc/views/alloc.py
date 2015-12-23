# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2015 Gordon Irlam
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

from datetime import datetime, timedelta
from decimal import Decimal

from django.forms.util import ErrorList
from django.shortcuts import render

from aacalc.forms import AllocForm
from aacalc.spia import LifeTable, Scenario, YieldCurve

def default_alloc_params():

    return {
        'sex': 'male',
        'age': 65,
        'sex2': None,
        'age2': None,
        'date': (datetime.utcnow() + timedelta(hours = -24)).date().isoformat(),  # Yesterday's quotes are retrieved at midnight.
        'db' : ({
            'description': 'Social Security',
            'who': 'self',
            'age': 65,
            'amount': 15000,
            'inflation_indexed': True,
            'joint_type': 'survivor',
            'joint_payout_pct': 0,
        }, {
            'description': 'Pension',
            'who': 'self',
            'age': 65,
            'amount': 0,
            'inflation_indexed': True,
            'joint_type': 'survivor',
            'joint_payout_pct': 0,
        }, {
            'description': 'Income annuity',
            'who': 'self',
            'age': 65,
            'amount': 0,
            'inflation_indexed': True,
            'joint_type': 'contingent',
            'joint_payout_pct': 70,
        }, {
            'description': 'Income annuity',
            'who': 'self',
            'age': 65,
            'amount': 0,
            'inflation_indexed': False,
            'joint_type': 'contingent',
            'joint_payout_pct': 70,
        }, {
            'description': 'Social Security',
            'who': 'spouse',
            'age': 65,
            'amount': 0,
            'inflation_indexed': True,
            'joint_type': 'survivor',
            'joint_payout_pct': 0,
        }, {
            'description': 'Pension',
            'who': 'spouse',
            'age': 65,
            'amount': 0,
            'inflation_indexed': True,
            'joint_type': 'survivor',
            'joint_payout_pct': 0,
        }, {
            'description': 'Income annuity',
            'who': 'spouse',
            'age': 65,
            'amount': 0,
            'inflation_indexed': True,
            'joint_type': 'contingent',
            'joint_payout_pct': 70,
        }, {
            'description': 'Income annuity',
            'who': 'spouse',
            'age': 65,
            'amount': 0,
            'inflation_indexed': False,
            'joint_type': 'contingent',
            'joint_payout_pct': 70,
        }),
        'p_traditional_iras': 0,
        'tax_rate_pct': 30,
        'p_roth_iras': 0,
        'p': 0,
        'contribution': 10000,
        'contribution_growth_pct': 7,
    }

def alloc(request):

    errors_present = False

    results = {}

    if request.method == 'POST':

        alloc_form = AllocForm(request.POST)

        if alloc_form.is_valid():

            try:

                data = alloc_form.cleaned_data
                date_str = data['date']
                yield_curve_real = YieldCurve('real', date_str)
                yield_curve_nominal = YieldCurve('nominal', date_str)

                if yield_curve_real.yield_curve_date == yield_curve_nominal.yield_curve_date:
                    results['yield_curve_date'] = yield_curve_real.yield_curve_date;
                else:
                    results['yield_curve_date'] = yield_curve_real.yield_curve_date + ' real, ' + yield_curve_nominal.yield_curve_date + ' nominal';

                table = 'ssa_cohort'

                sex = data['sex']
                age = float(data['age']);
                life_table = LifeTable(table, sex, age)

                sex2 = data['sex2']
                if sex2 == None:
                    life_table2 = None
                else:
                    age2 = float(data['age2']);
                    life_table2 = LifeTable(table, sex2, age2)

                npv_db = 0
                results['db'] = []

                for db in data['db']:

                    amount = float(db['amount'])

                    if amount == 0:
                        continue

                    yield_curve = yield_curve_real if db['inflation_indexed'] else yield_curve_nominal

                    if db['who'] == 'self':
                        starting_age = age
                        lt1 = life_table
                        lt2 = life_table2
                    else:
                        starting_age = age2
                        lt1 = life_table2
                        lt2 = life_table

                    joint_payout_fraction = float(db['joint_payout_pct']) / 100
                    joint_contingent = (db['joint_type'] == 'contingent')
                    payout_delay = max(0, float(db['age']) - starting_age) * 12
                    period_certain = 0
                    frequency = 12  # Makes NPV more accurate.
                    cpi_adjust = 'all'

                    scenario = Scenario(yield_curve, payout_delay, None, None, 0, lt1, life_table2 = lt2, \
                        joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                        frequency = frequency, cpi_adjust = cpi_adjust)
                    price = scenario.price() * amount
                    npv_db += price

                    results['db'].append({
                        'description': db['description'],
                        'who': db['who'],
                        'npv': '{:,.0f}'.format(price),
                    })

                npv_traditional = float(data['p_traditional_iras']) * (1 - float(data['tax_rate_pct']) / 100)
                npv_roth = float(data['p_roth_iras'])
                npv_taxable = float(data['p'])
                npv_investments = npv_traditional + npv_roth + npv_taxable
                npv = npv_db + npv_investments

                results['npv_db'] = '{:,.0f}'.format(npv_db)
                results['npv_traditional'] = '{:,.0f}'.format(npv_traditional)
                results['npv_roth'] = '{:,.0f}'.format(npv_roth)
                results['npv_taxable'] = '{:,.0f}'.format(npv_taxable)
                results['npv_investments'] = '{:,.0f}'.format(npv_investments)
                results['npv'] = '{:,.0f}'.format(npv)

            except YieldCurve.NoData:

                errors = alloc_form._errors.setdefault('date', ErrorList())  # Simplified in Django 1.7.
                errors.append('No interest rate data available for the specified date.')

                errors_present = True

        else:

            errors_present = True

    else:

        alloc_form = AllocForm(default_alloc_params())

    return render(request, 'alloc.html', {
        'errors_present': errors_present,
        'alloc_form': alloc_form,
        'results': results,
    })
