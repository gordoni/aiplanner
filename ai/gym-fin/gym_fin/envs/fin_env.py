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
from random import seed, randint, random, uniform, lognormvariate

import numpy as np

from gym import Env
from gym.spaces import Box

from spia import LifeTable, YieldCurve, IncomeAnnuity

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.bonds import BondsSet
from gym_fin.envs.defined_benefit import DefinedBenefit
from gym_fin.envs.policies import policy
from gym_fin.envs.returns import Returns, returns_report, yields_report
from gym_fin.envs.returns_sample import ReturnsSample
from gym_fin.envs.taxes import Taxes, contribution_limit
from gym_fin.envs.utility import Utility

class FinError(Exception):

    pass

class AttributeObject(object):

    def __init__(self, dict):
        self.__dict__.update(dict)

class FinEnv(Env):

    metadata = {'render.modes': ['human']}

    def _compute_vital_stats(self, age_start, age_start2, preretirement):

        start_date = datetime.strptime(self.params.life_table_date, '%Y-%m-%d')
        this_year = datetime(start_date.year, 1, 1)
        next_year = datetime(start_date.year + 1, 1, 1)
        start_decimal_year = start_date.year + (start_date - this_year) / (next_year - this_year)

        alive_both = [1 if self.params.sex2 else 0]
        alive_one = [0 if self.params.sex2 else 1]
        _alive = 1
        _alive2 = 1

        alive_single = [None if self.params.sex2 else 1]
        _alive_single = None if self.params.sex2 else 1
        dead = False
        dead2 = self.params.sex2 == None
        dead_at = random()
        dead_at2 = random()
        only_alive2 = False

        alive_count = [2 if self.params.sex2 else 1] # Mock count of number of individuals alive. Only used for plots, for computations use alive_single probability.
        _alive_count = 2 if self.params.sex2 else 1

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
                if self.params.sex2:
                    q2 = self.life_table2.q(age_start2 + q_y, year = start_decimal_year + q_y)
                else:
                    q2 = 1
                remaining_fract = 1
                if q == q2 == 1:
                    break

        alive_either = tuple(alive_one[i] + alive_both[i] for i in range(len(alive_one)))

        life_expectancy_both = self.sums_to_end(alive_both, 0, alive_both)
        life_expectancy_one = self.sums_to_end(alive_one, 0, alive_either)

        retired_index = ceil(preretirement / self.params.time_period)
        retirement_expectancy_both = self.sums_to_end(alive_both, retired_index, alive_both)
        retirement_expectancy_one = self.sums_to_end(alive_one, retired_index, alive_either)
        retirement_expectancy_single = self.sums_to_end(alive_single, retired_index, alive_single)

        alive_single.append(0)
        alive_count.append(0)

        if not self.params.probabilistic_life_expectancy:
            alive_single = tuple(None if _alive_count == 2 else _alive_count for _alive_count in alive_count)

        self.only_alive2, self.alive_single, self.alive_count, self.life_expectancy_both, self.life_expectancy_one, \
            self.retirement_expectancy_both, self.retirement_expectancy_one, self.retirement_expectancy_single = \
            only_alive2, tuple(alive_single), tuple(alive_count), tuple(life_expectancy_both), tuple(life_expectancy_one), \
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

    def __init__(self, direct_action = False, **kwargs):

        self.direct_action = direct_action
        self.params = AttributeObject(kwargs)

        self.action_space = Box(low = -1.0, high = 1.0, shape = (15, ), dtype = 'float32')
            # consume_action, spias_action, real_spias_action,
            # stocks_action, real_bonds_action, nominal_bonds_action, iid_bonds_action, bills_action,
            # stocks_curvature_action, real_bonds_curvature_action, nominal_bonds_curvature_action, iid_bonds_curvature_action, bills_curvature_action,
            # real_bonds_duration_action, nominal_bonds_duration_action,
            # DDPG implementation assumes [-x, x] symmetric actions.
            # PPO1 implementation ignores size and very roughly initially assumes N(0, 1) actions, but potentially trainable to any value.
        self.observation_space = Box(
            # Note: Couple status must be observation[0], or else change is_couple() in gym-fin/gym_fin/common/tf_util.py and baselines/baselines/ppo1/pposgd_dual.py.
            # couple, number of 401(k)'s available, 1 / gamma
            # average asset years,
            # mortality return for spia, final spias purchase,
            # reward to go estimate, expected total income level of episode, total income level in remaining retirement,
            # portfolio wealth on total wealth, income present value as a fraction of total wealth: tax_deferred, taxable,
            # portfolio wealth as a fraction of total wealth: tax_deferred, taxable,
            # first person preretirement income as a fraction of total wealth, second person preretirement income as a fraction of total wealth,
            # consume preretirement as a fraction of total wealth, taxable basis as a fraction of total wealth,
            # stock price on fair value, short real interest rate, short inflation rate
            #
            # Values listed below are intended as an indicative ranges, not the absolute range limits.
            # Values are not used by ppo1. It is only the length that matters.
            low  = np.array((0, 0, 0,   0, -1, 0, -100,   0,   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.05, 0.0)),
            high = np.array((1, 2, 1, 100,  1, 1,  100, 5e5, 5e5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2,  0.05, 0.05)),
            dtype = 'float32'
        )

        assert self.params.action_space_unbounded in (False, True)
        assert self.params.observation_space_ignores_range in (False, True)

        self.env_couple_timesteps = 0
        self.env_single_timesteps = 0

        self.vs_cache = None

        self.life_table_age = None
        self.life_table2_age = None

        self.stocks = Returns(self.params.stocks_return, self.params.stocks_volatility, self.params.stocks_price_low, self.params.stocks_price_high,
            self.params.stocks_price_noise_sigma, self.params.stocks_mean_reversion_rate,
            self.params.stocks_standard_error if self.params.returns_standard_error else 0, self.params.time_period)
        self.iid_bonds = Returns(self.params.iid_bonds_return, self.params.iid_bonds_volatility, 1, 1, 0, 0,
            self.params.bonds_standard_error if self.params.returns_standard_error else 0, self.params.time_period)
        self.bills = Returns(self.params.bills_return, self.params.bills_volatility, 1, 1, 0, 0,
            self.params.bills_standard_error if self.params.returns_standard_error else 0, self.params.time_period)

        self.bonds = BondsSet(fixed_real_bonds_rate = self.params.fixed_real_bonds_rate, fixed_nominal_bonds_rate = self.params.fixed_nominal_bonds_rate,
            date_str = self.params.bonds_date, date_str_low = self.params.bonds_date_start,
            real_r0_type = self.params.real_short_rate_type, inflation_r0_type = self.params.inflation_short_rate_type)
        self.bonds.update(
            fixed_real_bonds_rate = self.params.fixed_real_bonds_rate, fixed_nominal_bonds_rate = self.params.fixed_nominal_bonds_rate,
            real_short_rate = self.params.real_short_rate_value, inflation_short_rate = self.params.inflation_short_rate_value,
            real_standard_error = self.params.bonds_standard_error if self.params.returns_standard_error else 0,
            inflation_standard_error = self.params.inflation_standard_error if self.params.returns_standard_error else 0,
            time_period = self.params.time_period)
        self.bonds_stepper = self.bonds.nominal
        self.bonds_zero = YieldCurve('fixed', self.params.life_table_date)

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
                returns_report('stocks', self.stocks, time_period = self.params.time_period)

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

        self.reset()

    def gi_sum(self, source = ('tax_free', 'tax_deferred', 'taxable')):

        gi = 0
        if 'taxable' in source:
            gi += self.income_preretirement + self.income_preretirement2
        for db in self.defined_benefits.values():
            if db.type_of_funds in source:
                gi += db.payout()

        return gi

    def p_sum(self):

        return self.p_tax_free + self.p_tax_deferred + self.p_taxable

    def get_db(self, type, owner, inflation_adjustment, joint, payout_fraction, type_of_funds):

        key = (type_of_funds, inflation_adjustment == 'cpi', type == 'Social Security', owner, joint, payout_fraction)
        try:
            db = self.defined_benefits[key]
        except KeyError:
            real = inflation_adjustment == 'cpi'
            db = DefinedBenefit(self, type = type, owner = owner, real = real, joint = joint, payout_fraction = payout_fraction, type_of_funds = type_of_funds)
            self.defined_benefits[key] = db

        return db

    def add_db(self, type = 'Income Annuity', owner = 'self', age = None, probability = 1, premium = None, payout = None, inflation_adjustment = 'cpi',
        joint = False, payout_fraction = 0, source_of_funds = 'tax_deferred', exclusion_period = 0, exclusion_amount = 0):

        assert owner in ('self', 'spouse')

        if owner == 'spouse' and self.params.sex2 == None:
            return

        if random() >= probability:
            return

        db = self.get_db(type, owner, inflation_adjustment, joint, payout_fraction, source_of_funds)
        adjustment = 0 if inflation_adjustment == 'cpi' else inflation_adjustment
        db.add(age = age, premium = premium, payout = payout, adjustment = adjustment, joint = joint, payout_fraction = payout_fraction,
               exclusion_period = exclusion_period, exclusion_amount = exclusion_amount)

    def parse_defined_benefits(self):

        self.defined_benefits = {}
        for db in loads(self.params.defined_benefits) + loads(self.params.defined_benefits_additional):
            self.add_db(**db)

    def age_uniform(self, low, high):
        if low == high:
            return low # Allow fractional ages.
        else:
            return randint(floor(low), ceil(high)) # SPIA module runs faster with non-fractional ages.

    def log_uniform(self, low, high):
        if low == high:
            return low # Handles low == high == 0.
        else:
            return exp(uniform(log(low), log(high)))

    def reset(self):

        if self.params.reproduce_episode != None:
            self._reproducable_seed(self.params.reproduce_episode, 0, 0)

        self.age = self.age_start = self.age_uniform(self.params.age_start_low, self.params.age_start_high)
        self.age2 = self.age_start2 = self.age_uniform(self.params.age_start2_low, self.params.age_start2_high)
        le_add = self.age_uniform(self.params.life_expectancy_additional_low, self.params.life_expectancy_additional_high)
        le_add2 = self.age_uniform(self.params.life_expectancy_additional2_low, self.params.life_expectancy_additional2_high)
        self.age_retirement = uniform(self.params.age_retirement_low, self.params.age_retirement_high)
        self.preretirement_years = max(0, self.age_retirement - self.age)

        death_age = self.params.age_end - self.params.time_period
        if self.age != self.life_table_age or le_add != self.life_table_le_add:
            self.life_table = LifeTable(self.params.life_table, self.params.sex, self.age,
                                        death_age = death_age, le_add = le_add, date_str = self.params.life_table_date, interpolate_q = False)
            self.life_table_age = self.age
            self.life_table_le_add = le_add
        else:
            self.life_table.age = self.age # Undo hack (value gets messed with below).
        if self.params.sex2 == None:
            self.life_table2 = None
        elif self.age2 != self.life_table2_age or le_add2 != self.life_table_le_add2:
            self.life_table2 = LifeTable(self.params.life_table, self.params.sex2, self.age2,
                                         death_age = death_age, le_add = le_add2, date_str = self.params.life_table_date, interpolate_q = False)
            self.life_table2_age = self.age2
            self.life_table_le_add2 = le_add2
        else:
            self.life_table2.age = self.age2
        self._compute_vital_stats(self.age, self.age2, self.preretirement_years)

        self.couple = self.alive_single[0] == None

        self.have_401k = bool(randint(int(self.params.have_401k_low), int(self.params.have_401k_high)))
        self.have_401k2 = bool(randint(int(self.params.have_401k2_low), int(self.params.have_401k2_high)))

        self.gamma = self.log_uniform(self.params.gamma_low, self.params.gamma_high)
        self.utility = Utility(self.gamma, self.params.consume_utility_floor)

        self.date_start = datetime.strptime(self.params.life_table_date, '%Y-%m-%d').date()
        self.date = self.date_start
        self.cpi = 1

        self.stocks.reset()
        self.iid_bonds.reset()
        self.bills.reset()

        self.bonds_stepper.reset()

        self.episode_length = 0

        found = False
        preretirement_ok = False
        for _ in range(1000):

            self.parse_defined_benefits()
            for db in self.defined_benefits.values():
                db.step(0) # Pick up non-zero schedule for observe.

            self.consume_preretirement = self.log_uniform(self.params.consume_preretirement_low, self.params.consume_preretirement_high)
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

            self.p_tax_free = self.log_uniform(self.params.p_tax_free_low, self.params.p_tax_free_high)
            self.p_tax_deferred = self.log_uniform(self.params.p_tax_deferred_low, self.params.p_tax_deferred_high)
            taxable_assets = AssetAllocation(fractional = False)
            if self.params.stocks:
                taxable_assets.aa['stocks'] = self.log_uniform(self.params.p_taxable_stocks_low, self.params.p_taxable_stocks_high)
            if self.params.real_bonds:
                taxable_assets.aa['real_bonds'] = self.log_uniform(self.params.p_taxable_real_bonds_low, self.params.p_taxable_real_bonds_high)
            if self.params.nominal_bonds:
                taxable_assets.aa['nominal_bonds'] = self.log_uniform(self.params.p_taxable_nominal_bonds_low, self.params.p_taxable_nominal_bonds_high)
            if self.params.iid_bonds:
                taxable_assets.aa['iid_bonds'] = self.log_uniform(self.params.p_taxable_iid_bonds_low, self.params.p_taxable_iid_bonds_high)
            if self.params.bills:
                taxable_assets.aa['bills'] = self.log_uniform(self.params.p_taxable_bills_low, self.params.p_taxable_bills_high)
            self.p_taxable = sum(taxable_assets.aa.values())
            if self.params.p_taxable_stocks_basis_fraction_low == self.params.p_taxable_stocks_basis_fraction_high:
                p_taxable_stocks_basis_fraction = self.params.p_taxable_stocks_basis_fraction_low
            else:
                p_taxable_stocks_basis_fraction = uniform(self.params.p_taxable_stocks_basis_fraction_low, self.params.p_taxable_stocks_basis_fraction_high)

            self.taxes = Taxes(self, taxable_assets, p_taxable_stocks_basis_fraction)
            self.taxes_due = 0

            self._pre_calculate()

            if self.preretirement_years * self.consume_preretirement > self.params.consume_income_ratio_max * \
                (min(self.preretirement_years, self.income_preretirement_years) * self.income_preretirement + \
                 min(self.preretirement_years, self.income_preretirement_years2) * self.income_preretirement2) + sum(self.wealth.values()):
                # Scenario consumes too much of portfolio preretirement.
                # Stochastic nature of preretirement income means we might run out of assets preretirement,
                # which would result in training to fit large negative reward values.
                continue

            preretirement_ok = True

            found = self.params.consume_floor <= self.consume_estimate_individual <= self.params.consume_ceiling
            if found:
                break

        if not found:
            if preretirement_ok:
                raise FinError('Expected consumption falls outside model training range.')
            else:
                raise FinError('Insufficient pre-retirement wages and wealth to support pre-retirement consumption.')

        self.consume_expect_individual = self.consume_estimate_individual
        _, self.reward_expect = self.raw_reward(self.consume_expect_individual)
        _, self.reward_zero_point = self.raw_reward(self.params.reward_zero_point_factor * self.consume_expect_individual)

        self.prev_asset_allocation = None
        self.prev_taxable_assets = taxable_assets
        self.prev_real_spias_rate = None
        self.prev_nominal_spias_rate = None
        self.prev_consume_rate = None
        self.prev_reward = None

        return self._observe()

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

        consume_action, spias_action, real_spias_action, \
            stocks_action, real_bonds_action, nominal_bonds_action, iid_bonds_action, bills_action, \
            stocks_curvature_action, real_bonds_curvature_action, nominal_bonds_curvature_action, iid_bonds_curvature_action, bills_curvature_action, \
            real_bonds_duration_action, nominal_bonds_duration_action = action

        def safe_atanh(x):
            try:
                return atanh(x)
            except ValueError:
                assert abs(x) == 1, 'Invalid value to atanh.'
                return copysign(10, x) # Change to 20 if using float64.

        if self.params.action_space_unbounded:
            consume_action = tanh(consume_action / 5)
                # Scaling back initial volatility of consume_action is observed to improve run to run mean and reduce standard deviation of certainty equivalent.
            spias_action = tanh(spias_action / 4)
                # Scaling back initial volatility of spias_action is observed to improve run to run mean and reduce standard deviation of certainty equivalent.
            real_spias_action = tanh(real_spias_action)
            real_bonds_duration_action = tanh(real_bonds_duration_action)
            nominal_bonds_duration_action = tanh(nominal_bonds_duration_action)
        else:
            stocks_action = safe_atanh(stocks_action)
            real_bonds_action = safe_atanh(real_bonds_action)
            nominal_bonds_action = safe_atanh(nominal_bonds_action)
            iid_bonds_action = safe_atanh(iid_bonds_action)
            bills_action = safe_atanh(bills_action)
            stocks_curvature_action = safe_atanh(stocks_curvature_action)
            real_bonds_curvature_action = safe_atanh(real_bonds_curvature_action)
            nominal_bonds_curvature_action = safe_atanh(nominal_bonds_curvature_action)
            iid_bonds_curvature_action = safe_atanh(iid_bonds_curvature_action)
            bills_curvature_action = safe_atanh(bills_curvature_action)

        if self.params.consume_rescale == 'estimate_biased':

            consume_action = (consume_action + 1) / 2
            consume_estimate = self.consume_p_estimate
            consume_weight = 2 * log((1 + sqrt(1 - 4 * consume_estimate * (1 - consume_estimate))) / (2 * consume_estimate))
                # So that consume_fraction = consume_estimate when consume_action = 0.5.
            consume_weight = max(1e-3, consume_weight) # Don't allow weight to become zero.
            # consume_action is in the range [0, 1]. Make consume_fraction also in the range [0, 1], but weight consume_fraction towards zero.
            # Otherwise by default consume 50% of assets each year. Quickly end up with few assets, and large negative utilities, making learning difficult.
            consume_fraction = (exp(consume_weight * consume_action) - 1) / (exp(consume_weight) - 1)

        elif self.params.consume_rescale == 'estimate_bounded':

            consume_action = (consume_action + 1) / 2
            # Define a consume floor and consume ceiling outside of which we won't consume.
            # The mid-point acts as a hint as to the initial consumption values to try.
            # With 0.5 as the mid-point (when time_period = 1) we will initially consume on average half the portfolio at each step.
            # This leads to very small consumption at advanced ages. The utilities and thus rewards for these values will be highly negative.
            # For DDPG the resulting reward values will be sampled from the replay buffer, leading to a good DDPG fit for the negative rewards.
            # This will be to the detriment of the fit for more likely reward values.
            # For PPO the policy network either never fully retrains after the initial poor fit, or requires more training time.
            consume_estimate = self.consume_p_estimate
            consume_floor = 0
            consume_ceil = 2 * consume_estimate
            consume_fraction = consume_floor + (consume_ceil - consume_floor) * consume_action

        else:

            assert False

        consume_fraction = max(1e-6, min(consume_fraction, 1 / self.params.time_period))
            # Don't allow consume_fraction of zero as have problems with -inf utility.

        if self.spias:

            # Try and make it easy to learn the optimal amount of guaranteed income,
            # so things function well with differing current amounts of guaranteed income.

            spias_action = (spias_action + 1) / 2
            current_spias_fraction_estimate = sum(self.pv_income.values()) / self.total_wealth
            current_spias_fraction_estimate = max(0, min(current_spias_fraction_estimate, 1))
            # Might like to pass on any more SPIAs when spias_action <= current_spias_fraction_estimate,
            # but that might then make learning to increase spias_action difficult.
            # We thus use a variant of the leaky ReLU.
            def leaky_lu(x):
                '''x in [-1, 1]. Result in [0, 1].'''
                leak = 0 # Disable leak for now as it results in unwanted SPIA purchases.
                return leak + x * (1 - leak) if x > 0 else leak * (1 + x)
            try:
                spias_fraction = leaky_lu(spias_action - current_spias_fraction_estimate) / leaky_lu(1 - current_spias_fraction_estimate)
            except ZeroDivisionError:
                spias_fraction = 0
            if spias_action - current_spias_fraction_estimate < self.params.spias_min_purchase_fraction:
                spias_fraction = 0
            assert 0 <= spias_fraction <= 1

            real_spias_fraction = spias_fraction if self.params.real_spias else 0
            if self.params.nominal_spias:
                real_spias_fraction *= (real_spias_action + 1) / 2
            nominal_spias_fraction = spias_fraction - real_spias_fraction

        if not self.params.real_spias or not self.spias:
            real_spias_fraction = None
        if not self.params.nominal_spias or not self.spias:
            nominal_spias_fraction = None

        # It is too much to expect optimization to compute the precise asset allocation surface.
        # Instead we provide guidelines as to what the surface might look like, and allow optimization to tune within those guidelines.
        #
        # Assuming defined benefits are risk free, for stocks and risk free portfolio assets using CRRA utility according to Merton's portfolio problem we expect:
        #     stocks * wealth / total_wealth = const
        # Re-arranging gives:
        #     stocks = total_wealth / wealth * const
        # And so:
        #     risk free = 1 - total_wealth / wealth * const
        # This suggests more generally equations of the form:
        #     asset class = y + (x - y) * total_wealth / wealth for x, y in [0, 1].
        # may be helpful to determining the stock allocation.

        # Softmax x's, the alocations when wealth is total_wealth (no defined benefits).
        stocks_action = exp(stocks_action) if self.params.stocks else 0
        real_bonds_action = exp(real_bonds_action) if self.params.real_bonds else 0
        nominal_bonds_action = exp(nominal_bonds_action) if self.params.nominal_bonds else 0
        iid_bonds_action = exp(iid_bonds_action) if self.params.iid_bonds else 0
        bills_action = exp(bills_action) if self.params.bills else 0
        total = stocks_action + real_bonds_action + nominal_bonds_action + iid_bonds_action + bills_action
        stocks_action /= total
        real_bonds_action /= total
        nominal_bonds_action /= total
        iid_bonds_action /= total
        bills_action /= total

        # Softax y's, so that when we fit to the curve (below) the allocations sum to one.
        stocks_curvature_action = exp(stocks_curvature_action) if self.params.stocks else 0
        real_bonds_curvature_action = exp(real_bonds_curvature_action) if self.params.real_bonds else 0
        nominal_bonds_curvature_action = exp(nominal_bonds_curvature_action) if self.params.nominal_bonds else 0
        iid_bonds_curvature_action = exp(iid_bonds_curvature_action) if self.params.iid_bonds else 0
        bills_curvature_action = exp(bills_curvature_action) if self.params.bills else 0
        total = stocks_curvature_action + real_bonds_curvature_action + nominal_bonds_curvature_action + iid_bonds_curvature_action + bills_curvature_action
        stocks_curvature_action /= total
        real_bonds_curvature_action /= total
        nominal_bonds_curvature_action /= total
        iid_bonds_curvature_action /= total
        bills_curvature_action /= total

        # Fit to curve.
        stocks = stocks_curvature_action + (stocks_action - stocks_curvature_action) * self.wealth_ratio
        real_bonds = real_bonds_curvature_action + (real_bonds_action - real_bonds_curvature_action) * self.wealth_ratio
        nominal_bonds = nominal_bonds_curvature_action + (nominal_bonds_action - nominal_bonds_curvature_action) * self.wealth_ratio
        iid_bonds = iid_bonds_curvature_action + (iid_bonds_action - iid_bonds_curvature_action) * self.wealth_ratio
        bills = bills_curvature_action + (bills_action - bills_curvature_action) * self.wealth_ratio

        # Asset classes will sum to one since actions and curvature actions each sum to one.
        # However individual asset classes may not be in the range [0, 1]. This needs to be fixed.
        # Softmax again.
        stocks = stocks if self.params.stocks else -1e100
        real_bonds = real_bonds if self.params.real_bonds else -1e100
        nominal_bonds = nominal_bonds if self.params.nominal_bonds else -1e100
        iid_bonds = iid_bonds if self.params.iid_bonds else -1e100
        bills = bills if self.params.bills else -1e100
        maximum = max(stocks, real_bonds, nominal_bonds, iid_bonds, bills) # Prevent exp() overflow.
        stocks = exp(stocks / maximum) if self.params.stocks else 0
        real_bonds = exp(real_bonds / maximum) if self.params.real_bonds else 0
        nominal_bonds = exp(nominal_bonds / maximum) if self.params.nominal_bonds else 0
        iid_bonds = exp(iid_bonds / maximum) if self.params.iid_bonds else 0
        bills = exp(bills / maximum) if self.params.bills else 0
        total = stocks + real_bonds + nominal_bonds + iid_bonds + bills
        stocks /= total
        real_bonds /= total
        nominal_bonds /= total
        iid_bonds /= total
        bills /= total

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

        real_bonds_duration = self.params.time_period + \
            (self.params.real_bonds_duration_max - self.params.time_period) * (real_bonds_duration_action + 1) / 2

        nominal_bonds_duration = self.params.time_period + \
            (self.params.nominal_bonds_duration_max - self.params.time_period) * (nominal_bonds_duration_action + 1) / 2

        return (consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration)

    def raw_reward(self, consume_rate):

        if self.couple:
            consume_rate = consume_rate / (1 + self.params.consume_additional)
            reward_weight = 2 * self.params.time_period
        else:
            reward_weight = self.alive_single[self.episode_length] * self.params.time_period
        consume = max(consume_rate, self.params.consume_clip)
        if self.params.verbose and consume != consume_rate:
            print('Consumption out of range - age, p_sum, consume_fraction, consume_rate:', self.age, self.p_sum(), consume_fraction, consume_rate)
        utility = self.utility.utility(consume)
        reward_annual = min(max(utility, - self.params.reward_clip), self.params.reward_clip)
        if self.params.verbose and reward_annual != utility:
            print('Reward out of range - age, p_sum, consume_fraction, utility:', self.age, self.p_sum(), consume_fraction, utility)

        return reward_weight, reward_annual

    def spend(self, consume_fraction, real_spias_fraction = 0, nominal_spias_fraction = 0):

        # Sanity check.
        consume_fraction_period = consume_fraction * self.params.time_period
        assert 0 <= consume_fraction_period <= 1

        p = self.p_plus_income
        if self.age < self.age_retirement:
            consume = min(p, self.consume_preretirement * self.params.time_period)
        else:
            #consume_annual = consume_fraction * p
            consume = consume_fraction_period * p
        p -= consume
        assert p >= 0

        p_taxable = self.p_taxable + (p - self.p_sum())
        p_tax_deferred = self.p_tax_deferred + min(p_taxable, 0)
        # Required Minimum Distributions (RMDs) not considered. Would need separate p_tax_deferred for each spouse.
        p_tax_free = self.p_tax_free + min(p_tax_deferred, 0)
        p_taxable = max(p_taxable, 0)
        p_tax_deferred = max(p_tax_deferred, 0)
        if p_tax_free < 0:
            assert p_tax_free / self.p_sum() > -1e-15
            p_tax_free = 0

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
        p_taxable -= real_taxable_spias + nominal_taxable_spias
        if p_taxable < 0:
            assert p_taxable / self.p_sum() > -1e-15
            p_taxable = 0

        return p_tax_free, p_tax_deferred, p_taxable, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias

    def interpret_spending(self, consume_fraction, asset_allocation, *, real_spias_fraction = 0, nominal_spias_fraction = 0,
        real_bonds_duration = None, nominal_bonds_duration = None):

        p_tax_free, p_tax_deferred, p_taxable, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias = \
            self.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)

        return {
            'consume': consume / self.params.time_period,
            'asset_allocation': asset_allocation,
            'retirement_contribution': retirement_contribution / self.params.time_period,
            'real_spias_purchase': real_tax_free_spias + real_tax_deferred_spias + real_taxable_spias if self.params.real_spias else None,
            'nominal_spias_purchase': nominal_tax_free_spias + nominal_tax_deferred_spias + nominal_taxable_spias if self.params.nominal_spias else None,
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

        owner = 'self' # Owner doesn't matter for joint SPIAs. Doing things this way reduces the number of db objects required for couples.
        age = self.age + self.params.time_period
        payout_fraction = 1 / (1 + self.params.consume_additional)
        if tax_free_spias > 0:
            self.add_db(owner = owner, age = age, premium = tax_free_spias, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'tax_free')
        if tax_deferred_spias > 0:
            self.add_db(owner = owner, age = age, premium = tax_deferred_spias, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'tax_deferred')
        if taxable_spias > 0:
            exclusion_period = ceil(self.life_expectancy_both[self.episode_length] + self.life_expectancy_one[self.episode_length])
                # Highly imperfect, but total exclusion amount will be correct.
            if inflation_adjustment in ('cpi', 0):
                exclusion_amount = taxable_spias / exclusion_period
            else:
                exclusion_amount = taxable_spias * inflation_adjustment / ((1 + inflation_adjustment) ** exclusion_period - 1)
            self.add_db(owner = owner, age = age, premium = taxable_spias, inflation_adjustment = inflation_adjustment, joint = True, \
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

        p_tax_free, p_tax_deferred, p_taxable, consume, retirement_contribution, \
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

        regular_income = self.gi_sum(source = ('tax_deferred', 'taxable')) - retirement_contribution \
            + self.p_tax_deferred - (p_tax_deferred - retirement_contribution + real_tax_deferred_spias + nominal_tax_deferred_spias)
        if regular_income < 0:
            if regular_income < -1e-12 * (self.gi_sum(source = ('tax_deferred', 'taxable')) + self.p_tax_deferred):
                print('Negative regular income:', regular_income)
                    # Possible if taxable SPIA non-taxable amount exceeds payout due to deflation.
            regular_income = 0

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

        self.taxes_due += self.taxes.tax(regular_income, not self.couple, inflation) - self.taxes_paid

        if self.age < self.age_retirement:
            self.reward_weight = 0
            self.reward_value = 0
            reward = 0
        else:
            self.reward_weight, self.reward_value = self.raw_reward(consume_rate)
            # Scale returned reward based on distance from zero point and initial expected reward value.
            # Ensures equal optimization emphasis placed on episodes with high and low expected reward value.
            # But this also means we need to observe the initial expected consumption level, as the observed reward is now a function of it.
            reward = self.reward_weight * (self.reward_value - self.reward_zero_point) / (self.reward_expect - self.reward_zero_point)
            if isinf(reward):
                print('Infinite reward')

        self._step()
        self._step_bonds()

        done = self.alive_single[self.episode_length] == 0
        if done:
            observation = None
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

        return observation, reward, done, info

    def _step(self, steps = 1, force_family_unit = False, forced_family_unit_couple = True):

        self.age += steps
        self.age2 += steps
        self.life_table.age = self.age # Hack.
        try:
            self.life_table2.age = self.age2
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

            self.retirement_expectancy_both = [0] * len(self.retirement_expectancy_both)
            self.retirement_expectancy_one = self.retirement_expectancy_single

            self.defined_benefits = {key: db for key, db in self.defined_benefits.items() if not db.sched_single_zero}
            for db in self.defined_benefits.values():
                db.couple_became_single()

        if self.income_preretirement_years > 0:
            for _ in range(steps):
                self.income_preretirement *= lognormvariate(self.params.income_preretirement_mu * self.params.time_period,
                    self.params.income_preretirement_sigma * sqrt(self.params.time_period))
        else:
            self.income_preretirement = 0
        if self.income_preretirement_years2 > 0:
            for _ in range(steps):
                self.income_preretirement2 *= lognormvariate(self.params.income_preretirement_mu2 * self.params.time_period,
                    self.params.income_preretirement_sigma2 * sqrt(self.params.time_period))
        else:
            self.income_preretirement2 = 0

        for db in self.defined_benefits.values():
            db.step(steps)

        self.episode_length += steps
        if self.couple:
            self.env_couple_timesteps += steps
        else:
            self.env_single_timesteps += steps

        self.couple = self.alive_single[self.episode_length] == None and not force_to_single or keep_as_couple

        self.date = self.date_start + timedelta(days = self.episode_length * self.params.time_period * 365.25)

    def _reproducable_seed(self, episode, episode_length, substep):

        seed(episode * 1000000 + episode_length * 1000 + substep, version = 2)

    def _step_bonds(self):

        if not self.params.static_bonds:

            if self.params.reproduce_episode != None:
                self._reproducable_seed(self.params.reproduce_episode, self.episode_length, 2)

            self.bonds_stepper.step()

    def goto(self, step = None, age = None, real_oup_x = None, inflation_oup_x = None, p_tax_free = None, p_tax_deferred = None, p_taxable_assets = None,
             p_taxable_stocks_basis_fraction = None, taxes_due = None, force_family_unit = False, forced_family_unit_couple = True):
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
            assert p_taxable_stocks_basis_fraction == None
        else:
            self.p_taxable = sum(p_taxable_assets.aa.values())
            self.taxes = Taxes(self, taxable_assets, p_taxable_stocks_basis_fraction)
        if taxes_due != None:
            self.taxes_due = 0

        self._pre_calculate()
        return self._observe()

    def set_reproduce_episode(self, episode):

        self.params.reproduce_episode = episode

    def render(self, mode = 'human'):

        print(self.age, self.p_tax_free, self.p_tax_deferred, self.p_taxable, \
              self.prev_asset_allocation, self.prev_consume_rate, self.prev_real_spias_rate, self.prev_nominal_spias_rate, self.prev_reward)

        for db in self.defined_benefits.values():
            db.render()

    def seed(self, seed=None):

        return

    def _pre_calculate(self):

        self.pv_income = {'tax_free': 0, 'tax_deferred': 0, 'taxable': 0}
        for db in self.defined_benefits.values():
            self.pv_income[db.type_of_funds] += db.pv()

        p_basis, cg_carry = self.taxes.observe()
        self.wealth = {'tax_free': self.p_tax_free, 'tax_deferred': self.p_tax_deferred, 'taxable': self.p_taxable - self.taxes_due}
        self.taxable_basis = p_basis - cg_carry

        if not self.params.tax and self.params.income_aggregate:
            self.pv_income = {'tax_free': sum(self.pv_income.values()), 'tax_deferred': 0, 'taxable': 0} # Results in better training.
            self.wealth = {'tax_free': sum(self.wealth.values()), 'tax_deferred': 0, 'taxable': 0}
            self.taxable_basis = 0

        self.pv_income_preretirement = self.income_preretirement * self.income_preretirement_years
        self.pv_income_preretirement2 = self.income_preretirement2 * self.income_preretirement_years2
        self.pv_consume_preretirement = self.consume_preretirement * self.preretirement_years

        self.total_wealth = sum(self.pv_income.values()) + sum(self.wealth.values()) \
            + self.pv_income_preretirement + self.pv_income_preretirement2 - self.pv_consume_preretirement

        w = sum(self.wealth.values())
        self.wealth_ratio = self.total_wealth / w if w > 0 else float('inf')
        self.wealth_ratio = min(self.wealth_ratio, 50) # Cap so that exp(wealth_ratio) doesn't overflow.

        self.p_plus_income = self.p_sum() + self.gi_sum() * self.params.time_period
        self.taxes_paid = min(self.taxes_due, 0.9 * self.p_plus_income) # Don't allow taxes to consume all of p.
        self.p_plus_income -= self.taxes_paid

        self.spias = (self.params.real_spias or self.params.nominal_spias) and (self.params.couple_spias or not self.couple)
        if self.spias:
            if self.couple:
                min_age = min(self.age, self.age2)
                max_age = max(self.age, self.age2)
            else:
                min_age = max_age = self.age2 if self.only_alive2 else self.age
            self.spias = min_age >= self.params.spias_permitted_from_age and max_age <= self.params.spias_permitted_to_age

        if self.couple:
            self.years_retired = self.retirement_expectancy_both[self.episode_length] + \
                self.retirement_expectancy_one[self.episode_length] / (1 + self.params.consume_additional)
            self.consume_estimate_individual = self.total_wealth / self.years_retired / (1 + self.params.consume_additional)
        else:
            self.years_retired = self.retirement_expectancy_one[self.episode_length]
            self.consume_estimate_individual = self.total_wealth / self.years_retired

        try:
            self.consume_p_estimate = self.total_wealth / self.years_retired / self.p_plus_income
        except ZeroDivisionError:
            self.consume_p_estimate = float('inf')

    def spia_life_tables(self, age, age2):

        life_table = LifeTable(self.params.life_table_spia, self.params.sex, age, ae = 'aer2005_08-summary')
        if self.params.sex2:
            life_table2 = LifeTable(self.params.life_table_spia, self.params.sex2, age2, ae = 'aer2005_08-summary')
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
        if self.params.sex2:
            if not self.couple:
                if self.only_alive2:
                    k_age = None
                else:
                    k_age2 = None
        else:
            k_age2 = None
        key = (k_age, k_age2, date)

        try:
            duration = FinEnv._spia_years_cache[key]
        except KeyError:
            life_table, life_table2 = self.spia_life_tables(age, age2)
            payout_delay = 0
            payout_fraction = 1 / (1 + self.params.consume_additional)
            spia = IncomeAnnuity(self.bonds_zero, life_table, life_table2 = life_table2, payout_delay = 12 * payout_delay, joint_contingent = True,
                joint_payout_fraction = payout_fraction, frequency = round(1 / self.params.time_period), date_str = date)

            duration = spia.premium(1) * self.params.time_period

            FinEnv._spia_years_cache[key] = duration

        return duration

    def _observe(self):

        couple = int(self.couple)
        if couple:
            num_401k = int(self.have_401k) + int(self.have_401k2)
        else:
            num_401k = int(self.have_401k2) if self.only_alive2 else int(self.have_401k)
        one_on_gamma = 1 / self.gamma

        average_asset_years = self.preretirement_years + self.years_retired / 2
            # Consumption amount in retirement and thus expected reward to go is likely a function of average asset age.

        if self.spias:
            # We siplify by comparing life expectancies and SPIA payouts rather than retirement expectancies and DIA payouts.
            # DIA payouts depend on retirement age, which would make the _spia_years_cache sigificiantly larger and less effective.
            later = self.episode_length + round(10 / self.params.time_period)
            if self.couple:
                max_age = max(self.age, self.age2) # Determines age cut-off and thus final purchase signal for the purchase of SPIAs.
                life_expectancy_now = self.life_expectancy_both[self.episode_length] + \
                    self.life_expectancy_one[self.episode_length] / (1 + self.params.consume_additional)
            else:
                max_age = self.age2 if self.only_alive2 else self.age
                life_expectancy_now = self.life_expectancy_one[self.episode_length]
            spia_years_now = self._spia_years(0)
            spia_mortality_return = life_expectancy_now / spia_years_now - 1 # Fraction by which outlive SPIA mortality.
            final_spias_purchase = max_age <= self.params.spias_permitted_to_age < max_age + self.params.time_period
            final_spias_purchase = int(final_spias_purchase)
        else:
            spia_mortality_return = 0
            final_spias_purchase = 0

        reward_weight = (2 * self.retirement_expectancy_both[self.episode_length] + self.retirement_expectancy_one[self.episode_length]) * self.params.time_period
        _, reward_value = self.raw_reward(self.consume_estimate_individual)
        reward_estimate = reward_weight * (reward_value - self.reward_zero_point) / (self.reward_expect - self.reward_zero_point)

        tw = self.total_wealth
        if tw == 0:
            tw = sum(self.pv_income.values())
            if tw == 0:
                tw = 1 # To avoid divide by zero later.
        w = sum(self.wealth.values())

        if self.params.stocks_mean_reversion_rate != 0:
            stocks_price, = self.stocks.observe()
        else:
            stocks_price = 1 # Avoid observing spurious noise for better training.
        if self.params.observe_interest_rate:
            real_interest_rate, = self.bonds.real.observe()
        else:
            real_interest_rate = 0
        if self.params.observe_inflation_rate:
            inflation_rate, = self.bonds.inflation.observe()
        else:
            inflation_rate = 0

        observe = (
            # Scenario description observations.
            couple, num_401k, one_on_gamma,
            # Nature of lifespan observations.
            average_asset_years,
            # Annuitization related observations.
            spia_mortality_return, final_spias_purchase,
            # Value function related observations.
            # Best results (especially when gamma=6) if provide both reward estimate and reward estimate components: consume expect and consume estimate.
            reward_estimate, self.consume_expect_individual, self.consume_estimate_individual,
            # Nature of wealth/income observations.
            # Obseve fractionality to hopefully take advantage of iso-elasticity of utility.
            # No need to observe tax free wealth or income as this represents the baseline case.
            w / tw, self.pv_income['tax_deferred'] / tw, self.pv_income['taxable'] / tw,
            self.wealth['tax_deferred'] / tw, self.wealth['taxable'] / tw,
            self.pv_income_preretirement / tw, self.pv_income_preretirement2 / tw, self.pv_consume_preretirement / tw,
            self.taxable_basis / tw,
            # Market condition obsevations.
            stocks_price, real_interest_rate, inflation_rate)
        obs = np.array(observe, dtype = 'float32')
        obs = self.encode_observation(obs)
        if np.any(np.isnan(obs)) or np.any(np.isinf(obs)):
            print(observe, obs)
            assert False, 'Invalid observation.'
        return obs

    def encode_observation(self, obs):

        if self.params.observation_space_ignores_range:
            obs = obs / np.maximum(abs(self.observation_space.low), abs(self.observation_space.high))
        return obs

    def decode_observation(self, obs):

        items = ('couple', 'num_401k', 'one_on_gamma',
            'preretirement_years', 'average_asset_years',
            'spia_mortality_return', 'final_spias_purchase',
            'reward_estimate', 'consume_expect_individual', 'consume_estimate_individual',
            'wealth_fraction', 'income_tax_deferred_fraction', 'income_taxable_fraction',
            'wealth_tax_deferred_fraction', 'wealth_taxable_fraction',
            'income_preretirement_fraction', 'income_preretirement2_fraction', 'consume_preretirement_fraction',
            'taxable_basis',
            'stocks_price', 'real_interest_rate', 'inflation_rate')

        return {item: value for item, value in zip(items, obs.tolist())}
