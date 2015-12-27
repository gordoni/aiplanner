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
from math import ceil, exp, isnan, log, sqrt

from django.forms.forms import NON_FIELD_ERRORS
from django.forms.util import ErrorList
from django.shortcuts import render
from numpy import array
from numpy.linalg import inv, LinAlgError
from scipy.stats import lognorm, norm

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
            'bonds_contribution_corr_pct': 0,

            'retirement_age': 65,
            'joint_income_pct': 70,
            'desired_income': 40000,
            'purchase_income_annuity': True,

            'equity_ret_pct': Decimal('7.2'),
            'equity_vol_pct': Decimal('17'),
            'bonds_ret_pct': Decimal('1.1'),
            'bonds_vol_pct': Decimal('10'),
            'equity_bonds_corr_pct': 7,
            'equity_se_pct': Decimal('1.7'),
            'confidence_pct': 80,
            'expense_pct': Decimal('0.1'),

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
        # Convert volatility to lognormal distribution sigma parameter.
        sigma = sqrt(log((1 + sqrt(1 + 4 * vol ** 2)) / 2.0))
        g = sum(lognorm.ppf(percentiles, sigma)) / len(percentiles)
        g = float(g) # De-numpyfy.
        if isnan(g):
            # vol == 0.
            g = 1
        return g

    def yield_curve_schedule(self, life_table):

        def sched(y):
            return life_table.discount_rate(y) ** y

        return sched

    def stochastic_schedule(self, schedule, vol, years):

        def sched(y):
            if y < years:
                return schedule(y) * g ** y
            else:
                return 0

        g = self.vol_factor(vol)
        return sched

    def npv_contrib(self, schedule):
        payout_delay = 0
        schedule = self.stochastic_schedule(schedule, self.contribution_vol, self.pre_retirement_years)
        scenario = Scenario(self.yield_curve_real, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
            joint_payout_fraction = 1, joint_contingent = True, period_certain = 0, \
            frequency = 1, cpi_adjust = 'all', schedule = schedule)
        return self.contribution * scenario.price()

    def value_table(self, schedule):

        nv_db = 0
        results = {}
        display = {}
        display['db'] = []

        for db in self.db:

            amount = float(db['amount'])

            if amount == 0:
                continue

            yield_curve = self.yield_curve_real if db['inflation_indexed'] else self.yield_curve_nominal

            if db['who'] == 'self':
                starting_age = self.age
                lt1 = self.life_table
                lt2 = self.life_table2
            else:
                starting_age = self.age2
                lt1 = self.life_table2
                lt2 = self.life_table

            payout_delay = max(0, float(db['age']) - starting_age) * 12
            joint_payout_fraction = float(db['joint_payout_pct']) / 100
            joint_contingent = (db['joint_type'] == 'contingent')

            scenario = Scenario(yield_curve, payout_delay, None, None, 0, lt1, life_table2 = lt2, \
                joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, \
                period_certain = self.period_certain, frequency = self.frequency, cpi_adjust = self.cpi_adjust, \
                schedule = schedule)
            price = scenario.price() * amount
            nv_db += price

            display['db'].append({
                'description': db['description'],
                'who': db['who'],
                'nv': '{:,.0f}'.format(price),
            })

        nv_contributions = self.npv_contrib(lambda y: schedule(y) * (1 + self.contribution_growth) ** y)

        nv_traditional = self.traditional * (1 - self.tax_rate) / 100
        nv_investments = nv_traditional + self.npv_roth + self.npv_taxable
        nv = nv_db + nv_investments + nv_contributions

        results['nv_contributions'] = nv_contributions
        results['nv_db'] = nv_db
        results['nv'] = nv

        display['nv_db'] = '{:,.0f}'.format(nv_db)
        display['nv_traditional'] = '{:,.0f}'.format(nv_traditional)
        display['nv_roth'] = '{:,.0f}'.format(self.npv_roth)
        display['nv_taxable'] = '{:,.0f}'.format(self.npv_taxable)
        display['nv_investments'] = '{:,.0f}'.format(nv_investments)
        display['nv_contributions'] = '{:,.0f}'.format(nv_contributions)
        display['nv'] = '{:,.0f}'.format(nv)

        return results, display

    def calc(self, description, factor, data, results, consume, lm_bonds_ret):

        expense = float(data['expense_pct']) / 100
        equity_ret = float(data['equity_ret_pct']) / 100 - expense
        equity_ret += factor * float(data['equity_se_pct']) / 100
        bonds_ret = float(data['bonds_ret_pct']) / 100 - expense
        gamma = float(data['gamma'])
        equity_vol = float(data['equity_vol_pct']) / 100
        bonds_vol = float(data['bonds_vol_pct']) / 100
        equity_contribution_corr = float(data['equity_contribution_corr_pct']) / 100
        bonds_contribution_corr = float(data['bonds_contribution_corr_pct']) / 100
        equity_bonds_corr = float(data['equity_bonds_corr_pct']) / 100
        cov_ec2 = equity_vol * self.contribution_vol * equity_contribution_corr ** 2
        cov_bc2 = bonds_vol * self.contribution_vol * bonds_contribution_corr ** 2
        cov_eb2 = equity_vol * bonds_vol * equity_bonds_corr ** 2
        stocks_index = 0
        bonds_index = 1
        contrib_index = 2
        risk_free_index = 3

        lo = -0.5
        hi = 0.5
        while (hi - lo) > 0.000001:
            future_growth_try = (lo + hi) / 2.0
            sigma_matrix = (
                (equity_vol ** 2, cov_eb2, cov_ec2),
                (cov_eb2, bonds_vol ** 2, cov_bc2),
                (cov_ec2, cov_bc2, self.contribution_vol ** 2)
            )
            alpha = (equity_ret, bonds_ret, future_growth_try)
            w = list(self.solve_merton(gamma, sigma_matrix, alpha, lm_bonds_ret))
            w.append(1 - sum(w))
            discounted_contrib = self.npv_contrib(lambda y: ((1 + self.contribution_growth) / (1 + future_growth_try)) ** y)
            npv_discounted = results['nv'] - results['nv_contributions'] + discounted_contrib
            try:
                wc_discounted = discounted_contrib / npv_discounted
            except ZeroDivisionError:
                wc_discounted = 0
            if wc_discounted > w[contrib_index]:
                lo = future_growth_try
            else:
                hi = future_growth_try
        try:
            w_prime = list(wi * npv_discounted / results['nv'] for wi in w)
        except ZeroDivisionError:
            w_prime = list(0 for _ in w)
        w_prime[contrib_index] = 0
        w_prime[contrib_index] = 1 - sum(w_prime)

        try:
            w_alloc = list(wi * min(self.desired_income / consume, 1) for wi in w)
        except ZeroDivisionError:
            w_alloc = list(0 for _ in w)
        w_alloc[stocks_index] = 0
        w_alloc[contrib_index] = w_prime[contrib_index]
        w_alloc[stocks_index] = 1 - sum(w_alloc)
        if data['purchase_income_annuity']:
            annuitize_equity = min(max(0, (self.min_age - 50.0) / (80 - 50)), 1)
            annuitize_fixed = min(max(0, (self.min_age - 35.0) / (60 - 35)), 1)
        else:
            annuitize_equity = 0
            annuitize_fixed = 0
        alloc_equity = min(max(0, w_alloc[stocks_index] * (1 - annuitize_equity)), 1)
        alloc_bonds = min(max(0, w_alloc[bonds_index] * (1 - annuitize_fixed)), 1)
        alloc_contrib = results['nv_contributions'] / results['nv']
        alloc_lm_bonds = min(max(0, w_alloc[risk_free_index] * (1 - annuitize_fixed)), 1)
        alloc_db = 1 - alloc_equity - alloc_bonds - alloc_contrib - alloc_lm_bonds
        try:
            alloc_existing_db = results['nv_db'] / results['nv']
        except ZeroDivisionError:
            alloc_existing_db = 0
        shortfall = alloc_db - alloc_existing_db
        if data['purchase_income_annuity']:
            shortfall = min(0, shortfall)
        alloc_db -= shortfall
        alloc_lm_bonds += shortfall
        if alloc_lm_bonds < 0:
            surplus = alloc_lm_bonds
        else:
            surplus = max(alloc_lm_bonds - 1, 0)
        alloc_lm_bonds -= surplus
        alloc_bonds += surplus
        if alloc_bonds < 0:
            surplus = alloc_bonds
        else:
            surplus = max(alloc_bonds - 1, 0)
        alloc_bonds -= surplus
        alloc_equity += surplus
        alloc_new_db = alloc_db - alloc_existing_db
        purchase_income_annuity = alloc_new_db * results['nv']
        try:
            aa_equity = alloc_equity / (alloc_equity + alloc_bonds + alloc_lm_bonds)
        except ZeroDivisionError:
            aa_equity = 1
        aa_bonds = 1 - aa_equity

        result = {
            'description': description,
            'future_growth_try_pct': '{:.1f}'.format(future_growth_try * 100),
            'w' : ({
                'name' : 'Discounted future contributions',
                'alloc': '{:.0f}'.format(w[contrib_index] * 100),
            }, {
                'name': 'Stocks',
                'alloc': '{:.0f}'.format(w[stocks_index] * 100),
            }, {
                'name': 'Regular bonds',
                'alloc': '{:.0f}'.format(w[bonds_index] * 100),
            }, {
                'name': 'Liability matching bonds and defined benefits',
                'alloc': '{:.0f}'.format(w[risk_free_index] * 100),
            }),
            'discounted_contrib': '{:,.0f}'.format(discounted_contrib),
            'wc_discounted':  '{:.0f}'.format(wc_discounted * 100),
            'w_prime' : ({
                'name' : 'Future contributions',
                'alloc': '{:.0f}'.format(w_prime[contrib_index] * 100),
            }, {
                'name': 'Stocks',
                'alloc': '{:.0f}'.format(w_prime[stocks_index] * 100),
            }, {
                'name': 'Regular bonds',
                'alloc': '{:.0f}'.format(w_prime[bonds_index] * 100),
            }, {
                'name': 'Liability matching bonds and defined benefits',
                'alloc': '{:.0f}'.format(w_prime[risk_free_index] * 100),
            }),
            'annuitize_equity_pct': '{:.0f}'.format(annuitize_equity * 100),
            'annuitize_fixed_pct': '{:.0f}'.format(annuitize_fixed * 100),
            'alloc_equity_pct': '{:.0f}'.format(alloc_equity * 100),
            'alloc_bonds_pct': '{:.0f}'.format(alloc_bonds * 100),
            'alloc_lm_bonds_pct': '{:.0f}'.format(alloc_lm_bonds * 100),
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
                        results['yield_curve_date'] = self.yield_curve_real.yield_curve_date + ' real, ' + \
                            self.yield_curve_nominal.yield_curve_date + ' nominal';

                    table = 'ssa_cohort'

                    sex = data['sex']
                    self.age = float(data['age'])
                    self.life_table = LifeTable(table, sex, self.age)

                    sex2 = data['sex2']
                    if sex2 == None:
                        self.life_table2 = None
                    else:
                        self.age2 = float(data['age2']);
                        self.life_table2 = LifeTable(table, sex2, self.age2)

                    self.db = data['db']
                    self.traditional = float(data['p_traditional_iras'])
                    self.tax_rate = float(data['tax_rate_pct']) / 100
                    self.npv_roth = float(data['p_roth_iras'])
                    self.npv_taxable = float(data['p'])
                    self.contribution = float(data['contribution'])
                    self.contribution_growth = float(data['contribution_growth_pct']) / 100
                    self.contribution_vol = float(data['contribution_vol_pct']) / 100
                    self.pre_retirement_years = max(0, float(data['retirement_age']) - self.age)
                    self.joint_income = float(data['joint_income_pct']) / 100
                    self.desired_income = float(data['desired_income'])

                    self.period_certain = 0
                    self.frequency = 12 # Makes NPV more accurate.
                    self.cpi_adjust = 'calendar'

                    npv_results, npv_display = self.value_table(schedule = self.yield_curve_schedule(self.yield_curve_zero))
                    results['present'] = npv_display
                    results['db'] = []
                    for db in npv_display['db']:
                        results['db'].append({'present': db})
                    #for i, db in enumerate(future_display['db']):
                    #    results['db'][i]['future'] = db

                    payout_delay = self.pre_retirement_years * 12
                    joint_payout_fraction = self.joint_income
                    joint_contingent = True

                    scenario = Scenario(self.yield_curve_zero, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
                        joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, \
                        period_certain = self.period_certain, frequency = self.frequency, cpi_adjust = self.cpi_adjust)
                    bonds_initial = scenario.price()
                    scenario = Scenario(self.yield_curve_real, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
                        joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, \
                        period_certain = self.period_certain, frequency = self.frequency, cpi_adjust = self.cpi_adjust)
                    bonds_final = scenario.price()
                    lm_bonds_ret = bonds_initial / scenario.discount_single_year - 1
                    lm_bonds_duration = scenario.duration
                    future_value = npv_results['nv'] * bonds_initial / bonds_final
                    retirement_life_expectancy = bonds_initial
                    consume = future_value / max(retirement_life_expectancy, 8)

                    results['lm_bonds_ret_pct'] = '{:.1f}'.format(lm_bonds_ret * 100)
                    results['lm_bonds_duration'] = '{:.1f}'.format(lm_bonds_duration)
                    results['future_value'] = '{:,.0f}'.format(future_value)
                    results['retirement_life_expectancy'] = '{:.1f}'.format(retirement_life_expectancy)
                    results['consume'] = '{:,.0f}'.format(consume)

                    if sex2 == None:
                        self.min_age = self.age
                    else:
                        self.min_age = min(self.age, self.age2)
                    factor = norm.ppf(0.5 + float(data['confidence_pct']) / 100 / 2)
                    factor = float(factor) # De-numpyfy.
                    results['calc'] = (
                        self.calc('Baseline estimate', 0, data, npv_results, consume, lm_bonds_ret),
                        self.calc('Low estimate', - factor, data, npv_results, consume, lm_bonds_ret),
                        self.calc('High estimate', factor, data, npv_results, consume, lm_bonds_ret),
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
