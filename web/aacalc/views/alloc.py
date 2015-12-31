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
from os import umask
from tempfile import mkdtemp

from django.forms.forms import NON_FIELD_ERRORS
from django.forms.util import ErrorList
from django.shortcuts import render
from numpy import array
from numpy.linalg import inv, LinAlgError
from scipy.stats import lognorm, norm
from subprocess import check_call

from aacalc.forms import AllocForm
from aacalc.spia import LifeTable, Scenario, YieldCurve
from settings import STATIC_ROOT, STATIC_URL

class Alloc:

    class IdenticalCovarError(Exception):
        pass

    def default_alloc_params(self):

        return {
            'sex': 'male',
            'age': 50,
            'le_add': 8,
            'sex2': None,
            'age2': None,
            'le_add2': 8,
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

    def geomean(self, mean, vol):
        # Convert mean and vol to lognormal distribution mu and sigma parameters.
        mu = log(mean ** 2 / sqrt(vol ** 2 + mean ** 2))
        sigma = sqrt(log(vol ** 2 / mean ** 2 + 1))
        # Compute the middle value.
        geomean = lognorm.ppf(0.5, sigma, scale=exp(mu))
        geomean = float(geomean) # De-numpyfy.
        if isnan(geomean):
            # vol == 0.
            geomean = mean
        return geomean

    def solve_merton(self, gamma, sigma_matrix, alpha, r):
        try:
            w = inv(sigma_matrix).dot(array(alpha) - r) / gamma
        except LinAlgError:
            raise self.IdenticalCovarError
        return tuple(float(wi) for wi in w) # De-numpyfy.

    def yield_curve_schedule(self, life_table):

        def sched(y):
            return life_table.discount_rate(y) ** y

        return sched

    def stochastic_schedule(self, mean, years = None):

        def sched(y):
            if years == None or y < years:
                return mean ** y
            else:
                return 0

        return sched

    def npv_contrib(self, ret):
        payout_delay = 0
        schedule = self.stochastic_schedule(1 + ret, self.pre_retirement_years)
        scenario = Scenario(self.yield_curve_real, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
            joint_payout_fraction = 1, joint_contingent = True, period_certain = self.period_certain, \
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

        nv_contributions = self.npv_contrib(self.contribution_growth)

        nv_traditional = self.traditional * (1 - self.tax_rate)
        nv_investments = nv_traditional + self.npv_roth + self.npv_taxable
        nv = nv_db + nv_investments + nv_contributions

        results['nv_contributions'] = nv_contributions
        results['nv_db'] = nv_db
        results['nv_investments'] = nv_investments
        results['nv'] = nv

        display['nv_db'] = '{:,.0f}'.format(nv_db)
        display['nv_traditional'] = '{:,.0f}'.format(nv_traditional)
        display['nv_roth'] = '{:,.0f}'.format(self.npv_roth)
        display['nv_taxable'] = '{:,.0f}'.format(self.npv_taxable)
        display['nv_investments'] = '{:,.0f}'.format(nv_investments)
        display['nv_contributions'] = '{:,.0f}'.format(nv_contributions)
        display['nv'] = '{:,.0f}'.format(nv)

        return results, display

    def calc(self, description, factor, data, results):

        payout_delay = self.pre_retirement_years * 12
        joint_payout_fraction = self.joint_income
        joint_contingent = True

        scenario = Scenario(self.yield_curve_zero, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
            joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, \
            period_certain = 0, frequency = self.frequency, cpi_adjust = self.cpi_adjust)
        bonds_initial = scenario.price()
        retirement_life_expectancy = bonds_initial
        scenario = Scenario(self.yield_curve_real, payout_delay, None, None, 0, self.life_table, life_table2 = self.life_table2, \
            joint_payout_fraction = joint_payout_fraction, joint_contingent = joint_contingent, \
            period_certain = 0, frequency = self.frequency, cpi_adjust = self.cpi_adjust)
        scenario.price()
        lm_bonds_ret = bonds_initial / scenario.discount_single_year - 1
        lm_bonds_duration = scenario.duration

        expense = float(data['expense_pct']) / 100
        equity_ret = float(data['equity_ret_pct']) / 100 - expense
        equity_ret += factor * float(data['equity_se_pct']) / 100
        bonds_ret = float(data['bonds_ret_pct']) / 100 - expense
        gamma = float(data['gamma'])
        equity_vol = float(data['equity_vol_pct']) / 100
        bonds_vol = float(data['bonds_vol_pct']) / 100

        equity_gm = self.geomean(1 + equity_ret, equity_vol) - 1
        bonds_gm = self.geomean(1 + bonds_ret, bonds_vol) - 1

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
        while hi - lo > 0.000001:
            future_growth_try = (lo + hi) / 2.0
            sigma_matrix = (
                (equity_vol ** 2, cov_eb2, cov_ec2),
                (cov_eb2, bonds_vol ** 2, cov_bc2),
                (cov_ec2, cov_bc2, self.contribution_vol ** 2)
            )
            alpha = (equity_ret, bonds_ret, future_growth_try)
            w = list(self.solve_merton(gamma, sigma_matrix, alpha, lm_bonds_ret))
            w.append(1 - sum(w))
            discounted_contrib = self.npv_contrib((1 + self.contribution_growth) / (1 + future_growth_try) - 1)
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

        lo = 0
        hi = 2 # First mid will be 1.
        while hi - lo > 0.000001:

            mid = (hi + lo) / 2.0
            w_alloc = list(wi * mid for wi in w)
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
            try:
                alloc_contrib = results['nv_contributions'] / results['nv']
            except:
                alloc_contrib = 1
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
            alloc_db = max(0, alloc_db) # Eliminate negative values from fp rounding errors.
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
            alloc_new_db = max(0, alloc_db - alloc_existing_db) # Eliminate negative values from fp rounding errors.
            purchase_income_annuity = alloc_new_db * results['nv']

            try:
                aa_equity = alloc_equity / (alloc_equity + alloc_bonds + alloc_lm_bonds)
            except ZeroDivisionError:
                aa_equity = 1
            aa_bonds = 1 - aa_equity

            total_ret = alloc_contrib * future_growth_try + alloc_equity * equity_ret + alloc_bonds * bonds_ret + \
                alloc_lm_bonds * lm_bonds_ret + alloc_db * lm_bonds_ret
            total_var = alloc_contrib ** 2 * self.contribution_vol ** 2 + \
                alloc_equity ** 2 * equity_vol ** 2 + \
                alloc_bonds ** 2 * bonds_vol ** 2 + \
                2 * alloc_contrib * alloc_equity * cov_ec2 + \
                2 * alloc_contrib * alloc_bonds * cov_bc2 + \
                2 * alloc_equity * alloc_bonds * cov_eb2
            total_vol = sqrt(total_var)

            # We should use total_var, total_vol, and gamma to compute the
            # annual consumption amount.  Merton's Continuous Time Finance
            # provides solutions for a single risky asset with a finite
            # time horizon, and many asset with a infinite time horizon,
            # but not many assets with a finite time horizon. And even if
            # such a solution existed we would also need to factor in
            # pre-retirement years. Instead we compute the withdrawal
            # amount for a compounding total portfolio.
            periodic_ret = total_ret
            try:
                c = periodic_ret * (1 + periodic_ret) ** (retirement_life_expectancy - 1) / \
                    ((1 + periodic_ret) ** retirement_life_expectancy - 1)
            except DivisionByZeroError:
                c = 1 / retirement_life_expectancy
            c *= (1 + periodic_ret) ** self.pre_retirement_years
            consume = c * results['nv']

            if mid * consume > self.desired_income:
                hi = mid
            else:
                if mid == 1:
                    break # Early exit for common case.
                lo = mid

        result = {
            'description': description,
            'lm_bonds_ret_pct': '{:.1f}'.format(lm_bonds_ret * 100),
            'lm_bonds_duration': '{:.1f}'.format(lm_bonds_duration),
            'retirement_life_expectancy': '{:.1f}'.format(retirement_life_expectancy),
            'consume': '{:,.0f}'.format(consume),
            'equity_am_pct':'{:.1f}'.format(equity_ret * 100),
            'bonds_am_pct':'{:.1f}'.format(bonds_ret * 100),
            'equity_gm_pct':'{:.1f}'.format(equity_gm * 100),
            'bonds_gm_pct':'{:.1f}'.format(bonds_gm * 100),
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
            'equity_ret_pct': '{:.1f}'.format(equity_ret * 100),
            'bonds_ret_pct': '{:.1f}'.format(bonds_ret * 100),
            'lm_bonds_ret_pct': '{:.1f}'.format(lm_bonds_ret * 100),
            'total_ret_pct': '{:.1f}'.format(total_ret * 100),
            'total_vol_pct': '{:.1f}'.format(total_vol * 100),
            'alloc_equity': alloc_equity,
            'alloc_bonds': alloc_bonds,
            'alloc_lm_bonds': alloc_lm_bonds,
            'alloc_contributions': alloc_contrib,
            'alloc_existing_db': alloc_existing_db,
            'alloc_new_db': alloc_new_db,
            'aa_equity': aa_equity,
            'aa_bonds': aa_bonds,
        }
        return result

    def plot(self, result):
        umask(0077)
        parent = STATIC_ROOT + 'results'
        dirname = mkdtemp(prefix='aa-', dir=parent)
        f = open(dirname + '/alloc.csv', 'w')
        f.write('''class,allocation
stocks,%(alloc_equity)f
regular bonds,%(alloc_bonds)f
LM bonds,%(alloc_lm_bonds)f
defined benefits,%(alloc_existing_db)f
new annuities,%(alloc_new_db)f
future contribs,%(alloc_contributions)f
''' % result)
        f.close()
        f = open(dirname + '/aa.csv', 'w')
        f.write('''asset class,allocation
stocks,%(aa_equity)f
bonds,%(aa_bonds)f
''' % result)
        f.close()
        cmd = __file__.replace('aacalc/views/alloc.py', 'plot.R')
        prefix = dirname + '/'
        check_call((cmd, '--args', prefix))
        return dirname

    def alloc(self, request):

        errors_present = False

        results = {}

        if request.method == 'POST':

            alloc_form = AllocForm(request.POST)

            if alloc_form.is_valid():

                try:

                    data = alloc_form.cleaned_data
                    self.date_str = data['date']
                    self.yield_curve_real = YieldCurve('real', self.date_str)
                    self.yield_curve_nominal = YieldCurve('nominal', self.date_str)
                    self.yield_curve_zero = YieldCurve('fixed', self.date_str)

                    if self.yield_curve_real.yield_curve_date == self.yield_curve_nominal.yield_curve_date:
                        results['yield_curve_date'] = self.yield_curve_real.yield_curve_date;
                    else:
                        results['yield_curve_date'] = self.yield_curve_real.yield_curve_date + ' real, ' + \
                            self.yield_curve_nominal.yield_curve_date + ' nominal';

                    table = 'ssa_cohort'

                    sex = data['sex']
                    self.age = float(data['age'])
                    self.le_add = float(data['le_add'])
                    self.life_table = LifeTable(table, sex, self.age, le_add = self.le_add, date_str = self.date_str)

                    sex2 = data['sex2']
                    if sex2 == None:
                        self.life_table2 = None
                    else:
                        self.age2 = float(data['age2']);
                        self.le_add2 = float(data['le_add2'])
                        self.life_table2 = LifeTable(table, sex2, self.age2, le_add = self.le_add2, date_str = self.date_str)

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

                    self.period_certain = self.pre_retirement_years
                        # For planning purposes when computing the npv of defined benefits
                        # and contributions we need to assume we will reach retirement.

                    self.frequency = 12 # Makes NPV more accurate.
                    self.cpi_adjust = 'calendar'

                    npv_results, npv_display = self.value_table(schedule = self.yield_curve_schedule(self.yield_curve_zero))
                    results['present'] = npv_display
                    results['db'] = []
                    for db in npv_display['db']:
                        results['db'].append({'present': db})
                    #for i, db in enumerate(future_display['db']):
                    #    results['db'][i]['future'] = db

                    if sex2 == None:
                        self.min_age = self.age
                    else:
                        self.min_age = min(self.age, self.age2)
                    factor = norm.ppf(0.5 + float(data['confidence_pct']) / 100 / 2)
                    factor = float(factor) # De-numpyfy.
                    results['calc'] = (
                        self.calc('Baseline estimate', 0, data, npv_results),
                        self.calc('Low estimate', - factor, data, npv_results),
                        self.calc('High estimate', factor, data, npv_results),
                    )

                    dirname = self.plot(results['calc'][0])
                    results['dirurl'] = dirname.replace(STATIC_ROOT, STATIC_URL)

                except LifeTable.UnableToAdjust:

                    errors = alloc_form._errors.setdefault('le_add2', ErrorList())  # Simplified in Django 1.7.
                    errors.append('Unable to adjust life table.')

                    errors_present = True

                except YieldCurve.NoData:

                    errors = alloc_form._errors.setdefault('date', ErrorList())  # Simplified in Django 1.7.
                    errors.append('No interest rate data available for the specified date.')

                    errors_present = True

                except self.IdenticalCovarError:

                    errors = alloc_form._errors.setdefault(NON_FIELD_ERRORS, ErrorList())  # Simplified in Django 1.7.
                    errors.append('Two or more rows of covariance matrix appear equal under scaling. This means asset allocation has no unique solution.')

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
