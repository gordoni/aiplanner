# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from datetime import datetime, timedelta
from json import loads
from math import atanh, ceil, copysign, exp, floor, isinf, isnan, log, sqrt, tanh
from os import environ
from os.path import expanduser
from random import seed, randint, random, uniform, lognormvariate
from sys import stderr

import numpy as np

import cython

from spia import LifeTable, YieldCurve, IncomeAnnuity

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.bonds import BondsSet
from gym_fin.envs.defined_benefit import DefinedBenefit
from gym_fin.envs.policies import policy
from gym_fin.envs.returns import Returns, returns_report, yields_report
from gym_fin.envs.returns_equity import ReturnsEquity
from gym_fin.envs.returns_sample import ReturnsSample
from gym_fin.envs.taxes import Taxes, contribution_limit
from gym_fin.envs.utility import Utility

class FinError(Exception):

    pass

@cython.cclass
class Fin:

    def warn(self, *args):

        if self.params.warn:
            stderr.write('AIPLANNER: ' + ' '.join(str(arg) for arg in args) + '\n')
            #print('AIPLANNER:', *args, file = stderr)

    def _compute_vital_stats(self, age_start, age_start2, preretirement):

        start_date = datetime.strptime(self.params.life_table_date, '%Y-%m-%d')
        this_year = datetime(start_date.year, 1, 1)
        next_year = datetime(start_date.year + 1, 1, 1)
        start_decimal_year = start_date.year + (start_date - this_year) / (next_year - this_year)

        alive_both = [1 if self.sex2 else 0] # Probability across all rollouts.
        alive_one = [0 if self.sex2 else 1] # Probability across all rollouts.
        _alive = 1
        _alive2 = 1

        alive_single = [None if self.sex2 else 1] # Probability for this couple rollout.
        _alive_single = None if self.sex2 else 1
        dead = False
        dead2 = self.sex2 == None
        dead_at = random()
        dead_at2 = random()
        only_alive2 = False

        alive_count = [2 if self.sex2 else 1] # Mock count of number of individuals alive. Only used for plots, for computations use alive_single probability.
        _alive_count = 2 if self.sex2 else 1

        y = 0
        q_y = -1
        q = 0
        q2 = 0
        remaining_fract = 0
        a_y = self.params.time_period
        while True:
            append_time = a_y - y
            fract = min(remaining_fract, append_time)
            prev_alive = _alive
            prev_alive2 = _alive2
            q_fract = (1 - q) ** fract
            _alive *= q_fract
            q_fract2 = (1 - q2) ** fract
            _alive2 *= q_fract2
            if not (dead or dead2):
                dead = _alive < dead_at
                dead2 = dead if self.params.couple_death_concordant else _alive2 < dead_at2
                if dead and dead2:
                    _alive_single = 0
                    _alive_count = 0
                elif dead:
                    only_alive2 = True
                    _alive_single = q_fract2 ** ((dead_at - _alive) / (prev_alive - _alive))
                    _alive_count = 1
                elif dead2:
                    _alive_single = q_fract ** ((dead_at2 - _alive2) / (prev_alive2 - _alive2))
                    _alive_count = 1
            elif dead:
                _alive_single *= q_fract2
                if _alive2 < dead_at2:
                    _alive_count = 0
            elif dead2:
                _alive_single *= q_fract
                if _alive < dead_at:
                    _alive_count = 0
            remaining_fract -= fract
            y += fract
            if y >= a_y:
                alive_both.append(_alive * _alive2)
                alive_one.append(1 - _alive * _alive2 - (1 - _alive) * (1 - _alive2))
                alive_single.append(_alive_single)
                alive_count.append(_alive_count)
                a_y += self.params.time_period
            if y - q_y >= 1:
                q_y += 1
                q = self.life_table.q(age_start + q_y, year = start_decimal_year + q_y)
                if self.sex2:
                    q2 = self.life_table2.q(age_start2 + q_y, year = start_decimal_year + q_y)
                else:
                    q2 = 1
                remaining_fract = 1
                if q == q2 == 1:
                    break

        alive_either = tuple(alive_one[i] + alive_both[i] for i in range(len(alive_one)))

        life_expectancy_both = self.sums_to_end(alive_both, 0, alive_both)
        life_expectancy_one = self.sums_to_end(alive_one, 0, alive_either)

        percentile = 0.8
        alive_weighted = list(alive_one[i] + alive_both[i] * (1 + self.params.consume_additional) for i in range(len(alive_one)))
        alive_weighted.append(0)
        life_percentile = []
        j = len(alive_weighted) - 1
        for i in range(len(alive_weighted) - 1, -1, -1):
            target = (1 - percentile) * alive_weighted[i]
            while alive_weighted[j] <= target and j >= i:
                j -= 1
            try:
                partial = (alive_weighted[j] - target) / (alive_weighted[j] - alive_weighted[j + 1])
            except (IndexError, ZeroDivisionError):
                partial = 0
            life_percentile.insert(0, (j - i + 1 + partial) * self.params.time_period)

        retired_index = ceil(preretirement / self.params.time_period)
        retirement_expectancy_both = self.sums_to_end(alive_both, retired_index, alive_both)
        retirement_expectancy_one = self.sums_to_end(alive_one, retired_index, alive_either)
        retirement_expectancy_single = self.sums_to_end(alive_single, retired_index, alive_single)

        alive_single.append(0)
        alive_count.append(0)

        if not self.params.probabilistic_life_expectancy:
            alive_single = tuple(None if _alive_count == 2 else _alive_count for _alive_count in alive_count)

        self.only_alive2, self.alive_single, self.alive_count, self.life_expectancy_both, self.life_expectancy_one, self.life_percentile, \
            self.retirement_expectancy_both, self.retirement_expectancy_one, self.retirement_expectancy_single = \
            only_alive2, tuple(alive_single), tuple(alive_count), tuple(life_expectancy_both), tuple(life_expectancy_one), tuple(life_percentile), \
            tuple(retirement_expectancy_both), tuple(retirement_expectancy_one), tuple(retirement_expectancy_single)

    def sums_to_end(self, l, start, divl):

        r = [0]
        s = 0
        for i in range(len(l) - 1, -1, -1):
            if i >= start:
                try:
                    s += l[i]
                except TypeError:
                    s = None
            try:
                v = s / divl[i] * self.params.time_period
            except TypeError:
                v = None
            except ZeroDivisionError:
                assert s == 0
                v = 0
            r.insert(0, v)

        return r

    def __init__(self, fin_env, direct_action, params):

        self.observation_space_items = fin_env.observation_space_items
        self.observation_space = fin_env.observation_space
        self.direct_action = direct_action
        self.params = params

        self.observation_space_range = self.observation_space.high - self.observation_space.low
        self.observation_space_scale = 2 / self.observation_space_range
        self.observation_space_shift = -1 - self.observation_space.low * self.observation_space_scale
        self.observation_space_extreme_range = self.params.observation_space_warn * self.observation_space_range
        self.observation_space_extreme_range[self.observation_space_items.index('reward_to_go_estimate')] *= 2
        self.observation_space_extreme_range[self.observation_space_items.index('relative_ce_estimate_individual')] *= 3
        self.observation_space_extreme_range[self.observation_space_items.index('stocks_price')] *= 2
        self.observation_space_extreme_range[self.observation_space_items.index('stocks_volatility')] *= 2
        self.observation_space_extreme_range[self.observation_space_items.index('real_interest_rate')] = 0.30
        self.observation_space_range_exceeded = np.zeros(shape = self.observation_space_extreme_range.shape, dtype = 'int')
        self.observation_space_extreme_range = self.observation_space_extreme_range.tolist() # De-numpify.
        self.observation_space_range_exceeded = self.observation_space_range_exceeded.tolist()

        self.env_timesteps = 0
        self.env_couple_timesteps = 0
        self.env_single_timesteps = 0

        self._init_done = False

    def _init(self):

        np.seterr(divide = 'raise', over = 'raise', under = 'ignore', invalid = 'raise')

        home_dir = environ.get('AIPLANNER_HOME', expanduser('~/aiplanner'))

        self._cvs_key = None

        self.life_table_age = -1
        self.life_table2_age = -1

        assert self.params.sex in ('male', 'female'), 'sex must be male or female.'
        assert self.params.sex2 in ('male', 'female'), 'sex2 must be male or female.'

        self.age_start = self.params.age_start
        self.death_age = self.params.age_end - self.params.time_period
        self.life_table_le_hi = LifeTable(self.params.life_table, self.params.sex, self.age_start,
            death_age = self.death_age, le_add = self.params.life_expectancy_additional_high, date_str = self.params.life_table_date, interpolate_q = False)

        if self.params.stocks_model == 'bootstrap':
            std_res_fname = home_dir + '/data/public/standardized_residuals.csv'
            self.stocks = ReturnsEquity(self.params, std_res_fname = std_res_fname)
        else:
            self.stocks = Returns(self.params.stocks_return, self.params.stocks_volatility,
                self.params.stocks_standard_error if self.params.returns_standard_error else 0, self.params.time_period)
        self.iid_bonds = Returns(self.params.iid_bonds_return, self.params.iid_bonds_volatility,
            self.params.bonds_standard_error if self.params.returns_standard_error else 0, self.params.time_period)
        self.bills = Returns(self.params.bills_return, self.params.bills_volatility,
            self.params.bills_standard_error if self.params.returns_standard_error else 0, self.params.time_period)

        self.bonds = BondsSet(fixed_real_bonds_rate = self.params.fixed_real_bonds_rate, fixed_nominal_bonds_rate = self.params.fixed_nominal_bonds_rate,
            static_bonds = self.params.static_bonds, date_str = self.params.bonds_date, date_str_low = self.params.bonds_date_start,
            real_r0_type = self.params.real_short_rate_type, inflation_r0_type = self.params.inflation_short_rate_type)
        self.bonds.update(
            fixed_real_bonds_rate = self.params.fixed_real_bonds_rate, fixed_nominal_bonds_rate = self.params.fixed_nominal_bonds_rate,
            real_short_rate = self.params.real_short_rate_value, inflation_short_rate = self.params.inflation_short_rate_value,
            real_standard_error = self.params.bonds_standard_error if self.params.returns_standard_error else 0,
            inflation_standard_error = self.params.inflation_standard_error if self.params.returns_standard_error else 0,
            time_period = self.params.time_period)
        self.bonds_stepper = self.bonds.nominal
        self.bonds_zero = YieldCurve('fixed', self.params.life_table_date)
        self.bonds_constant_inflation = YieldCurve('fixed', self.params.life_table_date, adjust = exp(self.bonds.inflation.spot(100)) - 1)

        if self.params.iid_bonds:
            if self.params.iid_bonds_type == 'real':
                self.iid_bonds = ReturnsSample(self.bonds.real, self.params.iid_bonds_duration,
                    self.params.bonds_standard_error if self.params.returns_standard_error else 0,
                    stepper = self.bonds_stepper, time_period = self.params.time_period)
            elif self.params.iid_bonds_type == 'nominal':
                self.iid_bonds = ReturnsSample(self.bonds.nominal, self.params.iid_bonds_duration,
                    self.params.bonds_standard_error if self.params.returns_standard_error else 0,
                    stepper = self.bonds_stepper, time_period = self.params.time_period)

        if self.params.display_returns:

            print()
            print('Real/nominal yields:')

            if self.params.real_bonds:
                if self.params.real_bonds_duration:
                    yields_report('real bonds {:2d}'.format(int(self.params.real_bonds_duration)), self.bonds.real,
                        duration = self.params.real_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
                else:
                    yields_report('real bonds  5', self.bonds.real, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                    yields_report('real bonds 15', self.bonds.real, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

            if self.params.nominal_bonds:
                if self.params.nominal_bonds_duration:
                    yields_report('nominal bonds {:2d}'.format(int(self.params.nominal_bonds_duration)), self.bonds.nominal,
                        duration = self.params.nominal_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
                else:
                    yields_report('nominal bonds  5', self.bonds.nominal, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                    yields_report('nominal bonds 15', self.bonds.nominal, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

            print()
            print('Real returns:')

            if self.params.stocks:
                returns_report('stocks', self.stocks, time_period = self.params.time_period, sample_count = 5000, sample_skip = 10)

            if self.params.real_bonds:
                if self.params.real_bonds_duration:
                    returns_report('real bonds {:2d}'.format(int(self.params.real_bonds_duration)), self.bonds.real,
                        duration = self.params.real_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
                else:
                    returns_report('real bonds  5', self.bonds.real, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                    returns_report('real bonds 15', self.bonds.real, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

            if self.params.nominal_bonds:
                if self.params.nominal_bonds_duration:
                    returns_report('nominal bonds {:2d}'.format(int(self.params.nominal_bonds_duration)), self.bonds.nominal,
                        duration = self.params.nominal_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
                else:
                    returns_report('nominal bonds  5', self.bonds.nominal, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                    returns_report('nominal bonds 15', self.bonds.nominal, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

            if self.params.iid_bonds:
                returns_report('iid bonds', self.iid_bonds, time_period = self.params.time_period)

            if self.params.bills:
                returns_report('bills', self.bills, time_period = self.params.time_period)

            if self.params.nominal_bonds or self.params.nominal_spias:
                returns_report('inflation', self.bonds.inflation,
                    duration = self.params.time_period, stepper = self.bonds_stepper, time_period = self.params.time_period)

        self._init_done = True

    def gi_sum(self, type = None, source = ('tax_free', 'tax_deferred', 'taxable')):

        gi = 0
        preretirement_income_source = 'taxable' if self.params.income_preretirement_taxable else 'tax_free'
        if type in (None, 'Preretirement Income') and preretirement_income_source in source:
            gi += self.income_preretirement + self.income_preretirement2
        for db in self.defined_benefits.values():
            if type in (None, db.type) and db.type_of_funds in source:
                gi += db.payout()

        return gi

    def p_sum(self):

        return self.p_tax_free + self.p_tax_deferred + self.p_taxable

    def get_db(self, type, real, type_of_funds):

        key = (type_of_funds, real, type == 'social_security')
        try:
            db = self.defined_benefits[key]
        except KeyError:
            db = DefinedBenefit(self, type = type, real = real, type_of_funds = type_of_funds)
            self.defined_benefits[key] = db

        return db

    def add_db(self, type = 'income_annuity', owner = 'self', start = None, end = None, probability = 1, premium = None, payout = None,
        inflation_adjustment = 'cpi', joint = False, payout_fraction = 0, source_of_funds = 'tax_deferred', exclusion_period = 0, exclusion_amount = 0,
        delay_calcs = False):

        assert owner in ('self', 'spouse')
        assert source_of_funds in ('tax_free', 'tax_deferred', 'taxable')

        if owner == 'spouse' and self.sex2 == None:
            return

        if random() >= probability:
            return

        if not self.couple:
            joint = False
            payout_fraction = 0

        real = inflation_adjustment == 'cpi'
        db = self.get_db(type, real, source_of_funds)
        adjustment = 0 if inflation_adjustment == 'cpi' else inflation_adjustment
        db.add(owner = owner, start = start, end = end, premium = premium, payout = payout, adjustment = adjustment,
            joint = joint, payout_fraction = payout_fraction,
            exclusion_period = exclusion_period, exclusion_amount = exclusion_amount, delay_calcs = delay_calcs)

    def parse_defined_benefits(self):

        def load(s):
            return loads(s) if isinstance(s, str) else s

        self.defined_benefits = {}
        for db in load(self.params.guaranteed_income) + load(self.params.guaranteed_income_additional):
            self.add_db(delay_calcs = True, **db)

        for db in self.defined_benefits.values():
            db.force_calcs()

    def age_uniform(self, low, high):
        if low == high:
            return low # Allow fractional ages.
        else:
            return randint(floor(low), ceil(high)) # SPIA module runs faster with non-fractional ages.

    def log_uniform(self, low, high):
        if low == high:
            return low # Handles low == high == 0.
        else:
            if low > 0:
                return exp(uniform(log(low), log(high)))
            else:
                return - exp(uniform(log(- low), log(- high)))

    def reset(self):

        if not self._init_done:
            self._init()

        if self.params.reproduce_episode != None:
            self._reproducable_seed(self.params.reproduce_episode, 0, 0)

        self.sex2 = self.params.sex2 if random() < self.params.couple_probability else None

        self.age = self.age_start
        self.age2 = self.age_uniform(self.params.age_start2_low, self.params.age_start2_high)
        le_add = self.age_uniform(self.params.life_expectancy_additional_low, self.params.life_expectancy_additional_high)
        le_add2 = self.age_uniform(self.params.life_expectancy_additional2_low, self.params.life_expectancy_additional2_high)
        self.age_retirement = uniform(self.params.age_retirement_low, self.params.age_retirement_high)

        if self.age != self.life_table_age or le_add != self.life_table_le_add:
            self.life_table = LifeTable(self.params.life_table, self.params.sex, self.age,
                death_age = self.death_age, le_add = le_add, date_str = self.params.life_table_date, interpolate_q = False)
            self.life_table_age = self.age
            self.life_table_le_add = le_add
        else:
            self.life_table.age = self.age # Undo hack (value gets messed with below).
        if self.sex2 == None:
            self.life_table2 = None
        elif self.age2 != self.life_table2_age or le_add2 != self.life_table_le_add2 or self.life_table2 == None:
            self.life_table2 = LifeTable(self.params.life_table, self.sex2, self.age2,
                death_age = self.death_age, le_add = le_add2, date_str = self.params.life_table_date, interpolate_q = False)
            self.life_table2_age = self.age2
            self.life_table_le_add2 = le_add2
        else:
            self.life_table2.age = self.age2

        # Try and ensure each training episode starts at the same life expectancy (at least if single).
        # This helps ensure set_reward_level() normalizes as consistently as possible. May not be necessary.
        adjust = self.life_table.age_add - self.life_table_le_hi.age_add
        self.age -= adjust
        self.life_table.age -= adjust
        if self.sex2 != None:
            self.age2 -= adjust
            self.life_table2.age -= adjust

        self.preretirement_years = max(0, self.age_retirement - self.age)

        # As a speedup create special matching life tables that cover just the preretirement years.
        self.life_table_preretirement = LifeTable(self.params.life_table, self.params.sex, self.age,
            death_age = self.age + self.preretirement_years + self.params.time_period, date_str = self.params.life_table_date, interpolate_q = False)
        self.life_table_preretirement.age_add = self.life_table.age_add
        if self.sex2 != None:
            self.life_table2_preretirement = LifeTable(self.params.life_table, self.sex2, self.age2,
                death_age = self.age2 + self.preretirement_years + self.params.time_period, date_str = self.params.life_table_date, interpolate_q = False)
            self.life_table2_preretirement.age_add = self.life_table2.age_add
        else:
            self.life_table2_preretirement = None

        key = (self.age, self.preretirement_years, le_add)
        if self.sex2 or not self.params.probabilistic_life_expectancy or key != self._cvs_key:
            # Can't cache vital stats for couple as would loose random rollouts of couple expectancy.
            # Additionally would need to save retirement_expectancy_one and retirement_expectancy_both as the get clobbered below.
            self._compute_vital_stats(self.age, self.age2, self.preretirement_years)
            self._cvs_key = key

        self.couple = self.alive_single[0] == None

        self.have_401k = bool(randint(int(self.params.have_401k_low), int(self.params.have_401k_high)))
        self.have_401k2 = bool(randint(int(self.params.have_401k2_low), int(self.params.have_401k2_high)))

        self.taxes_due = 0

        self.gamma = self.log_uniform(self.params.gamma_low, self.params.gamma_high)

        self.date_start = datetime.strptime(self.params.life_table_date, '%Y-%m-%d').date()
        self.date = self.date_start
        self.cpi = 1

        self.stocks.reset()
        self.iid_bonds.reset()
        self.bills.reset()

        self.bonds_stepper.reset()

        self.episode_length = 0

        found = False
        gi_fraction = 0
        for _ in range(1000):

            self.parse_defined_benefits()
            for db in self.defined_benefits.values():
                db.step(0) # Pick up non-zero schedule for observe.

            for _ in range(20):

                self.start_income_preretirement = self.log_uniform(self.params.income_preretirement_low, self.params.income_preretirement_high)
                self.start_income_preretirement2 = self.log_uniform(self.params.income_preretirement2_low, self.params.income_preretirement2_high)
                if self.params.income_preretirement_age_end != None:
                    self.income_preretirement_years = max(0, self.params.income_preretirement_age_end - self.age)
                else:
                    self.income_preretirement_years = self.preretirement_years
                if self.couple:
                    if self.params.income_preretirement_age_end2 != None:
                        self.income_preretirement_years2 = max(0, self.params.income_preretirement_age_end2 - self.age2)
                    else:
                        self.income_preretirement_years2 = self.preretirement_years
                else:
                    self.income_preretirement_years2 = 0
                self.income_preretirement = self.start_income_preretirement if self.income_preretirement_years > 0 else 0
                self.income_preretirement2 = self.start_income_preretirement2 if self.income_preretirement_years2 > 0 else 0

                assert not self.params.consume_preretirement or not self.params.consume_preretirement_income_ratio_high
                self.consume_preretirement = self.params.consume_preretirement + \
                    uniform(self.params.consume_preretirement_income_ratio_low, self.params.consume_preretirement_income_ratio_high) * \
                    (self.income_preretirement + self.income_preretirement2)

                p_tax_free_weight = uniform(self.params.p_tax_free_weight_low, self.params.p_tax_free_weight_high)
                p_tax_deferred_weight = uniform(self.params.p_tax_deferred_weight_low, self.params.p_tax_deferred_weight_high)
                p_taxable_stocks_weight = uniform(self.params.p_taxable_stocks_weight_low, self.params.p_taxable_stocks_weight_high) if self.params.stocks else 0
                p_taxable_real_bonds_weight = uniform(self.params.p_taxable_real_bonds_weight_low, self.params.p_taxable_real_bonds_weight_high) \
                    if self.params.real_bonds else 0
                p_taxable_nominal_bonds_weight = uniform(self.params.p_taxable_nominal_bonds_weight_low, self.params.p_taxable_nominal_bonds_weight_high) \
                    if self.params.nominal_bonds else 0
                p_taxable_iid_bonds_weight = uniform(self.params.p_taxable_iid_bonds_weight_low, self.params.p_taxable_iid_bonds_weight_high) \
                    if self.params.iid_bonds  else 0
                p_taxable_bills_weight = uniform(self.params.p_taxable_bills_weight_low, self.params.p_taxable_bills_weight_high) if self.params.bills else 0
                total_weight = p_tax_free_weight + p_tax_deferred_weight + \
                    p_taxable_stocks_weight + p_taxable_real_bonds_weight + p_taxable_nominal_bonds_weight + p_taxable_iid_bonds_weight + p_taxable_bills_weight
                p_weighted = self.log_uniform(self.params.p_weighted_low, self.params.p_weighted_high)
                if total_weight == 0:
                    assert p_weighted == 0
                    total_weight = 1
                self.p_tax_free = self.log_uniform(self.params.p_tax_free_low, self.params.p_tax_free_high) + \
                    p_weighted * p_tax_free_weight / total_weight
                self.p_tax_deferred = self.log_uniform(self.params.p_tax_deferred_low, self.params.p_tax_deferred_high) + \
                    p_weighted * p_tax_deferred_weight / total_weight
                taxable_assets = AssetAllocation(fractional = False)
                if self.params.stocks:
                    taxable_assets.aa['stocks'] = self.log_uniform(self.params.p_taxable_stocks_low, self.params.p_taxable_stocks_high) + \
                        p_weighted * p_taxable_stocks_weight / total_weight
                if self.params.real_bonds:
                    taxable_assets.aa['real_bonds'] = self.log_uniform(self.params.p_taxable_real_bonds_low, self.params.p_taxable_real_bonds_high) + \
                        p_weighted * p_taxable_real_bonds_weight / total_weight
                if self.params.nominal_bonds:
                    taxable_assets.aa['nominal_bonds'] = self.log_uniform(self.params.p_taxable_nominal_bonds_low, self.params.p_taxable_nominal_bonds_high) + \
                        p_weighted * p_taxable_nominal_bonds_weight / total_weight
                if self.params.iid_bonds:
                    taxable_assets.aa['iid_bonds'] = self.log_uniform(self.params.p_taxable_iid_bonds_low, self.params.p_taxable_iid_bonds_high) + \
                        p_weighted * p_taxable_iid_bonds_weight / total_weight
                if self.params.bills:
                    taxable_assets.aa['bills'] = self.log_uniform(self.params.p_taxable_bills_low, self.params.p_taxable_bills_high) + \
                        p_weighted * p_taxable_bills_weight / total_weight
                self.p_taxable = sum(taxable_assets.aa.values())

                self._pre_calculate_wealth(growth_rate = 1.05) # Use a typical stock growth rate for determining expected consume range.
                ce_estimate_ok = self.params.consume_floor <= self.rough_ce_estimate_individual <= self.params.consume_ceiling
                if not ce_estimate_ok:
                    continue

                self._pre_calculate_wealth(growth_rate = 1) # By convention use no growth for determining guaranteed income bucket.

                preretirement_ok = self.raw_preretirement_income_wealth >= 0
                if not preretirement_ok:
                    continue

                try:
                    gi_fraction = self.retired_income_wealth_pretax / self.net_wealth_pretax
                except ZeroDivisionError:
                    gi_fraction = 1
                if not self.params.gi_fraction_low <= gi_fraction <= self.params.gi_fraction_high:
                    continue

                found = True
                break

            if found:
                break

        if not found:
            if not ce_estimate_ok:
                raise FinError('Expected consumption falls outside model training range.')
            elif not preretirement_ok:
                raise FinError('Insufficient pre-retirement wages and wealth to support pre-retirement consumption.')
            else:
                raise FinError('Guaranteed income falls outside model training range.')

        #print('wealth:', self.net_wealth_pretax, self.raw_preretirement_income_wealth, self.retired_income_wealth_pretax, self.p_wealth)

        taxable_basis = AssetAllocation(fractional = False)
        if self.params.stocks:
            assert not self.params.p_taxable_stocks_basis or not self.params.p_taxable_stocks_basis_fraction_high
            taxable_basis.aa['stocks'] = self.params.p_taxable_stocks_basis + \
                uniform(self.params.p_taxable_stocks_basis_fraction_low, self.params.p_taxable_stocks_basis_fraction_high) * taxable_assets.aa['stocks']
        if self.params.real_bonds:
            assert not self.params.p_taxable_real_bonds_basis or not self.params.p_taxable_real_bonds_basis_fraction_high
            taxable_basis.aa['real_bonds'] = self.params.p_taxable_real_bonds_basis + \
                uniform(self.params.p_taxable_real_bonds_basis_fraction_low, self.params.p_taxable_real_bonds_basis_fraction_high) * taxable_assets.aa['real_bonds']
        if self.params.nominal_bonds:
            assert not self.params.p_taxable_nominal_bonds_basis or not self.params.p_taxable_nominal_bonds_basis_fraction_high
            taxable_basis.aa['nominal_bonds'] = self.params.p_taxable_nominal_bonds_basis + \
                uniform(self.params.p_taxable_nominal_bonds_basis_fraction_low, self.params.p_taxable_nominal_bonds_basis_fraction_high) * \
                taxable_assets.aa['nominal_bonds']
        if self.params.iid_bonds:
            assert not self.params.p_taxable_iid_bonds_basis or not self.params.p_taxable_iid_bonds_basis_fraction_high
            taxable_basis.aa['iid_bonds'] = self.params.p_taxable_iid_bonds_basis + \
                uniform(self.params.p_taxable_iid_bonds_basis_fraction_low, self.params.p_taxable_iid_bonds_basis_fraction_high) * taxable_assets.aa['iid_bonds']
        if self.params.bills:
            assert not self.params.p_taxable_bills_basis or not self.params.p_taxable_bills_basis_fraction_high
            taxable_basis.aa['bills'] = self.params.p_taxable_bills_basis + \
                uniform(self.params.p_taxable_bills_basis_fraction_low, self.params.p_taxable_bills_basis_fraction_high) * taxable_assets.aa['bills']
        self.taxes = Taxes(self.params, taxable_assets, taxable_basis)

        self._pre_calculate()

        self.set_reward_level()

        self.prev_asset_allocation = None
        self.prev_taxable_assets = taxable_assets
        self.prev_real_spias_rate = None
        self.prev_nominal_spias_rate = None
        self.prev_consume_rate = None
        self.prev_reward = None

        if self.params.verbose:
            print()
            print('Age add:', self.life_table.age_add)
            print('Guaranteed income fraction:', gi_fraction)
            self.render()

        return self._observe()

    def set_reward_level(self):

        # Taking advantage of iso-elasticity, generalizability will be better if rewards are independent of initial portfolio size.
        #
        # Scale returned rewards.
        # This is helpful for PPO, which clips the value function advantage at 10.0.
        # A rough estimate of a minimal consumption level is 0.3 times a consumption estimate.
        # Having rewards for a minimal consumption level of -0.2 should ensure rewards rarely exceed -10.0, allowing the value function to converge quickly.
        consumption_estimate = self.ce_estimate_individual
        if consumption_estimate == 0:
            self.warn('Using a consumption scale that is incompatible with the default consumption scale.')
            consumption_estimate = 1
        self.consume_scale = consumption_estimate
        self.utility = Utility(self.gamma, 0.3 * consumption_estimate)
        #_, self.reward_expect = self.raw_reward(consumption_estimate)
        #_, self.reward_zero_point = self.raw_reward(self.params.reward_zero_point_factor * consumption_estimate)
        self.reward_scale = 0.2

    def encode_direct_action(self, consume_fraction, *, real_spias_fraction = None, nominal_spias_fraction = None,
        real_bonds_duration = None, nominal_bonds_duration = None, **kwargs):

        return (consume_fraction, real_spias_fraction, nominal_spias_fraction, AssetAllocation(**kwargs), real_bonds_duration, nominal_bonds_duration)

    def decode_action(self, action):

        action = action.reshape((-1, )) # Work around spinup returning a single element list of actions.

        if isnan(action[0]):
            assert False, 'Action is nan.' # Detect bug in code interacting with model before it messes things up.

        if not self.params.action_space_unbounded:
            # Spinup SAC, and possibly other algorithms return bogus action values like -1.0000002 and 1.0000001. Possibly a bug in tf.tanh.
            clipped_action = np.clip(action, -1, 1)
            assert np.allclose(action, clipped_action, rtol = 0, atol= 3e-7), 'Out of range action: ' + str(action)
            action = clipped_action

        try:
            action = action.tolist() # De-numpify if required.
        except AttributeError:
            pass

        consume_action, *action = action
        if self.params.real_spias or self.params.nominal_spias:
            spias_action, *action = action
            if self.params.real_spias and self.params.nominal_spias:
                real_spias_action, *action = action
        if self.params.stocks:
            stocks_action, *action = action
        if self.params.real_bonds:
            real_bonds_action, *action = action
            if not self.params.real_bonds_duration or self.params.real_bonds_duration_action_force:
                real_bonds_duration_action, *action = action
        if self.params.nominal_bonds:
            nominal_bonds_action, *action = action
            if not self.params.nominal_bonds_duration or self.params.nominal_bonds_duration_action_force:
                nominal_bonds_duration_action, *action = action
        if self.params.iid_bonds:
            iid_bonds_action, *action = action
        if self.params.bills:
            bills_action, *action = action
        assert not action

        def safe_atanh(x):
            try:
                return atanh(x)
            except ValueError:
                assert abs(x) == 1, 'Invalid value to atanh.'
                return copysign(10, x) # Change to 20 if using float64.

        if self.params.action_space_unbounded:
            consume_action = tanh(consume_action / 5)
                # Scaling back initial volatility of consume_action is observed to improve run to run mean and reduce standard deviation of certainty equivalent.
            if self.spias_ever:
                spias_action = tanh(spias_action / 2)
                    # Decreasing initial volatility of spias_action is observed to improve run to run mean certainty equivalent (gamma=6).
                    # Increasing initial volatility of spias_action is observed to improve run to run mean certainty equivalent (gamma=1.5).
                    #
                    # real spias, p_tax_free=2e6, age_start=65, life_expectancy_add=3, bucket-le ensemble results:
                    #                gamma=1.5   gamma=6
                    # tanh(action)     134304    106032
                    # tanh(action/2)   132693    112684
                    # tanh(action/5)   128307    110570
                if self.params.real_spias and self.params.nominal_spias:
                    real_spias_action = tanh(real_spias_action)
            if self.params.real_bonds and not self.params.real_bonds_duration:
                real_bonds_duration_action = tanh(real_bonds_duration_action)
            if self.params.nominal_bonds and not self.params.nominal_bonds_duration:
                nominal_bonds_duration_action = tanh(nominal_bonds_duration_action)
        else:
            if self.params_stocks:
                stocks_action = safe_atanh(stocks_action)
            if self.params.real_bonds:
                real_bonds_action = safe_atanh(real_bonds_action)
            if self.params.nominal_bonds:
                nominal_bonds_action = safe_atanh(nominal_bonds_action)
            if self.params.iid_bonds:
                iid_bonds_action = safe_atanh(iid_bonds_action)
            if self.params.bills:
                bills_action = safe_atanh(bills_action)

        consume_action = (consume_action + 1) / 2
        # Define a consume floor and consume ceiling outside of which we won't consume.
        # The mid-point acts as a hint as to the initial consumption values to try.
        consume_estimate = self.consume_net_wealth_estimate
        consume_floor = 0.1 * consume_estimate
        consume_ceil = 1.9 * consume_estimate
        consume_fraction = consume_floor + (consume_ceil - consume_floor) * consume_action
        try:
            consume_fraction *= self.net_wealth / self.p_plus_income
        except ZeroDivisionError:
            consume_fraction = float('inf')

        consume_fraction = max(1e-6, min(consume_fraction, 1 / self.params.time_period))
            # Don't allow consume_fraction of zero as have problems with -inf utility.

        if self.spias:

            if self.spias_required:
                spias_action = 1
            elif self.params.spias_partial:
                spias_action = (spias_action + 1) / 2
            else:
                spias_action = 1 if spias_action > 0 else 0

            # Try and make it easy to learn the optimal amount of guaranteed income,
            # so things function well with differing current amounts of guaranteed income.
            try:
                current_spias_fraction_estimate = self.retired_income_wealth / self.net_wealth
            except ZeroDivisionError:
                current_spias_fraction_estimate = 1
            current_spias_fraction_estimate = max(0, min(current_spias_fraction_estimate, 1))
            if spias_action - current_spias_fraction_estimate < self.params.spias_min_purchase_fraction:
                spias_fraction = 0
            elif spias_action > 1 - self.params.spias_min_purchase_fraction:
                spias_fraction = 1
            else:
                try:
                    spias_fraction = (spias_action - current_spias_fraction_estimate) * self.net_wealth / self.p_plus_income
                except ZeroDivisionError:
                    spias_fraction = 0
                spias_fraction = max(0, min(spias_fraction, 1))

            real_spias_fraction = spias_fraction if self.params.real_spias else 0
            if self.params.real_spias and self.params.nominal_spias:
                real_spias_fraction *= (real_spias_action + 1) / 2
            nominal_spias_fraction = spias_fraction - real_spias_fraction

        if not self.params.real_spias or not self.spias:
            real_spias_fraction = None
        if not self.params.nominal_spias or not self.spias:
            nominal_spias_fraction = None

        # Softmax the asset alocations when guaranteed_income is zero.
        maximum = max(
            stocks_action if self.params.stocks else float('-inf'),
            real_bonds_action if self.params.real_bonds else float('-inf'),
            nominal_bonds_action if self.params.nominal_bonds else float('-inf'),
            iid_bonds_action if self.params.iid_bonds else float('-inf'),
            bills_action if self.params.bills else float('-inf'),
        )
        stocks_action = exp(stocks_action - maximum) if self.params.stocks else 0
        real_bonds_action = exp(real_bonds_action - maximum) if self.params.real_bonds else 0
        nominal_bonds_action = exp(nominal_bonds_action - maximum) if self.params.nominal_bonds else 0
        iid_bonds_action = exp(iid_bonds_action - maximum) if self.params.iid_bonds else 0
        bills_action = exp(bills_action - maximum) if self.params.bills else 0
        total = stocks_action + real_bonds_action + nominal_bonds_action + iid_bonds_action + bills_action
        stocks_action /= total
        real_bonds_action /= total
        nominal_bonds_action /= total
        iid_bonds_action /= total
        bills_action /= total

        # Fit to curve.
        #
        # It is too much to expect optimization to compute the precise asset allocation surface.
        # Instead we provide guidelines as to what the surface might look like, and allow optimization to tune within those guidelines.
        #
        # If we just did stocks = stocks_action, there would be little incentive to increase stocks from say 98% to 100% in the region
        # where the protfolio is small, which is precisely when this is required.
        #
        # In the absense of guaranteed income, for stocks, other assets, and risk free, using CRRA utility according to Merton's portfolio problem we expect:
        #     stocks_fraction = const1
        # The above should hold when guaranteed income is zero, or the investment portfolio approaches infinity.
        # This suggests a more general equation of the form:
        #     stocks_fraction = const1 + const2 * guaranteed_income_wealth / investment_wealth
        # might be helpful to determining the stock allocation.
        #
        # Empirically for a single data value, stocks, we get better results training a single varaible, stocks_action,
        # than trying to train two variables, stocks_action and stocks_curvature_action for one data value.
        #
        # For stocks and iid bonds using Merton's portfolio solution and dynamic programming for 16e3 of guaranteed income, female age 65 SSA+3, we have:
        # stocks:
        #    p  gamma=3   gamma=6  wealth_ratio
        # 2.5e5  >100%      94%        1.57
        #   5e5  >100%      79%        0.78
        #   1e6    99%      70%        0.39
        #   2e6    90%      64%        0.19
        #   inf    77%      54%         -
        # From which we can derive the following estimates of stocks_curvature:
        #    p  gamma=3   gamma=6
        # 2.5e5     -       0.3
        #   5e5     -       0.3
        #   1e6    0.6      0.4
        #   2e6    0.7      0.5
        # We thus use a curvature coefficient of 0.5, and allow stocks to depend on the observation to fine tune things from there.
        stocks_curvature = real_bonds_curvature = nominal_bonds_curvature = iid_bonds_curvature = 0.5
        alloc = 1
        stocks = max(0, min(stocks_action + stocks_curvature * self.wealth_ratio + self.params.rl_stocks_bias, alloc)) if self.params.stocks else 0
        alloc -= stocks
        real_bonds = max(0, min(real_bonds_action + real_bonds_curvature * self.wealth_ratio, alloc)) if self.params.real_bonds else 0
        alloc -= real_bonds
        nominal_bonds = max(0, min(nominal_bonds_action + nominal_bonds_curvature * self.wealth_ratio, alloc)) if self.params.nominal_bonds else 0
        alloc -= nominal_bonds
        iid_bonds = max(0, min(iid_bonds_action + iid_bonds_curvature * self.wealth_ratio, alloc)) if self.params.iid_bonds else 0
        alloc -= iid_bonds
        if self.params.bills:
            bills = alloc
        elif self.params.iid_bonds:
            iid_bonds += alloc
        elif self.params.nominal_bonds:
            nominal_bonds += alloc
        elif self.params.real_bonds:
            real_bonds += alloc
        else:
            stocks += alloc

        asset_allocation = AssetAllocation(fractional = False)
        if self.params.stocks:
            asset_allocation.aa['stocks'] = stocks
        if self.params.real_bonds:
            asset_allocation.aa['real_bonds'] = real_bonds
        if self.params.nominal_bonds:
            asset_allocation.aa['nominal_bonds'] = nominal_bonds
        if self.params.iid_bonds:
            asset_allocation.aa['iid_bonds'] = iid_bonds
        if self.params.bills:
            asset_allocation.aa['bills'] = bills

        buckets = 100 # Quantize duration so that bonds.py:_log_p() _sr_cache can be utilized when sample returns.

        real_bonds_duration = self.params.real_bonds_duration or \
            self.params.time_period + (self.params.real_bonds_duration_max - self.params.time_period) * \
            round((real_bonds_duration_action + 1) / 2 * buckets) / buckets \
            if self.params.real_bonds else None

        nominal_bonds_duration = self.params.nominal_bonds_duration or \
            self.params.time_period + (self.params.nominal_bonds_duration_max - self.params.time_period) * \
            round((nominal_bonds_duration_action + 1) / 2 * buckets) / buckets \
            if self.params.nominal_bonds else None

        return (consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration)

    def raw_reward(self, consume_rate):

        if self.couple:
            reward_consume = consume_rate / (1 + self.params.consume_additional)
            reward_weight = 2 * self.params.time_period
        else:
            reward_consume = consume_rate
            reward_weight = self.alive_single[self.episode_length] * self.params.time_period
        reward_value = self.utility.utility(reward_consume)

        return reward_weight, reward_consume, reward_value

    def spend(self, consume_fraction, real_spias_fraction = 0, nominal_spias_fraction = 0):

        # Sanity check.
        consume_fraction_period = consume_fraction * self.params.time_period
        assert 0 <= consume_fraction_period <= 1

        p = self.p_plus_income
        if p < 0:
            self.warn('Portfolio became negative')
            p = 0
        if self.age < self.age_retirement:
            consume = self.consume_preretirement * self.params.time_period
        else:
            #consume_annual = consume_fraction * p
            consume = consume_fraction_period * p
        p -= consume
        if p < 0:
            self.warn('Consumption made portfolio negative')
            p = 0

        p_taxable = self.p_taxable + (p - self.p_sum())
        p_tax_deferred = self.p_tax_deferred + min(p_taxable, 0)
        # Required Minimum Distributions (RMDs) not considered. Would need separate p_tax_deferred for each spouse.
        p_tax_free = self.p_tax_free + min(p_tax_deferred, 0)
        p_taxable = max(p_taxable, 0)
        p_tax_deferred = max(p_tax_deferred, 0)
        if p_tax_free < 0:
            assert p_tax_free > min(-1e-14 * self.p_plus_income, -1e-11), '{} {}'.format(p_tax_free, self.p_plus_income)
            p_tax_free = 0
        delta_p_tax_deferred = self.p_tax_deferred - p_tax_deferred

        retirement_contribution = contribution_limit(self.income_preretirement, self.age, self.have_401k, self.params.time_period) \
            + contribution_limit(self.income_preretirement2, self.age2, self.have_401k2, self.params.time_period)
        retirement_contribution = min(retirement_contribution, p_taxable)
        p_taxable -= retirement_contribution
        p_tax_deferred += retirement_contribution

        if real_spias_fraction != None:
            real_spias_fraction *= self.params.time_period
        else:
            real_spias_fraction = 0
        if nominal_spias_fraction != None:
            nominal_spias_fraction *= self.params.time_period
        else:
            nominal_spias_fraction = 0
        total = real_spias_fraction + nominal_spias_fraction
        if total > 1:
            real_spias_fraction /= total
            nominal_spias_fraction /= total
        real_spias = real_spias_fraction * p
        nominal_spias = nominal_spias_fraction * p
        real_tax_free_spias = min(real_spias, p_tax_free)
        p_tax_free -= real_tax_free_spias
        real_spias -= real_tax_free_spias
        nominal_tax_free_spias = min(nominal_spias, p_tax_free)
        p_tax_free -= nominal_tax_free_spias
        nominal_spias -= nominal_tax_free_spias
        real_tax_deferred_spias = min(real_spias, p_tax_deferred)
        p_tax_deferred -= real_tax_deferred_spias
        real_taxable_spias = real_spias - real_tax_deferred_spias
        nominal_tax_deferred_spias = min(nominal_spias, p_tax_deferred)
        p_tax_deferred -= nominal_tax_deferred_spias
        nominal_taxable_spias = nominal_spias - nominal_tax_deferred_spias

        regular_income = self.gi_sum(source = ('tax_deferred', 'taxable')) - retirement_contribution + delta_p_tax_deferred
        if regular_income < 0:
            if regular_income < -1e-12 * (self.gi_sum(source = ('tax_deferred', 'taxable')) + self.p_tax_deferred):
                self.warn('Negative regular income:', regular_income)
                    # Possible if taxable real SPIA non-taxable amount exceeds payout due to deflation.
            regular_income = 0
        social_security = self.gi_sum(type = 'social_security')
        social_security = min(regular_income, social_security)

        taxable_spias = real_taxable_spias + nominal_taxable_spias
        if taxable_spias > 0:
            # Ensure leave enough taxable assets to cover any taxes due.
            max_capital_gains = self.taxes.unrealized_gains()
            if max_capital_gains > 0:
                max_capital_gains_taxes = sum(self.taxes.calculate_taxes(regular_income, social_security, max_capital_gains, not self.couple)) \
                    - sum(self.taxes.calculate_taxes(regular_income, social_security, 0, not self.couple))
                new_taxable_spias = min(taxable_spias, max(0, p_taxable - max_capital_gains_taxes))
                real_taxable_spias *= new_taxable_spias / taxable_spias
                nominal_taxable_spias *= new_taxable_spias / taxable_spias

        p_taxable -= real_taxable_spias + nominal_taxable_spias
        if p_taxable < 0:
            assert p_taxable / self.p_plus_income > -1e-15
            p_taxable = 0

        return p_tax_free, p_tax_deferred, p_taxable, regular_income, social_security, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias

    def interpret_spending(self, consume_fraction, asset_allocation, *, real_spias_fraction = 0, nominal_spias_fraction = 0,
        real_bonds_duration = None, nominal_bonds_duration = None):

        p_tax_free, p_tax_deferred, p_taxable, regular_income, social_security, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias = \
            self.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)

        real_spias_purchase = real_tax_free_spias + real_tax_deferred_spias + real_taxable_spias
        nominal_spias_purchase = nominal_tax_free_spias + nominal_tax_deferred_spias + nominal_taxable_spias
        return {
            'consume': consume / self.params.time_period,
            'asset_allocation': asset_allocation,
            'retirement_contribution': retirement_contribution / self.params.time_period \
                if self.income_preretirement_years > 0 or self.income_preretirement_years2 > 0 else None,
            'real_spias_purchase': real_spias_purchase if self.params.real_spias and self.spias else None,
            'nominal_spias_purchase': nominal_spias_purchase if self.params.nominal_spias and self.spias else None,
            'pv_spias_purchase': real_spias_purchase + nominal_spias_purchase - (real_tax_deferred_spias + nominal_tax_deferred_spias) * self.regular_tax_rate,
            'real_bonds_duration': real_bonds_duration,
            'nominal_bonds_duration': nominal_bonds_duration,
        }

    def interpret_action(self, action):

        if self.direct_action:
            decoded_action = action
        elif action is None:
            decoded_action = None
        else:
            decoded_action = self.decode_action(action)
        policified_action = policy(self, decoded_action)
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = policified_action
        return self.interpret_spending(consume_fraction, asset_allocation, real_spias_fraction = real_spias_fraction, nominal_spias_fraction = nominal_spias_fraction,
            real_bonds_duration = real_bonds_duration, nominal_bonds_duration = nominal_bonds_duration)

    def add_spias(self, inflation_adjustment, tax_free_spias, tax_deferred_spias, taxable_spias):

        owner = 'self' if self.couple or not self.only_alive2 else 'spouse'
        age = self.age if owner == 'self' else self.age2
        start = age + self.params.time_period
        payout_fraction = 1 / (1 + self.params.consume_additional)
        if tax_free_spias > 0:
            self.add_db(owner = owner, start = start, premium = tax_free_spias, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'tax_free')
        if tax_deferred_spias > 0:
            self.add_db(owner = owner, start = start, premium = tax_deferred_spias, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'tax_deferred')
        if taxable_spias > 0:
            exclusion_period = ceil(self.life_expectancy_both[self.episode_length] + self.life_expectancy_one[self.episode_length])
                # Highly imperfect, but total exclusion amount will be correct.
            if inflation_adjustment in ('cpi', 0):
                exclusion_amount = taxable_spias / exclusion_period
            else:
                exclusion_amount = taxable_spias * inflation_adjustment / ((1 + inflation_adjustment) ** exclusion_period - 1)
            self.add_db(owner = owner, start = start, premium = taxable_spias, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'taxable', exclusion_period = exclusion_period, exclusion_amount = exclusion_amount)

    def allocate_aa(self, p_tax_free, p_tax_deferred, p_taxable, asset_allocation):

        p = p_tax_free + p_tax_deferred + p_taxable
        tax_free_remaining = p_tax_free
        taxable_remaining = p_taxable

        tax_efficient_order = ('stocks', 'bills', 'iid_bonds', 'nominal_bonds', 'real_bonds')
        tax_inefficient_order = reversed(tax_efficient_order)

        tax_free = AssetAllocation(fractional = False)
        for ac in tax_inefficient_order:
            if ac in asset_allocation.aa:
                alloc = min(p * asset_allocation.aa[ac], tax_free_remaining)
                tax_free.aa[ac] = alloc
                tax_free_remaining = max(tax_free_remaining - alloc, 0)

        taxable = AssetAllocation(fractional = False)
        for ac in tax_efficient_order:
            if ac in asset_allocation.aa:
                alloc = min(p * asset_allocation.aa[ac], taxable_remaining)
                taxable.aa[ac] = alloc
                taxable_remaining = max(taxable_remaining - alloc, 0)

        tax_deferred = AssetAllocation(fractional = False)
        for ac in tax_efficient_order:
            if ac in asset_allocation.aa:
                tax_deferred.aa[ac] = max(p * asset_allocation.aa[ac] - tax_free.aa[ac] - taxable.aa[ac], 0)

        return tax_free, tax_deferred, taxable

    def step(self, action):

        if not self._init_done:
            self._init()
            self.reset()

        if self.params.reproduce_episode != None:
            self._reproducable_seed(self.params.reproduce_episode, self.episode_length, 1)

        if self.direct_action:
            decoded_action = action
        elif action is None:
            decoded_action = None
        else:
            decoded_action = self.decode_action(action)
        policified_action = policy(self, decoded_action)
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = policified_action

        p_tax_free, p_tax_deferred, p_taxable, regular_income, social_security, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias = \
            self.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)
        consume_rate = consume / self.params.time_period
        real_spias_rate = (real_tax_free_spias + real_tax_deferred_spias + real_taxable_spias) / self.params.time_period
        nominal_spias_rate = (nominal_tax_free_spias + nominal_tax_deferred_spias + nominal_taxable_spias) / self.params.time_period

        if real_spias_rate > 0:
            self.add_spias('cpi', real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias)

        if nominal_spias_rate > 0:
            self.add_spias(self.params.nominal_spias_adjust, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias)

        tax_free_assets, tax_deferred_assets, taxable_assets = self.allocate_aa(p_tax_free, p_tax_deferred, p_taxable, asset_allocation)

        inflation = self.bonds.inflation.inflation()
        self.cpi *= inflation

        p_tax_free = 0
        p_tax_deferred = 0
        p_taxable = 0
        for ac in asset_allocation.aa:
            if ac == 'stocks':
                ret = self.stocks.sample()
                dividend_yield = self.params.dividend_yield_stocks
                qualified_dividends = self.params.qualified_dividends_stocks
            else:
                dividend_yield = self.params.dividend_yield_bonds
                qualified_dividends = self.params.qualified_dividends_bonds
                if ac == 'real_bonds':
                    ret = self.bonds.real.sample(real_bonds_duration)
                elif ac == 'nominal_bonds':
                    ret = self.bonds.nominal.sample(nominal_bonds_duration)
                elif ac == 'iid_bonds':
                    ret = self.iid_bonds.sample()
                elif ac == 'bills':
                    ret = self.bills.sample()
                else:
                    assert False
            p_tax_free += tax_free_assets.aa[ac] * ret
            p_tax_deferred += tax_deferred_assets.aa[ac] * ret
            new_taxable = taxable_assets.aa[ac] * ret
            p_taxable += new_taxable
            taxable_buy_sell = taxable_assets.aa[ac] - self.prev_taxable_assets.aa[ac]
            self.taxes.buy_sell(ac, taxable_buy_sell, new_taxable, ret, dividend_yield, qualified_dividends)
            taxable_assets.aa[ac] *= ret

        self.p_tax_free = p_tax_free
        self.p_tax_deferred = p_tax_deferred
        self.p_taxable = p_taxable

        self.taxes_due += self.taxes.tax(regular_income, social_security, not self.couple, inflation) - self.taxes_paid
        if self.age < self.age_retirement:
            # Forgive taxes due that can't immediately be repaid pre-retirement.
            # Otherwise if have no investment assets at retirement (consumption greater than income) we would be expected to pay the
            # accumulated taxes which could be substantially more than the guaranteed income.
            # Instead we forgive these amounts, the same way we forgive in preretirement when consumption would make investments negative.
            ability_to_pay = self.p_sum()
            self.taxes_due = min(self.taxes_due, ability_to_pay)

        if self.age < self.age_retirement:
            self.reward_weight = 0
            self.reward_consume = 0
            self.reward_value = 0
            reward = 0
        else:
            self.reward_weight, self.reward_consume, self.reward_value = self.raw_reward(consume_rate)
            reward_unclipped = self.reward_weight * self.reward_scale * self.reward_value
            if isinf(reward_unclipped):
                self.warn('Infinite reward')
            elif not - self.params.reward_warn <= reward_unclipped <= self.params.reward_warn:
                self.warn('Extreme reward - age, consume, reward:', self.age, consume_rate, reward_unclipped)
            reward = min(max(reward_unclipped, - self.params.reward_clip), self.params.reward_clip)
            if reward != reward_unclipped:
                self.warn('Reward clipped - age, consume, reward:', self.age, consume_rate, reward_unclipped)

        alive0 = self.alive_single[self.episode_length]
        if alive0 == None:
            alive0 = 1
        alive1 = self.alive_single[self.episode_length + 1]
        if alive1 == None:
            alive1 = 1
        self.estate_weight = alive0 - alive1
        self.estate_value = max(0, self.p_sum() - self.taxes_due) # Ignore future taxation of p_tax_deferred; depends upon heirs tax bracket.

        self._step()
        self._step_bonds()

        done = self.alive_single[self.episode_length] == 0
        if done:
            observation = np.repeat(np.nan, self.observation_space.shape)
        else:
            self._pre_calculate()
            observation = self._observe()
        info = {}

        self.prev_asset_allocation = asset_allocation
        self.prev_taxable_assets = taxable_assets
        self.prev_real_spias_rate = real_spias_rate
        self.prev_nominal_spias_rate = nominal_spias_rate
        self.prev_consume_rate = consume_rate
        self.prev_reward = reward

        # Variables used by policy decison rules:
        self.prev_ret = ret
        self.prev_inflation = inflation

        if self.params.verbose:
            self.render()

        return observation, reward, done, info

    def _step(self, steps = 1, force_family_unit = False, forced_family_unit_couple = True):

        self.age += steps
        self.age2 += steps
        self.life_table.age = self.age # Hack. (Probably not needed here as set_age() doesn't result in a life table recompute).
        self.life_table_preretirement.age = self.age
        try:
            self.life_table2.age = self.age2
            self.life_table2_preretirement.age = self.age2
        except AttributeError:
            pass

        self.preretirement_years = max(0, self.preretirement_years - steps)
        self.income_preretirement_years = max(0, self.income_preretirement_years - steps)
        self.income_preretirement_years2 = max(0, self.income_preretirement_years2 - steps)

        force_to_single = force_family_unit and not forced_family_unit_couple
        keep_as_couple = force_family_unit and forced_family_unit_couple
        couple_became_single = self.couple and (self.alive_single[self.episode_length + steps] != None or force_to_single) and not keep_as_couple
        if couple_became_single:

            if self.only_alive2:
                self.income_preretirement_years = 0
            else:
                self.income_preretirement_years2 = 0
            if self.params.couple_death_preretirement_consume == 'consume_additional':
                self.consume_preretirement /= 1 + self.params.consume_additional
            elif self.params.couple_death_preretirement_consume == 'pro_rata':
                try:
                    ratio = (self.start_income_preretirement2 if self.only_alive2 else self.start_income_preretirement) / \
                        (self.start_income_preretirement + self.start_income_preretirement2)
                except ZeroDivisionError:
                    ratio = 1
                self.consume_preretirement *= ratio
            elif self.params.couple_death_preretirement_consume == 'none':
                pass
            else:
                assert False

            self.retirement_expectancy_both = [0] * len(self.retirement_expectancy_both)
            self.retirement_expectancy_one = self.retirement_expectancy_single

        for _ in range(steps):
            income_fluctuation = lognormvariate(self.params.income_preretirement_mu * self.params.time_period,
                self.params.income_preretirement_sigma * sqrt(self.params.time_period))
            if self.income_preretirement_years > 0:
                self.income_preretirement *= income_fluctuation
            if self.income_preretirement_years2 > 0:
                if self.params.income_preretirement_concordant:
                    self.income_preretirement2 *= income_fluctuation
                else:
                    self.income_preretirement2 *= lognormvariate(self.params.income_preretirement_mu2 * self.params.time_period,
                        self.params.income_preretirement_sigma2 * sqrt(self.params.time_period))
        if not self.income_preretirement_years > 0:
            self.income_preretirement = 0
        if not self.income_preretirement_years2 > 0:
            self.income_preretirement2 = 0

        for db in self.defined_benefits.values():
            db.step(steps)

        self.episode_length += steps
        self.env_timesteps += steps
        if self.couple:
            self.env_couple_timesteps += steps
        else:
            self.env_single_timesteps += steps

        self.couple = self.alive_single[self.episode_length] == None and not force_to_single or keep_as_couple

        self.date = self.date_start + timedelta(days = self.episode_length * self.params.time_period * 365.25)

    def _reproducable_seed(self, episode, episode_length, substep):

        seed(episode * 1000000 + episode_length * 1000 + substep, version = 2)

    def _step_bonds(self):

        if self.params.reproduce_episode != None:
            self._reproducable_seed(self.params.reproduce_episode, self.episode_length, 2)

        self.bonds_stepper.step()

    def goto(self, step = None, age = None, real_oup_x = None, inflation_oup_x = None, p_tax_free = None, p_tax_deferred = None, p_taxable_assets = None,
             p_taxable_basis = None, taxes_due = None, force_family_unit = False, forced_family_unit_couple = True):
        '''Goto a reproducable time step. Useful for benchmarking and plotting surfaces.'''

        assert (step == None) != (age == None)

        if step != None:
            age = self.age_start + step / self.params.time_period

        if age < self.age or force_family_unit and not self.couple and forced_family_unit_couple:
            self.reset()
            assert not force_family_unit or self.couple or not forced_family_unit_couple

        step = round((age - self.age) / self.params.time_period)
        assert step >= 0

        if step != 0:
            self._step(step, force_family_unit, forced_family_unit_couple)

        assert (real_oup_x == None) == (inflation_oup_x == None)

        if real_oup_x != None:
            self.bonds.real.oup.next_x = real_oup_x
            assert self.bonds.inflation.inflation_a == self.bonds.inflation.bond_a and self.bonds.inflation.inflation_sigma == self.bonds.inflation.bond_sigma
            self.bonds.inflation.oup.next_x = inflation_oup_x
            self.bonds.inflation.inflation_oup.next_x = inflation_oup_x
            self._step_bonds()

        if p_tax_free != None: self.p_tax_free = p_tax_free
        if p_tax_deferred != None: self.p_tax_deferred = p_tax_deferred
        if p_taxable_assets == None:
            assert p_taxable_basis == None
        else:
            assert p_taxable_basis != None
            self.p_taxable = sum(p_taxable_assets.aa.values())
            self.taxes = Taxes(self.params, p_taxable_assets, p_taxable_basis)
        if taxes_due != None:
            self.taxes_due = 0

        self._pre_calculate()
        return self._observe()

    def set_reproduce_episode(self, episode):

        self.params.reproduce_episode = episode

    def render(self, mode = 'human'):

        pv_income_preretirement = self.income_preretirement * self.income_preretirement_years
        pv_income_preretirement2 = self.income_preretirement2 * self.income_preretirement_years2
        pv_consume_preretirement = self.consume_preretirement * self.preretirement_years

        print(self.age, self.p_tax_free, self.p_tax_deferred, self.p_taxable, pv_income_preretirement, pv_income_preretirement2, pv_consume_preretirement)
        print('    ', self.prev_asset_allocation, self.prev_consume_rate, self.prev_real_spias_rate, self.prev_nominal_spias_rate, self.prev_reward)

        for db in self.defined_benefits.values():
            db.render()

    def seed(self, seed=None):

        return

    def _pre_calculate_wealth(self, growth_rate = 1.0):
        # By default use a conservative growth rate for determining the present value of wealth.
        # Also reflects the fact that we won't get to consume all wealth before we are expected to die.
        # Leave it to the AI to map to actual value.

        self.pv_preretirement_income = {'tax_free': 0, 'tax_deferred': 0, 'taxable': 0}
        self.pv_retired_income = {'tax_free': 0, 'tax_deferred': 0, 'taxable': 0}
        self.pv_social_security = 0
        for db in self.defined_benefits.values():
            if self.preretirement_years > 0:
                pv = db.pv(retired = False)
                self.pv_preretirement_income[db.type_of_funds] += pv
                if db.type == 'social_security':
                    self.pv_social_security += pv
            pv = db.pv(preretirement = False)
            self.pv_retired_income[db.type_of_funds] += pv
            if db.type == 'social_security':
                self.pv_social_security += pv
        source = 'taxable' if self.params.income_preretirement_taxable else 'tax_free'
        if self.preretirement_years > 0:
            self.pv_preretirement_income[source] += self.income_preretirement * min(self.income_preretirement_years, self.preretirement_years)
            self.pv_preretirement_income[source] += self.income_preretirement2 * min(self.income_preretirement_years2, self.preretirement_years)
            self.pv_preretirement_income['tax_free'] -= self.consume_preretirement * self.preretirement_years
        self.pv_retired_income[source] += self.income_preretirement * max(0, self.income_preretirement_years - self.preretirement_years)
        self.pv_retired_income[source] += self.income_preretirement2 * max(0, self.income_preretirement_years2 - self.preretirement_years)

        self.retired_income_wealth_pretax = sum(self.pv_retired_income.values())

        if self.couple:
            self.years_retired = self.retirement_expectancy_both[self.episode_length] + \
                self.retirement_expectancy_one[self.episode_length] / (1 + self.params.consume_additional)
            self.couple_weight = 2
        else:
            self.years_retired = self.retirement_expectancy_one[self.episode_length]
            self.couple_weight = 1

        if growth_rate != 1:
            preretirement_growth = growth_rate ** self.preretirement_years
            retirement_growth = 1 if growth_rate == 1 else self.years_retired * (1 - 1 / growth_rate) / (1 - 1 / growth_rate ** self.years_retired)
            total_growth = preretirement_growth * retirement_growth
        else:
            total_growth = 1

        self.wealth_tax_free = self.p_tax_free * total_growth
        self.wealth_tax_deferred = self.p_tax_deferred * total_growth
        self.wealth_taxable = self.p_taxable * total_growth

        if not self.params.tax and self.params.income_aggregate:
            self.pv_retired_income = {'tax_free': self.retired_income_wealth_pretax, 'tax_deferred': 0, 'taxable': 0} # Results in better training.
            self.wealth_tax_free += self.wealth_tax_deferred + self.wealth_taxable
            self.wealth_tax_deferred = 0
            self.wealth_taxable = 0

        self.p_wealth = self.wealth_tax_free + self.wealth_tax_deferred + self.wealth_taxable
        self.raw_preretirement_income_wealth = sum(self.pv_preretirement_income.values()) # Should factor in investment growth.
        self.net_wealth_pretax = self.retired_income_wealth_pretax + max(0, self.p_wealth + self.raw_preretirement_income_wealth - self.taxes_due * total_growth)

        self.rough_ce_estimate_individual = self.net_wealth_pretax / self.years_retired / self.couple_weight

    def _pre_calculate(self):

        self._pre_calculate_wealth()

        p_basis, cg_carry = self.taxes.observe()
        assert p_basis >= 0 and cg_carry <= 0
        self.taxable_basis = p_basis - cg_carry

        average_asset_years = self.preretirement_years + self.years_retired / 2
        total_years = self.preretirement_years + self.years_retired

        pv_regular_income = self.pv_preretirement_income['tax_deferred'] + self.pv_preretirement_income['taxable'] + \
            self.pv_retired_income['tax_deferred'] + self.pv_retired_income['taxable'] + self.wealth_tax_deferred
        pv_social_security = self.pv_social_security
        pv_capital_gains = self.wealth_taxable - self.taxable_basis / self.bonds_constant_inflation.discount_rate(average_asset_years) ** average_asset_years
            # Fails to take into consideration non-qualified dividends.
            # Taxable basis does not get adjusted for inflation.
        regular_tax, capital_gains_tax = \
            self.taxes.calculate_taxes(pv_regular_income / total_years, pv_social_security / total_years, pv_capital_gains / total_years, not self.couple)
                # Assumes income smoothing.
        pv_regular_tax = total_years * regular_tax
        pv_capital_gains_tax = total_years * capital_gains_tax
        self.pv_taxes = pv_regular_tax + pv_capital_gains_tax

        try:
            self.regular_tax_rate = pv_regular_tax / pv_regular_income
        except ZeroDivisionError:
            self.regular_tax_rate = 0
        self.p_wealth -= self.regular_tax_rate * self.wealth_tax_deferred
        self.raw_preretirement_income_wealth -= self.regular_tax_rate * (self.pv_preretirement_income['tax_deferred'] + self.pv_preretirement_income['taxable'])
        self.p_wealth = max(0, self.p_wealth - pv_capital_gains_tax)
        self.preretirement_income_wealth = max(0, self.raw_preretirement_income_wealth)
        self.net_wealth = max(0, self.net_wealth_pretax - self.pv_taxes)
        self.retired_income_wealth = max(0, self.net_wealth - self.p_wealth - self.preretirement_income_wealth)

        income_estimate = self.net_wealth / self.years_retired
        self.ce_estimate_individual = income_estimate / self.couple_weight

        try:
            self.consume_net_wealth_estimate = income_estimate / self.net_wealth
        except ZeroDivisionError:
            self.consume_net_wealth_estimate = float('inf')

        try:
            self.p_fraction = min(self.p_wealth / self.net_wealth, 1)
            self.preretirement_fraction = min(self.preretirement_income_wealth / self.net_wealth, 1)
        except ZeroDivisionError:
            self.p_fraction = 1
            self.preretirement_fraction = 1
        self.wealth_ratio = (self.retired_income_wealth + self.preretirement_income_wealth) / self.p_wealth if self.p_wealth > 0 else float('inf')
        self.wealth_ratio = min(self.wealth_ratio, 1e100) # Cap so that not calculating with inf.

        p_sum = self.p_sum()
        gi_sum = self.gi_sum() * self.params.time_period
        self.taxes_paid = min(self.taxes_due, p_sum + 0.9 * gi_sum) # Don't allow taxes to consume all of guaranteed income.
        self.p_plus_income = p_sum + gi_sum - self.taxes_paid

        self.spias_ever = self.params.real_spias or self.params.nominal_spias
        if self.spias_ever and (self.params.preretirement_spias or self.preretirement_years == 0):
            if self.couple:
                min_age = min(self.age, self.age2)
                max_age = max(self.age, self.age2)
            else:
                min_age = max_age = self.age2 if self.only_alive2 else self.age
            age_permitted = min_age >= self.params.spias_permitted_from_age and max_age <= self.params.spias_permitted_to_age
            self.spias_required = age_permitted and max_age >= self.params.spias_from_age
            self.spias = age_permitted and (self.params.couple_spias or not self.couple) or self.spias_required
        else:
            self.spias = False

    def spia_life_tables(self, age, age2):

        life_table = LifeTable(self.params.life_table_spia, self.params.sex, age, ae = 'aer2005_08-summary')
        if self.sex2:
            life_table2 = LifeTable(self.params.life_table_spia, self.sex2, age2, ae = 'aer2005_08-summary')
            if not self.couple:
                if self.only_alive2:
                    life_table = life_table2
                life_table2 = None
        else:
            life_table2 = None

        return life_table, life_table2

    _spia_years_cache = {}

    def _spia_years(self, offset_years):

        age = k_age = self.age + offset_years
        age2 = k_age2 = self.age2 + offset_years
        date = (self.date + timedelta(days = offset_years * 365)).isoformat()
        if self.sex2:
            if not self.couple:
                if self.only_alive2:
                    k_age = None
                else:
                    k_age2 = None
        else:
            k_age2 = None
        key = (k_age, k_age2, date)

        try:
            duration = Fin._spia_years_cache[key]
        except KeyError:
            life_table, life_table2 = self.spia_life_tables(age, age2)
            payout_delay = 0 # Observe better training for a generic model with a payout delay of 0 than self.params.time_period; not sure why.
            payout_fraction = 1 / (1 + self.params.consume_additional)
            spia = IncomeAnnuity(self.bonds_zero, life_table, life_table2 = life_table2, payout_delay = 12 * payout_delay, joint = True,
                payout_fraction = payout_fraction, frequency = 1 / self.params.time_period, price_adjust = 'all', date_str = date)

            duration = spia.premium(1) * self.params.time_period

            Fin._spia_years_cache[key] = duration

        return duration

    def _observe(self):

        couple = int(self.couple)
        if self.couple:
            num_401k = int(self.have_401k) + int(self.have_401k2)
        else:
            num_401k = int(self.have_401k2) if self.only_alive2 else int(self.have_401k)
        if self.couple and self.params.couple_hide:
            couple = 0
            num_401k = min(1, num_401k)
        one_on_gamma = 1 / self.gamma

        if self.spias_ever:
            # We siplify by comparing life expectancies and SPIA payouts rather than retirement expectancies and DIA payouts.
            # DIA payouts depend on retirement age, which would make the _spia_years_cache sigificiantly larger and less effective.
            if self.couple:
                max_age = max(self.age, self.age2) # Determines age cut-off and thus final purchase signal for the purchase of SPIAs.
            else:
                max_age = self.age2 if self.only_alive2 else self.age
            life_percentile = self.life_percentile[self.episode_length]
            spia_expectancy = self._spia_years(0)
            final_spias_purchase = max_age <= self.params.spias_permitted_to_age < max_age + self.params.time_period
            final_spias_purchase = int(final_spias_purchase)
        else:
            life_percentile = 0
            spia_expectancy = 0
            final_spias_purchase = 0

        alive_single = self.alive_single[self.episode_length]
        if alive_single == None:
            alive_single = 1
        reward_weight = (2 * self.retirement_expectancy_both[self.episode_length] + alive_single * self.retirement_expectancy_one[self.episode_length]) \
            * self.params.time_period
        _, _, reward_value = self.raw_reward(self.ce_estimate_individual)
        reward_estimate = reward_weight * self.reward_scale * reward_value
        reward_estimate = max(-1e30, reward_estimate) # Prevent observation of -inf reward estimate during training.

        # When mean reversion rate is zero, avoid observing spurious noise for better training.
        stocks_price, stocks_volatility = self.stocks.observe()
        if not self.params.observe_stocks_price or self.params.stocks_mean_reversion_rate == 0:
            stocks_price = 1
        if not self.params.observe_stocks_volatility:
            stocks_volatility = 1
        if self.params.observe_interest_rate:
            real_interest_rate, = self.bonds.real.observe()
        else:
            real_interest_rate = self.bonds.real.mean_short_interest_rate

        observe = (
            # Scenario description observations.
            couple, num_401k, one_on_gamma,
            # Nature of lifespan observations.
            self.preretirement_years, self.years_retired,
            # Annuitization related observations.
            life_percentile, spia_expectancy, final_spias_purchase,
            # Value function related observations.
            # Best results (especially when gamma=6) if provide both a rewards to go estimate that can be fine tuned and a relative CE estimate.
            reward_estimate, self.ce_estimate_individual / self.consume_scale,
            # Nature of wealth/income observations.
            # Obseve fractionality to hopefully take advantage of iso-elasticity of utility.
            self.p_fraction, self.preretirement_fraction,
            # Market condition obsevations.
            stocks_price, stocks_volatility, real_interest_rate)
        obs = self.encode_observation(observe)
        return obs

    def encode_observation(self, observe):

        obs = np.array(observe, dtype = 'float32')
        high = self.observation_space.high
        low = self.observation_space.low
        try:
            ok = all(low <= obs) and all(obs <= high)
        except FloatingPointError:
            self.warn('Invalid observation:', observe, obs, np.isnan(obs))
            assert False, 'Invalid observation.'
        if not ok:
            extreme_range = self.observation_space_extreme_range
            for index, ob in enumerate(obs):
                if not low[index] <= ob <= high[index]:
                    item = self.observation_space_items[index]
                    self.observation_space_range_exceeded[index] += 1
                    try:
                        fract = self.observation_space_range_exceeded[index] / self.env_timesteps
                    except ZeroDivisionError:
                        fract = float('inf')
                    if fract > 1e-4:
                        self.warn('Frequently out of range', item + ':', fract)
                    if not high[index] - extreme_range[index] < ob < low[index] + extreme_range[index]:
                        self.warn('Extreme', item + ', age:', ob, self.age)
                        if isinf(ob):
                            assert False, 'Infinite observation.'
                        if isnan(ob):
                            assert False, 'Undetected invalid observation.'
        if self.params.observation_space_ignores_range:
            try:
                obs = obs * self.observation_space_scale + self.observation_space_shift
            except FloatingPointError:
                assert False, 'Overflow in observation rescaling.'
        return obs

    def decode_observation(self, obs):

        return {item: value for item, value in zip(self.observation_space_items, obs.tolist())}
