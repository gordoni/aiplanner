# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2019 Gordon Irlam
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

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import isnan

from django.forms.utils import ErrorList
from django.shortcuts import render

from spia import LifeTable, Scenario, YieldCurve

from aacalc.forms import SpiaForm

def default_spia_params():

    return {
        'sex': 'male',
        'age_years': 65,
        'joint_type': 'contingent',
        'joint_payout_percent': 70,
        'table': 'iam2012-basic',
        'ae' : 'aer2005_13-grouped',
        'date': (datetime.utcnow() + timedelta(hours = -24)).date().isoformat(),  # Yesterday's quotes are retrieved at midnight.
        'bond_type': 'nominal',
        'adjust': 2,
        'bond_adjust_pct': Decimal('0.0'),
        'cpi_adjust': 'calendar',
        'frequency': 12,
        'payout_delay_months' : 1,
        'period_certain' : 0,
        'mwr_percent': 100,
        'percentile': 95
    }

def first_payout(date_str, delay, frequency):

    start_y, start_m, start_d = date_str.split('-')
    start_y = int(start_y)
    start_m = int(start_m)
    start_d = int(start_d)
    start_date = date(start_y, start_m, start_d)
    end_date = start_date + timedelta(delay / 12.0 * 365.25)
    y = end_date.year
    m = end_date.month
    d = end_date.day
    if d > 1:
        m += 1
        d = 1
    period = int(12 / frequency)
    m_adjust = int((m - 1 + period - 1) / period) * period - (m - 1)
    delay += m_adjust
    m += m_adjust
    if m > 12:
        y += 1
        m -= 12
    end_date = date(y, m, d)

    payout_date = end_date.strftime('%Y-%m-%d')
    payout_delay = (end_date.year - start_date.year) * 12
    payout_delay += end_date.month - start_date.month
    payout_delay += float(end_date.day - start_date.day) / monthrange(start_y, start_m)[1]  # Only works for end_date.day == 1.

    return payout_date, payout_delay

def format_calcs(calcs, price, payout, mwr):

    calculations = []
    for calc in calcs:
        calculations.append({
            'n': calc['i'],
            'y': '{:.3f}'.format(calc['y']),
            'primary': '{:.6f}'.format(calc['alive']),
            'joint': '{:.6f}'.format(calc['joint']),
            'combined': '{:.6f}'.format(calc['combined']),
            'combined_price': '{:,.2f}'.format(calc['payout_fraction'] * payout),
            'discount_rate': '{:.3f}%'.format((calc['interest_rate'] - 1) * 100),
            'fair_price': '{:,.2f}'.format(calc['fair_price'] * payout),
        })

    fair_price = sum(calc['fair_price'] for calc in calcs) * payout

    try:
        actual_price = fair_price / mwr
        assert((isnan(actual_price) and isnan(fair_price)) or abs(actual_price - price) <= 1e-6 * price)
    except ZeroDivisionError:
        actual_price = float('inf')

    return calculations, '{:,.2f}'.format(fair_price), '{:,.2f}'.format(actual_price)

def spia(request):

    errors_present = False

    results = {}

    if request.method == 'POST':

        spia_form = SpiaForm(request.POST)

        if spia_form.is_valid():

            try:

                data = spia_form.cleaned_data
                interest_rate = data['bond_type']
                date_str = data['date']
                adjust = float(data['bond_adjust_pct']) / 100
                yield_curve = YieldCurve(interest_rate, date_str, adjust = adjust)

                sex = data['sex']
                age = float(data['age_years']);
                if data['age_months']:
                    age += float(data['age_months']) / 12
                ae = data['ae']

                sex2 = data['sex2']

                table = data['table']
                le_set = None
                le_set2 = None
                if table == 'adjust':
                    table = 'ssa-cohort'
                    le_set = float(data['le_set'])
                    if sex2 != None:
                        le_set2 = float(data['le_set2'])

                life_table = LifeTable(table, sex, age, ae = ae, le_set = le_set, date_str = date_str)

                if sex2 == None:
                    life_table2 = None
                else:
                    age2 = float(data['age2_years']);
                    if data['age2_months']:
                        age2 += float(data['age2_months']) / 12
                    life_table2 = LifeTable(table, sex2, age2, ae = ae, le_set = le_set2, date_str = date_str)

                joint_payout_fraction = float(data['joint_payout_percent']) / 100
                joint_contingent = (data['joint_type'] == 'contingent')
                frequency = int(data['frequency'])
                adjust = float(data['adjust']) / 100
                cpi_adjust = data['cpi_adjust']
                payout_delay = float(data['payout_delay_months'])
                if data['payout_delay_years']:
                    payout_delay += float(data['payout_delay_years']) * 12
                payout_date, payout_delay = first_payout(date_str, payout_delay, frequency)
                period_certain = data['period_certain']
                premium = data.get('premium')
                if premium != None:
                    premium = float(premium)
                payout = data.get('payout')
                if payout != None:
                    payout = float(payout)
                mwr_percent = data.get('mwr_percent')
                if mwr_percent == None:
                    mwr = 1
                else:
                    mwr = float(mwr_percent) / 100
                percentile = float(data['percentile'])

                scenario = Scenario(yield_curve, payout_delay, premium, payout, 0, life_table, life_table2 = life_table2, \
                    joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                                    frequency = frequency, adjust = adjust, price_adjust = cpi_adjust, mwr = mwr, calcs = True)
                price = scenario.price() * frequency

                self_insure_scenario = Scenario(yield_curve, payout_delay, premium, payout, 0, life_table, life_table2 = life_table2, \
                    joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                                                frequency = frequency, adjust = adjust, price_adjust = cpi_adjust, percentile = percentile, calcs = True)
                self_insure_price = self_insure_scenario.price() * frequency

                results['fair'] = (mwr == 1)
                results['frequency'] = {
                    12: 'monthly',
                    4: 'quarterly',
                    2: 'semi-annual',
                    1: 'annual',
                }[frequency]
                results['payout_date'] = payout_date
                results['yield_curve_date'] = yield_curve.yield_curve_date
                if premium == None:
                    premium = payout * price
                    results['premium'] = '{:,.0f}'.format(premium)
                elif payout == None:
                    try:
                        payout = premium / price
                    except ZeroDivisionError:
                        payout = float('inf')
                    results['payout'] = '{:,.2f}'.format(payout)
                else:
                    try:
                        mwr = payout * price / premium
                    except ZeroDivisionError:
                        mwr = float('inf')
                results['mwr_percent'] = '{:.1f}'.format(mwr * 100)
                results['self_insure'] = '{:,.0f}'.format(payout * self_insure_price)
                results['self_insure_complex'] = (life_table2 != None and joint_payout_fraction != 1)

                results['spia_calcs'], results['spia_fair'], results['spia_actual'] = format_calcs(scenario.calcs, premium, payout, mwr)
                results['bond_calcs'], results['bond_fair'], _ = format_calcs(self_insure_scenario.calcs, payout * self_insure_price, payout, 1)

            except YieldCurve.NoData:

                spia_form.add_error('date', 'No interest rate data available for the specified date.')

                errors_present = True

            except LifeTable.UnableToAdjust:

                spia_form.add_error('le_set', 'Unable to adjust life table to match additional life expectancy.')

                errors_present = True

        else:

            errors_present = True

    else:

        spia_form = SpiaForm(default_spia_params())

    return render(request, 'spia.html', {
        'errors_present': errors_present,
        'spia_form': spia_form,
        'results': results,
    })
