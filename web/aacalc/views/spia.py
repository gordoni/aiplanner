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

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.forms.util import ErrorList
from django.shortcuts import render

from aacalc.forms import SpiaForm
from aacalc.spia import LifeTable, Scenario, YieldCurve

class UnableToAdjust(Exception):
    pass

def default_spia_params():

    return {
        'sex': 'male',
        'age_years': 65,
        'joint_type': 'contingent',
        'joint_payout_percent': 70,
        'table': 'iam',
        'ae' : 'full',
        'date': (datetime.utcnow() + timedelta(hours = -24)).date().isoformat(),  # Yesterday's quotes are retrieved at midnight.
        'bond_type': 'real',
        'bond_adjust_pct': Decimal('0.0'),
        'cpi_adjust': 'calendar',
        'frequency': 12,
        'payout_delay_months' : 1,
        'period_certain' : 0,
        'mwr_percent': 100,
        'percentile': 95
    }

def compute_q_adjust(date_str, table, sex, age, le):
    yield_curve = YieldCurve('le', date_str)
    q_lo = 0
    q_hi = 10
    for _ in range(50):
        q_adjust = (q_lo + q_hi) / 2.0
        life_table = LifeTable(table, sex, age, q_adjust = q_adjust)
        scenario = Scenario(yield_curve, 0, None, None, 0, life_table)
        compute_le = scenario.price()
        if abs(le / compute_le - 1) < 1e-6:
            return q_adjust
        if compute_le > le:
            q_lo = q_adjust
        else:
            q_hi = q_adjust
    raise UnableToAdjust

def first_payout(date_str, delay, frequency):

    y, m, d = date_str.split('-')
    start_date = date(int(y), int(m), int(d))
    end_date = start_date + timedelta(delay * 365.25)
    y = end_date.year
    m = end_date.month
    d = end_date.day
    if d > 1:
        m += 1
        d = 1
    period = 12 / frequency
    m = (m - 1 + period - 1) / period * period + 1
    if m > 12:
        y += 1
        m -= 12
    end_date = date(y, m, d)

    payout_date = end_date.strftime('%Y-%m-%d')
    payout_delay = (end_date - start_date).days / 365.25

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
        assert(abs(actual_price - price) <= 1e-6 * price)
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

                table = data['table']
                if table == 'adjust':
                    table = 'ssa_cohort'
                    q_adjust = compute_q_adjust(date_str, table, sex, age, float(data['le']))
                else:
                    q_adjust = 1

                life_table = LifeTable(table, sex, age, ae = ae, q_adjust = q_adjust)

                sex2 = data['sex2']
                if sex2 == None:
                    life_table2 = None
                else:
                    age2 = float(data['age2_years']);
                    if data['age2_months']:
                        age2 += float(data['age2_months']) / 12
                    life_table2 = LifeTable(table, sex2, age2, ae = ae, q_adjust = q_adjust)

                joint_payout_fraction = float(data['joint_payout_percent']) / 100
                joint_contingent = (data['joint_type'] == 'contingent')
                frequency = int(data['frequency'])
                cpi_adjust = data['cpi_adjust']
                payout_delay = float(data['payout_delay_months']) / 12
                if data['payout_delay_years']:
                    payout_delay += float(data['payout_delay_years'])
                payout_date, payout_delay = first_payout(date_str, payout_delay, frequency)
                payout_delay *= 12
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
                    frequency = frequency, cpi_adjust = cpi_adjust, mwr = mwr)
                price = scenario.price() * frequency

                self_insure_scenario = Scenario(yield_curve, payout_delay, premium, payout, 0, life_table, life_table2 = life_table2, \
                    joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                    frequency = frequency, cpi_adjust = cpi_adjust, percentile = percentile)
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
                    payout = premium / price
                    results['payout'] = '{:,.2f}'.format(payout)
                else:
                    try:
                        mwr = payout * price / premium
                        results['mwr_percent'] = '{:.1f}'.format(mwr * 100)
                    except ZeroDivisionError:
                        mwr = float('inf')
                        results['mwr_percent'] = 'inf'
                results['self_insure'] = '{:,.0f}'.format(payout * self_insure_price)
                results['self_insure_complex'] = (life_table2 != None and joint_payout_fraction != 1)

                results['spia_calcs'], results['spia_fair'], results['spia_actual'] = format_calcs(scenario.calcs, premium, payout, mwr)
                results['bond_calcs'], results['bond_fair'], _ = format_calcs(self_insure_scenario.calcs, payout * self_insure_price, payout, 1)

            except YieldCurve.NoData:

                errors = spia_form._errors.setdefault('date', ErrorList())  # Simplified in Django 1.7.
                errors.append('No interest rate data available for the specified date.')

                errors_present = True

            except UnableToAdjust:

                errors = spia_form._errors.setdefault('le', ErrorList())
                errors.append('Unable to adjust life table to match additional life expectancy.')

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
