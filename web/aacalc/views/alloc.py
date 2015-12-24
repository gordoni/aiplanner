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
        'age': 50,
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

        'retirement_age': 65,
        'joint_income_pct': 70,
        'purchase_income_annuity': True,

        'equity_ret_pct': Decimal('6.8'),
        'equity_ret_geom_pct': Decimal('5.0'),
        'equity_vol_pct': Decimal('18'),
        'equity_se_pct': Decimal('2.1'),
        'equity_range_factor': 1,
        'expense_pct': Decimal('0.5'),

        'gamma': Decimal('4.0'),
    }

def calc(description, factor, data, average_age, bonds_ret, npv_db, npv):
    equity_ret = float(data['equity_ret_pct']) / 100
    equity_ret += factor * float(data['equity_se_pct']) / 100
    gamma = float(data['gamma'])
    equity_vol = float(data['equity_vol_pct']) / 100
    try:
        pi = (equity_ret - bonds_ret) / (equity_vol ** 2 * gamma)
    except ZeroDivisionError:
        pi = float('inf')
    if data['purchase_income_annuity']:
        annuitize_equity = min(max(0, (average_age - 50.0) / (80 - 50)), 1)
        annuitize_fixed = min(max(0, (average_age - 35.0) / (60 - 35)), 1)
    else:
        annuitize_equity = 0
        annuitize_fixed = 0
    alloc_equity = min(max(0, pi * (1 - annuitize_equity)), 1)
    alloc_bonds = min(max(0, (1 - pi) * (1 - annuitize_fixed)), 1)
    alloc_db = 1 - alloc_equity - alloc_bonds
    try:
        min_alloc_db = npv_db / npv
    except ZeroDivisionError:
        min_alloc_db = 0
    shortfall = min(0, alloc_db - min_alloc_db)
    alloc_db -= shortfall
    alloc_bonds += shortfall
    shortfall = min(0, alloc_bonds)
    alloc_bonds -= shortfall
    alloc_equity += shortfall
    purchase_income_annuity = (alloc_db - min_alloc_db) * npv
    try:
        aa_equity = alloc_equity / (alloc_equity + alloc_bonds)
    except ZeroDivisionError:
        aa_equity = 1
    aa_bonds = 1 - aa_equity
    result = {
        'description': description,
        'pi_pct': '{:.0f}'.format(pi * 100),
        'annuitize_equity_pct': '{:.0f}'.format(annuitize_equity * 100),
        'annuitize_fixed_pct': '{:.0f}'.format(annuitize_fixed * 100),
        'alloc_equity_pct': '{:.0f}'.format(alloc_equity * 100),
        'alloc_bonds_pct': '{:.0f}'.format(alloc_bonds * 100),
        'alloc_db_pct': '{:.0f}'.format(alloc_db * 100),
        'purchase_income_annuity': '{:,.0f}'.format(purchase_income_annuity),
        'aa_equity_pct': '{:.0f}'.format(aa_equity * 100),
        'aa_bonds_pct': '{:.0f}'.format(aa_bonds * 100),
    }
    return result

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
                yield_curve_zero = YieldCurve('fixed', date_str)

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

                period_certain = 0
                frequency = 12  # Makes NPV more accurate.
                cpi_adjust = 'calendar'

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

                    payout_delay = max(0, float(db['age']) - starting_age) * 12
                    joint_payout_fraction = float(db['joint_payout_pct']) / 100
                    joint_contingent = (db['joint_type'] == 'contingent')

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

                payout_delay = max(0, float(data['retirement_age']) - age) * 12
                joint_payout_fraction = float(data['joint_income_pct']) / 100
                joint_contingent = True

                scenario = Scenario(yield_curve_zero, payout_delay, None, None, 0, life_table, life_table2 = life_table2, \
                    joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                    frequency = frequency, cpi_adjust = cpi_adjust)
                bonds_initial = scenario.price()
                scenario = Scenario(yield_curve_real, payout_delay, None, None, 0, life_table, life_table2 = life_table2, \
                    joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                    frequency = frequency, cpi_adjust = cpi_adjust)
                scenario.price()
                bonds_ret = bonds_initial / scenario.discount_single_year - 1
                results['bonds_ret_pct'] = '{:.1f}'.format(bonds_ret * 100)
                bonds_duration = scenario.duration
                results['bonds_duration'] = '{:.1f}'.format(bonds_duration)

                if sex2 == None:
                    average_age = age
                else:
                    average_age = (age + age2) / 2.0
                results['calc'] = (
                    calc('Baseline estimate', 0, data, average_age, bonds_ret, npv_db, npv),
                    calc('Low estimate', - float(data['equity_range_factor']), data, average_age, bonds_ret, npv_db, npv),
                    calc('High estimate', float(data['equity_range_factor']), data, average_age, bonds_ret, npv_db, npv),
                )
                equity_ret = float(data['equity_ret_pct']) / 100
                gamma = float(data['gamma'])
                equity_vol = float(data['equity_vol_pct']) / 100
                try:
                    pi = (equity_ret - bonds_ret) / (equity_vol ** 2 * gamma)
                except ZeroDivisionError:
                    pi = float('inf')
                results['pi_pct'] = '{:.0f}'.format(pi * 100)

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
