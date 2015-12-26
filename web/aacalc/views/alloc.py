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
from math import ceil, isnan, sqrt

from django.forms.forms import NON_FIELD_ERRORS
from django.forms.util import ErrorList
from django.shortcuts import render
from numpy import array
from numpy.linalg import inv, LinAlgError
from scipy.stats import lognorm

from aacalc.forms import AllocForm
from aacalc.spia import LifeTable, Scenario, YieldCurve

class Alloc:

    class IdenticalCovarError(Exception):
        pass

    def default_alloc_params(self):

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
            'contribution_vol_pct': 10,
            'equity_contribution_corr_pct': 0,

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

    def solve_merton(self, gamma, sigma_matrix, alpha, r):
        try:
            w = inv(sigma_matrix).dot(array(alpha) - r) / gamma
        except LinAlgError:
            raise self.IdenticalCovarError
        return tuple(float(wi) for wi in w) # De-numpyfy.

    def vol_factor(self, vol):
        # Volatility increases the expected growth rate.
        growth_samples = 1000
        percentiles = tuple((i + 0.5) / growth_samples for i in range(growth_samples))
        g = sum(lognorm.ppf(percentiles, vol)) / len(percentiles)
        g = float(g) # De-numpyfy.
        if isnan(g):
            # vol == 0.
            g = 1
        return g

    def stochastic_schedule(self, growth_factor, vol, years):
        g = growth_factor * self.vol_factor(vol)
        return tuple(g ** y for y in range(int(ceil(years))))

    def schedule(self, contribution_schedule):

        def sched(y):
             assert(y % 1 == 0)
             try:
                 return contribution_schedule[int(y)]
             except IndexError:
                 return 0

        return sched

    def npv_contrib(self, growth_factor):
        contribution_schedule = self.stochastic_schedule(growth_factor, self.contribution_vol, self.pre_retirement_years)
        payout_delay = 0
        scenario = Scenario(self.yield_curve_real, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
            joint_payout_fraction = 1, joint_contingent = True, period_certain = 0, \
            frequency = 1, cpi_adjust = 'all', schedule = self.schedule(contribution_schedule))
        return self.contribution * scenario.price()

    def calc(self, description, factor, data, average_age, npv_db, npv_contributions, npv):

        equity_ret = float(data['equity_ret_pct']) / 100
        equity_ret += factor * float(data['equity_se_pct']) / 100
        gamma = float(data['gamma'])
        equity_vol = float(data['equity_vol_pct']) / 100
        equity_contribution_corr = float(data['equity_contribution_corr_pct']) / 100
        cov2 = equity_vol * self.contribution_vol * equity_contribution_corr ** 2
        contrib_index = 1

        lo = -0.5
        hi = 0.5
        while (hi - lo) > 0.000001:
            future_growth_try = (lo + hi) / 2.0
            sigma_matrix = ((equity_vol ** 2, cov2), (cov2, self.contribution_vol ** 2))
            alpha = (equity_ret, future_growth_try)
            w = list(self.solve_merton(gamma, sigma_matrix, alpha, self.bonds_ret))
            w.append(1 - sum(w))
            discounted_contrib = self.npv_contrib((1 + self.contribution_growth) / (1 + future_growth_try))
            npv_discounted = npv - npv_contributions + discounted_contrib
            try:
                wc_discounted = discounted_contrib / npv_discounted
            except ZeroDivisionError:
                wc_discounted = 0
            if wc_discounted > w[contrib_index]:
                lo = future_growth_try
            else:
                hi = future_growth_try
        try:
            w_prime = list(wi * npv_discounted / npv for wi in w)
        except ZeroDivisionError:
            w_prime = list(0 for _ in w)
        w_prime[contrib_index] = 0
        w_prime[contrib_index] = 1 - sum(w_prime)

        if data['purchase_income_annuity']:
            annuitize_equity = min(max(0, (average_age - 50.0) / (80 - 50)), 1)
            annuitize_fixed = min(max(0, (average_age - 35.0) / (60 - 35)), 1)
        else:
            annuitize_equity = 0
            annuitize_fixed = 0
        alloc_equity = min(max(0, w_prime[0] * (1 - annuitize_equity)), 1)
        alloc_contrib = npv_contributions / npv
        alloc_bonds = min(max(0, w_prime[2] * (1 - annuitize_fixed)), 1)
        alloc_db = 1 - alloc_equity - alloc_bonds - alloc_contrib
        try:
            alloc_existing_db = npv_db / npv
        except ZeroDivisionError:
            alloc_existing_db = 0
        shortfall = alloc_db - alloc_existing_db
        if data['purchase_income_annuity']:
            shortfall = min(0, shortfall)
        alloc_db -= shortfall
        alloc_bonds += shortfall
        if alloc_bonds < 0:
            surplus = alloc_bonds
        else:
            surplus = max(alloc_bonds - 1, 0)
        alloc_bonds -= surplus
        alloc_equity += surplus
        alloc_new_db = alloc_db - alloc_existing_db
        purchase_income_annuity = alloc_new_db * npv
        try:
            aa_equity = alloc_equity / (alloc_equity + alloc_bonds)
        except ZeroDivisionError:
            aa_equity = 1
        aa_bonds = 1 - aa_equity

        result = {
            'description': description,
            'future_growth_try_pct': '{:.1f}'.format(future_growth_try * 100),
            'w' : ({
                'name': 'Stocks',
                'alloc': '{:.0f}'.format(w[0] * 100),
            }, {
                'name' : 'Discounted future contributions',
                'alloc': '{:.0f}'.format(w[1] * 100),
            }, {
                'name': 'Liability matching bonds and defined benefits',
                'alloc': '{:.0f}'.format(w[2] * 100),
            }),
            'discounted_contrib': '{:,.0f}'.format(discounted_contrib),
            'wc_discounted':  '{:.0f}'.format(wc_discounted * 100),
            'w_prime' : ({
                'name': 'Stocks',
                'alloc': '{:.0f}'.format(w_prime[0] * 100),
            }, {
                'name' : 'Future contributions',
                'alloc': '{:.0f}'.format(w_prime[1] * 100),
            }, {
                'name': 'Liability matching bonds and defined benefits',
                'alloc': '{:.0f}'.format(w_prime[2] * 100),
            }),
            'annuitize_equity_pct': '{:.0f}'.format(annuitize_equity * 100),
            'annuitize_fixed_pct': '{:.0f}'.format(annuitize_fixed * 100),
            'alloc_equity_pct': '{:.0f}'.format(alloc_equity * 100),
            'alloc_bonds_pct': '{:.0f}'.format(alloc_bonds * 100),
            'alloc_contributions_pct': '{:.0f}'.format(alloc_contrib * 100),
            'alloc_existing_db_pct': '{:.0f}'.format(alloc_existing_db * 100),
            'alloc_new_db_pct': '{:.0f}'.format(alloc_new_db * 100),
            'purchase_income_annuity': '{:,.0f}'.format(purchase_income_annuity),
            'aa_equity_pct': '{:.0f}'.format(aa_equity * 100),
            'aa_bonds_pct': '{:.0f}'.format(aa_bonds * 100),
        }
        return result

    def alloc(self, request):

        errors_present = False

        results = {}

        if request.method == 'POST':

            alloc_form = AllocForm(request.POST)

            if alloc_form.is_valid():

                try:

                    data = alloc_form.cleaned_data
                    date_str = data['date']
                    self.yield_curve_real = YieldCurve('real', date_str)
                    self.yield_curve_nominal = YieldCurve('nominal', date_str)
                    self.yield_curve_zero = YieldCurve('fixed', date_str)

                    if self.yield_curve_real.yield_curve_date == self.yield_curve_nominal.yield_curve_date:
                        results['yield_curve_date'] = self.yield_curve_real.yield_curve_date;
                    else:
                        results['yield_curve_date'] = self.yield_curve_real.yield_curve_date + ' real, ' + self.yield_curve_nominal.yield_curve_date + ' nominal';

                    table = 'ssa_cohort'

                    sex = data['sex']
                    age = float(data['age']);
                    self.life_table = LifeTable(table, sex, age)

                    sex2 = data['sex2']
                    if sex2 == None:
                        self.life_table2 = None
                    else:
                        age2 = float(data['age2']);
                        self.life_table2 = LifeTable(table, sex2, age2)

                    period_certain = 0
                    frequency = 12  # Makes NPV more accurate.
                    cpi_adjust = 'calendar'

                    npv_db = 0
                    results['db'] = []

                    for db in data['db']:

                        amount = float(db['amount'])

                        if amount == 0:
                            continue

                        yield_curve = self.yield_curve_real if db['inflation_indexed'] else self.yield_curve_nominal

                        if db['who'] == 'self':
                            starting_age = age
                            lt1 = self.life_table
                            lt2 = self.life_table2
                        else:
                            starting_age = age2
                            lt1 = self.life_table2
                            lt2 = self.life_table

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

                    self.pre_retirement_years = max(0, float(data['retirement_age']) - age)
                    payout_delay = self.pre_retirement_years * 12
                    joint_payout_fraction = float(data['joint_income_pct']) / 100
                    joint_contingent = True

                    scenario = Scenario(self.yield_curve_zero, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
                        joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                        frequency = frequency, cpi_adjust = cpi_adjust)
                    bonds_initial = scenario.price()
                    scenario = Scenario(self.yield_curve_real, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
                        joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, period_certain = period_certain, \
                        frequency = frequency, cpi_adjust = cpi_adjust)
                    scenario.price()
                    self.bonds_ret = bonds_initial / scenario.discount_single_year - 1
                    results['bonds_ret_pct'] = '{:.1f}'.format(self.bonds_ret * 100)
                    bonds_duration = scenario.duration
                    results['bonds_duration'] = '{:.1f}'.format(bonds_duration)

                    self.contribution = float(data['contribution'])
                    self.contribution_growth = float(data['contribution_growth_pct']) / 100
                    self.contribution_vol = float(data['contribution_vol_pct']) / 100
                    npv_contributions = self.npv_contrib(1 + self.contribution_growth)

                    npv_traditional = float(data['p_traditional_iras']) * (1 - float(data['tax_rate_pct']) / 100)
                    npv_roth = float(data['p_roth_iras'])
                    npv_taxable = float(data['p'])
                    npv_investments = npv_traditional + npv_roth + npv_taxable
                    npv = npv_db + npv_investments + npv_contributions

                    results['npv_db'] = '{:,.0f}'.format(npv_db)
                    results['npv_traditional'] = '{:,.0f}'.format(npv_traditional)
                    results['npv_roth'] = '{:,.0f}'.format(npv_roth)
                    results['npv_taxable'] = '{:,.0f}'.format(npv_taxable)
                    results['npv_investments'] = '{:,.0f}'.format(npv_investments)
                    results['npv_contributions'] = '{:,.0f}'.format(npv_contributions)
                    results['npv'] = '{:,.0f}'.format(npv)

                    if sex2 == None:
                        average_age = age
                    else:
                        average_age = (age + age2) / 2.0
                    results['calc'] = (
                        self.calc('Baseline estimate', 0, data, average_age, npv_db, npv_contributions, npv),
                        self.calc('Low estimate', - float(data['equity_range_factor']), data, average_age, npv_db, npv_contributions, npv),
                        self.calc('High estimate', float(data['equity_range_factor']), data, average_age, npv_db, npv_contributions, npv),
                    )

                except self.IdenticalCovarError:

                    errors = alloc_form._errors.setdefault(NON_FIELD_ERRORS, ErrorList())  # Simplified in Django 1.7.
                    errors.append('Two or more rows of covariance matrix appear equal under scaling. This means asset allocation has no unique solution.')

                    errors_present = True

                except YieldCurve.NoData:

                    errors = alloc_form._errors.setdefault('date', ErrorList())  # Simplified in Django 1.7.
                    errors.append('No interest rate data available for the specified date.')

                    errors_present = True

            else:

                errors_present = True

        else:

            alloc_form = AllocForm(self.default_alloc_params())

        return render(request, 'alloc.html', {
            'errors_present': errors_present,
            'alloc_form': alloc_form,
            'results': results,
        })

def alloc(request):
    return Alloc().alloc(request)
