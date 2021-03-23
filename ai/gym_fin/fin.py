# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from datetime import datetime, timedelta
from enum import Enum
from json import loads
from math import atanh, ceil, copysign, exp, floor, isinf, isnan, log, sqrt, tanh
from os import environ
from os.path import expanduser
from random import seed, randint, random, uniform, lognormvariate
from sys import stderr, stdout

import numpy as np

import cython

from ai.gym_fin.asset_classes import AssetClasses
from ai.gym_fin.factory import make_asset_allocation, make_bonds_set, make_defined_benefit, make_fin_params, make_policy, make_taxes, make_utility
from ai.gym_fin.factory_spia import make_income_annuity, make_life_table, make_yield_curve
from ai.gym_fin.returns_equity import ReturnsEquity, ReturnsIID, returns_report, yields_report
from ai.gym_fin.returns_sample import ReturnsSample

STOCKS = AssetClasses.STOCKS.value
REAL_BONDS = AssetClasses.REAL_BONDS.value
NOMINAL_BONDS = AssetClasses.NOMINAL_BONDS.value
IID_BONDS = AssetClasses.IID_BONDS.value

class TaxStatus(Enum):

    TAX_FREE = 0
    TAX_DEFERRED = 1
    TAXABLE = 2

TAX_FREE = TaxStatus.TAX_FREE.value
TAX_DEFERRED = TaxStatus.TAX_DEFERRED.value
TAXABLE = TaxStatus.TAXABLE.value

@cython.cclass
class Fin:

    # Properties for public variables.
    # @cython.cclass makes variables inaccessible to other code.

    @property
    def age(self):
        return self._age

    @property
    def age2(self):
        return self._age2

    @property
    def alive_both(self):
        return self._alive_both

    @property
    def alive_one(self):
        return self._alive_one

    @property
    def anticipated_episode_length(self):
        return self._anticipated_episode_length

    @property
    def bonds_constant_inflation(self):
        return self._bonds_constant_inflation

    @property
    def bonds_zero(self):
        return self._bonds_zero

    @property
    def cpi(self):
        return self._cpi

    @property
    def date(self):
        return self._date

    @property
    def defined_benefits(self):
        return self._defined_benefits

    @property
    def episode_length(self):
        return self._episode_length

    @property
    def life_table(self):
        return self._life_table

    @property
    def life_table2(self):
        return self._life_table2

    @property
    def life_table_preretirement(self):
        return self._life_table_preretirement

    @property
    def life_table2_preretirement(self):
        return self._life_table2_preretirement

    @property
    def net_gi(self):
        return self._net_gi

    @property
    def p_wealth(self):
        return self._p_wealth

    @property
    def params_dict(self):
        return self._params_dict

    @property
    def preretirement_years(self):
        return self._preretirement_years

    @property
    def p_sum(self):
        return self._p_sum

    @property
    def p_plus_income(self):
        return self._p_plus_income

    @property
    def sex2(self):
        return self._sex2

    @property
    def utility(self):
        return self._utility

    @property
    def warnings(self):
        return self._warnings

    def set_info(self, rewards = None, rollouts = None, strategy = None):
        if rewards is not None:
            self._info_rewards = rewards
        if rollouts is not None:
            self._info_rollouts = rollouts
        if strategy is not None:
            self._info_strategy = strategy

    def _warn(self, *args, timestep_ok_fraction = 0):

        if self._params.warn:
            stderr.write('AIPLANNER: ' + ' '.join(str(arg) for arg in args) + '\n')
            stderr.flush()

        try:
            self._warnings[args[0]]['count'] += 1
        except KeyError:
            self._warnings[args[0]] = {
                'count': 1,
                'timestep_ok_fraction': timestep_ok_fraction,
            }

    _vital_stats_cache = {}

    def _compute_vital_stats(self, age_start, age_start2, preretirement, key):

        if self._sex2 or self._info_rollouts or not self._params.probabilistic_life_expectancy:
            # Can't cache vital stats for couple as would loose random rollouts of couple expectancy.
            # Additionally would need to save _retirement_expectancy_one and _retirement_expectancy_both as they get clobbered below.
            # Can't cache vital stats if info rollouts as _alive_count wouldn't get updated.
            key = None

        try:

            vs = Fin._vital_stats_cache[key]

        except KeyError:

            start_date = datetime.strptime(self._params.life_table_date, '%Y-%m-%d')
            this_year = datetime(start_date.year, 1, 1)
            next_year = datetime(start_date.year + 1, 1, 1)
            start_decimal_year = start_date.year + (start_date - this_year) / (next_year - this_year)

            alive_both = [1 if self._sex2 else 0] # Probability across all rollouts.
            alive_one = [0 if self._sex2 else 1] # Probability across all rollouts.
            _alive = 1
            _alive2 = 1

            alive_single = [-1 if self._sex2 else 1] # Probability for this couple rollout. -1 if couple.
            _alive_single = -1 if self._sex2 else 1
            dead = False
            dead2 = self._sex2 is None
            dead_at = random()
            dead_at2 = random()
            only_alive2 = False

            alive_count = [2 if self._sex2 else 1] # Mock count of number of individuals alive. Only used for plots, for computations use alive_single probability.
            _alive_count = 2 if self._sex2 else 1

            y = 0
            q_y = -1
            q = 0
            q2 = 0
            remaining_fract = 0
            a_y = self._params.time_period
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
                    dead2 = dead if self._params.couple_death_concordant else _alive2 < dead_at2
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
                    a_y += self._params.time_period
                if y - q_y >= 1:
                    q_y += 1
                    q = self._life_table.q(age_start + q_y, year = start_decimal_year + q_y)
                    if self._sex2:
                        q2 = self._life_table2.q(age_start2 + q_y, year = start_decimal_year + q_y)
                    else:
                        q2 = 1
                    remaining_fract = 1
                    if q == q2 == 1:
                        break

            alive_either = tuple(alive_one[i] + alive_both[i] for i in range(len(alive_one)))

            life_expectancy_both = self._sums_to_end(alive_both, 0, alive_both)
            life_expectancy_one = self._sums_to_end(alive_one, 0, alive_either)

            percentile = 0.8
            alive_weighted = list(alive_one[i] + alive_both[i] * (1 + self._params.consume_additional) for i in range(len(alive_one)))
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
                life_percentile.insert(0, (j - i + 1 + partial) * self._params.time_period)

            retired_index = ceil(preretirement / self._params.time_period)
            retirement_expectancy_both = self._sums_to_end(alive_both, retired_index, alive_both)
            retirement_expectancy_one = self._sums_to_end(alive_one, retired_index, alive_either)
            retirement_expectancy_single = self._sums_to_end(alive_single, retired_index, alive_single)

            alive_single.append(0.0)
            alive_count.append(0)

            if not self._params.probabilistic_life_expectancy:
                alive_single = [-1 if _alive_count == 2 else _alive_count for _alive_count in alive_count]

            vs = alive_both, alive_one, only_alive2, alive_single, alive_count, \
                life_expectancy_both, life_expectancy_one, life_percentile, \
                retirement_expectancy_both, retirement_expectancy_one, retirement_expectancy_single

            if key is not None and len(Fin._vital_stats_cache) < 1000:
                Fin._vital_stats_cache[key] = vs

        # np.arrays allow cython.double[:] memory view access which is very fast, but isn't used because memory views can't be pickled.
        # If using np.arrays for memory view access have to ensure returned value is converted to a cython.double otherwise indexing is slow
        # and calculations using numpy.float64 will propagate and are also slow.
        # This can be done by typing the variable the value is assigned to as a cython.double when runing under Cython, or using float() for cPython.
        self._alive_both, self._alive_one, self._only_alive2, self._alive_single, self._alive_count, \
            self._life_expectancy_both, self._life_expectancy_one, self._life_percentile, \
            self._retirement_expectancy_both, self._retirement_expectancy_one, self._retirement_expectancy_single = vs

    def _sums_to_end(self, l, start, divl):

        r = [0]
        s = 0
        for i in range(len(l) - 1, -1, -1):
            if i >= start:
                try:
                    s += l[i]
                except TypeError:
                    s = None
            try:
                v = s / divl[i] * self._params.time_period
            except TypeError:
                v = None
            except ZeroDivisionError:
                assert s == 0
                v = 0
            r.insert(0, v)

        return r

    def __init__(self, fin_env, direct_action, params_dict):

        self._observation_space_items = fin_env.observation_space_items
        observation_space_low = np.array(fin_env.observation_space_low)
        observation_space_high = np.array(fin_env.observation_space_high)

        self._direct_action = direct_action

        self._params_dict = params_dict
        self._params = make_fin_params(params_dict)

        observation_space_range = observation_space_high - observation_space_low
        observation_space_scale = 2 / observation_space_range
        observation_space_shift = -1 - observation_space_low * observation_space_scale
        observation_space_extreme_range = self._params.observation_space_warn * observation_space_range
        observation_space_extreme_range[self._observation_space_items.index('reward_to_go_estimate')] *= 2
        observation_space_extreme_range[self._observation_space_items.index('relative_ce_estimate_individual')] *= 3
        observation_space_extreme_range[self._observation_space_items.index('stocks_price')] *= 2
        observation_space_extreme_range[self._observation_space_items.index('stocks_volatility')] *= 2
        observation_space_extreme_range[self._observation_space_items.index('real_interest_rate')] = 0.30
        observation_space_range_exceeded = np.zeros(observation_space_extreme_range.shape, dtype = 'int')

        self._observation_space_low_np = observation_space_low
        self._observation_space_high_np = observation_space_high
        self._observation_space_low = observation_space_low.tolist()
        self._observation_space_high = observation_space_high.tolist()
        self._observation_space_scale = observation_space_scale.tolist()
        self._observation_space_shift = observation_space_shift.tolist()
        self._observation_space_extreme_range = observation_space_extreme_range.tolist()
        self._observation_space_range_exceeded = observation_space_range_exceeded.tolist()

        self._info_rewards = False
        self._info_rollouts = False
        self._info_strategy = False

        self._env_timesteps = 0

        self._init_done = False

    def _init(self):

        np.seterr(divide = 'raise', over = 'raise', under = 'ignore', invalid = 'raise')

        self.e = exp(1) # Cython - self.e ** x which uses the C pow function is faster than calling the Python exp(x).

        home_dir = environ.get('AIPLANNER_HOME', expanduser('~/aiplanner'))

        self._warnings = {}

        assert self._params.sex in ('male', 'female'), 'sex must be male or female.'
        assert self._params.sex2 in ('male', 'female'), 'sex2 must be male or female.'

        self._age_start = self._params.age_start
        self._death_age = self._params.age_end - self._params.time_period
        self._life_table_le_hi = make_life_table(self._params.life_table, self._params.sex, self._age_start, death_age = self._death_age,
            le_add = self._params.life_expectancy_additional_high, date_str = self._params.life_table_date, interpolate_q = self._params.life_table_interpolate_q)

        self._tax_free_assets = make_asset_allocation() # Will be reused for speed.
        self._tax_deferred_assets = make_asset_allocation()
        self._taxable_assets = make_asset_allocation()

        self._taxes = make_taxes(self._params)

        if self._params.stocks_model in ('normal_residuals', 'bootstrap'):
            std_res_fname = home_dir + '/data/public/standardized_residuals.csv'
            self._stocks = ReturnsEquity(self._params, std_res_fname = std_res_fname)
        else:
            self._stocks = ReturnsIID(self._params.stocks_return, self._params.stocks_volatility,
                self._params.stocks_standard_error if self._params.returns_standard_error else 0, self._params.time_period)
        self._iid_bonds = ReturnsIID(self._params.iid_bonds_return, self._params.iid_bonds_volatility,
            self._params.bonds_standard_error if self._params.returns_standard_error else 0, self._params.time_period)

        assert self._params.real_short_rate_type != 'value' or self._params.real_short_rate_value != -1
        assert self._params.inflation_short_rate_type != 'value' or self._params.inflation_short_rate_value != -1
        self._bonds = make_bonds_set(fixed_real_bonds_rate = self._params.fixed_real_bonds_rate, fixed_nominal_bonds_rate = self._params.fixed_nominal_bonds_rate,
            real_bonds_adjust = self._params.real_bonds_adjust, inflation_adjust = self._params.inflation_adjust,
            nominal_bonds_adjust = self._params.nominal_bonds_adjust, corporate_nominal_spread = self._params.corporate_nominal_spread,
            static_bonds = self._params.static_bonds, date_str = self._params.bonds_date, date_str_low = self._params.bonds_date_start,
            real_r0_type = self._params.real_short_rate_type, inflation_r0_type = self._params.inflation_short_rate_type)
        self._bonds.update(
            fixed_real_bonds_rate = self._params.fixed_real_bonds_rate, fixed_nominal_bonds_rate = self._params.fixed_nominal_bonds_rate,
            real_short_rate = self._params.real_short_rate_value, inflation_short_rate = self._params.inflation_short_rate_value,
            real_standard_error = self._params.bonds_standard_error if self._params.returns_standard_error else 0,
            inflation_standard_error = self._params.inflation_standard_error if self._params.returns_standard_error else 0,
            time_period = self._params.time_period)
        self._bonds_stepper = self._bonds.nominal
        self._bonds_zero = make_yield_curve('fixed', self._params.life_table_date)
        self._bonds_constant_inflation = make_yield_curve('fixed', self._params.life_table_date, adjust = self._bonds.inflation.discount_rate(100) - 1)

        if self._params.iid_bonds:
            if self._params.iid_bonds_type == 'real':
                self._iid_bonds = ReturnsSample(self._bonds.real, self._params.iid_bonds_duration,
                    self._params.bonds_standard_error if self._params.returns_standard_error else 0,
                    stepper = self._bonds_stepper, time_period = self._params.time_period)
            elif self._params.iid_bonds_type == 'nominal':
                self._iid_bonds = ReturnsSample(self._bonds.nominal, self._params.iid_bonds_duration,
                    self._params.bonds_standard_error if self._params.returns_standard_error else 0,
                    stepper = self._bonds_stepper, time_period = self._params.time_period)

        if self._params.display_returns:

            print()
            print('Real/nominal yields:')

            if self._params.real_bonds:
                if self._params.real_bonds_duration != -1:
                    yields_report('real bonds {:2d}'.format(int(self._params.real_bonds_duration)), self._bonds.real,
                        duration = self._params.real_bonds_duration, stepper = self._bonds_stepper, time_period = self._params.time_period)
                else:
                    yields_report('real bonds  5', self._bonds.real, duration = 5, stepper = self._bonds_stepper, time_period = self._params.time_period)
                    yields_report('real bonds 15', self._bonds.real, duration = 15, stepper = self._bonds_stepper, time_period = self._params.time_period)

            if self._params.nominal_bonds:
                if self._params.nominal_bonds_duration != -1:
                    yields_report('nominal bonds {:2d}'.format(int(self._params.nominal_bonds_duration)), self._bonds.nominal,
                        duration = self._params.nominal_bonds_duration, stepper = self._bonds_stepper, time_period = self._params.time_period)
                else:
                    yields_report('nominal bonds  5', self._bonds.nominal, duration = 5, stepper = self._bonds_stepper, time_period = self._params.time_period)
                    yields_report('nominal bonds 15', self._bonds.nominal, duration = 15, stepper = self._bonds_stepper, time_period = self._params.time_period)

            print()
            print('Real returns:')

            if self._params.stocks:
                returns_report('stocks', lambda: self._stocks.sample(), resetter = self._stocks, time_period = self._params.time_period,
                    sample_count = 5000, sample_skip = 10)
                    # resetter needed to sample from standard error.

            if self._params.real_bonds:
                if self._params.real_bonds_duration != -1:
                    returns_report('real bonds {:2d}'.format(int(self._params.real_bonds_duration)),
                        lambda: self._bonds.real.sample(self._params.real_bonds_duration), stepper = self._bonds_stepper, time_period = self._params.time_period)
                else:
                    returns_report('real bonds  5', lambda: self._bonds.real.sample(5), stepper = self._bonds_stepper, time_period = self._params.time_period)
                    returns_report('real bonds 15', lambda: self._bonds.real.sample(15), stepper = self._bonds_stepper, time_period = self._params.time_period)

            if self._params.nominal_bonds:
                if self._params.nominal_bonds_duration != -1:
                    returns_report('nominal bonds {:2d}'.format(int(self._params.nominal_bonds_duration)),
                        lambda: self._bonds.nominal.sample(self._params.nominal_bonds_duration),
                        stepper = self._bonds_stepper, time_period = self._params.time_period)
                else:
                    returns_report('nominal bonds  5', lambda: self._bonds.nominal.sample(5), stepper = self._bonds_stepper, time_period = self._params.time_period)
                    returns_report('nominal bonds 15', lambda: self._bonds.nominal.sample(15), stepper = self._bonds_stepper, time_period = self._params.time_period)

            if self._params.iid_bonds:
                returns_report('iid bonds', lambda: self._iid_bonds.sample(), resetter = self._iid_bonds, time_period = self._params.time_period)

            if self._params.nominal_bonds or self._params.nominal_spias:
                returns_report('inflation', lambda: self._bonds.inflation.inflation(), stepper = self._bonds_stepper, time_period = self._params.time_period)

        self._init_done = True

    def _gi_sum(self):

        self._gi_total = self._income_preretirement + self._income_preretirement2
        self._gi_regular = self._gi_total if self._params.income_preretirement_taxable else 0
        self._gi_social_security = 0
        type_of_funds: str; is_social_security: cython.bint; db: DefinedBenefit
        for (type_of_funds, real, is_social_security), db in self._defined_benefits.items():
            payout = db.payout(self._cpi)
            self._gi_total += payout
            if type_of_funds in ('tax_deferred', 'taxable'):
                self._gi_regular += payout
            if is_social_security:
                self._gi_social_security += payout

    def get_db(self, type, real, type_of_funds):

        key = (type_of_funds, real, type == 'social_security')
        try:
            db = self._defined_benefits[key]
        except KeyError:
            db = make_defined_benefit(self, self._params, real = real, type_of_funds = type_of_funds)
            self._defined_benefits[key] = db

        return db

    def _add_db(self, type = 'income_annuity', owner = 'self', start = None, end = None, probability = 1, payout = None,
        inflation_adjustment = 'cpi', joint = False, payout_fraction = 0, source_of_funds = 'tax_deferred', exclusion_period = 0, exclusion_amount = 0,
        delay_calcs = False):

        assert owner in ('self', 'spouse')
        assert source_of_funds in ('tax_free', 'tax_deferred', 'taxable')

        if owner == 'spouse' and self._sex2 is None:
            return

        if random() >= probability:
            return

        if not self._couple:
            joint = False
            payout_fraction = 0

        real = inflation_adjustment == 'cpi'
        db = self.get_db(type, real, source_of_funds)
        adjustment = 0 if inflation_adjustment == 'cpi' else inflation_adjustment
        db.add(type = type, owner = owner, start = start, end = end, payout = payout, adjustment = adjustment,
            joint = joint, payout_fraction = payout_fraction,
            exclusion_period = exclusion_period, exclusion_amount = exclusion_amount, delay_calcs = delay_calcs)

    def _parse_defined_benefits(self):

        self._defined_benefits = {}
        for db in loads(self._params.guaranteed_income) + loads(self._params.guaranteed_income_additional):
            self._add_db(delay_calcs = True, **db)

        for db in self._defined_benefits.values():
            db.force_calcs()

    def _age_uniform(self, low, high):
        # This routine is here to work around an apparent Cython 0.29.14 bug.
        # Without the call to randint, after several million timesteps the cPython and Cython checkpoints differ ever so slightly,
        # and the final gamma=6, no tax, no SPIA, IID certainty equivalent distribution with a set of 10 seeds drops by an average of 5 standard errors.
        randint(floor(low), ceil(high))
        ret = uniform(low, high)
        return ret

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

        self._sex2 = self._params.sex2 if random() < self._params.couple_probability else None

        self._age = self._age_start
        self._age2 = self._age_uniform(self._params.age_start2_low, self._params.age_start2_high)
        le_add = uniform(self._params.life_expectancy_additional_low, self._params.life_expectancy_additional_high)
        le_add2 = uniform(self._params.life_expectancy_additional2_low, self._params.life_expectancy_additional2_high)
        self._age_retirement = uniform(self._params.age_retirement_low, self._params.age_retirement_high)

        self._life_table = make_life_table(self._params.life_table, self._params.sex, self._age, death_age = self._death_age,
            le_add = le_add, date_str = self._params.life_table_date, interpolate_q = self._params.life_table_interpolate_q)
        self._life_table2 = make_life_table(self._params.life_table, self._sex2, self._age2, death_age = self._death_age,
            le_add = le_add2, date_str = self._params.life_table_date, interpolate_q = self._params.life_table_interpolate_q) if self._sex2 else None

        if not self._params.age_continuous and self._params.life_expectancy_additional_low != self._params.life_expectancy_additional_high:
           self._life_table.age_add = floor(self._life_table.age_add)
           if self._sex2 is not None:
               self._life_table2.age_add = floor(self._life_table2.age_add)
           self._life_table_le_hi.age_add = floor(self._life_table_le_hi.age_add)

        # Try and ensure each training episode starts with the same life expectancy (at least if single).
        # This helps ensure set_reward_level() normalizes as consistently as possible. May not be necessary.
        adjust = self._life_table.age_add - self._life_table_le_hi.age_add
        self._age -= adjust
        if self._sex2 is not None:
            self._age2 -= adjust

        self._preretirement_years = ceil(max(0, self._age_retirement - self._age) / self._params.time_period) * self._params.time_period

        key = (self._age, self.life_table.age_add, self._preretirement_years)
        self._compute_vital_stats(self._age, self._age2, self._preretirement_years, key)

        # Number of steps that can be taken.
        self._anticipated_episode_length = len(self._alive_single)
        while self._alive_single[self._anticipated_episode_length - 1] == 0:
            self._anticipated_episode_length -= 1

        # Create separate pre-retirement and retired life tables so can compute present values separately.
        self._life_table_preretirement = make_life_table(self._params.life_table, self._params.sex, death_age = self._age + self._preretirement_years,
            age_add = self._life_table.age_add, interpolate_q = self._params.life_table_interpolate_q)
            # Make age_add match regular life table.
        self._life_table2_preretirement = make_life_table(self._params.life_table, self._sex2, death_age = self._age2 + self._preretirement_years,
            age_add = self._life_table2.age_add, interpolate_q = self._params.life_table_interpolate_q) if self._sex2 else None

        self._couple = self._alive_single[0] == -1

        self._have_401k = bool(randint(int(self._params.have_401k_low), int(self._params.have_401k_high)))
        self._have_401k2 = bool(randint(int(self._params.have_401k2_low), int(self._params.have_401k2_high)))

        self._taxes_due = 0

        self._gamma = self.log_uniform(self._params.gamma_low, self._params.gamma_high)

        self._consume_charitable = self._params.consume_charitable

        self._date = self._params.life_table_date
        self._date_start = datetime.strptime(self._date, '%Y-%m-%d').date()
        self._cpi = 1

        self._stocks.reset()
        self._iid_bonds.reset()

        self._bonds_stepper.reset()

        self._episode_length = 0

        found = False
        last_rough_ce_estimate_individual = None
        for i in range(1000):

            self._parse_defined_benefits()
            retired = self._preretirement_years == 0

            for j in range(20):

                self._start_income_preretirement = self.log_uniform(self._params.income_preretirement_low, self._params.income_preretirement_high)
                self._start_income_preretirement2 = self.log_uniform(self._params.income_preretirement2_low, self._params.income_preretirement2_high)
                if self._params.income_preretirement_age_end != -1:
                    self._income_preretirement_years = max(0, self._params.income_preretirement_age_end - self._age)
                else:
                    self._income_preretirement_years = self._preretirement_years
                if self._couple:
                    if self._params.income_preretirement_age_end2 != -1:
                        self._income_preretirement_years2 = max(0, self._params.income_preretirement_age_end2 - self._age2)
                    else:
                        self._income_preretirement_years2 = self._preretirement_years
                else:
                    self._income_preretirement_years2 = 0
                self._income_preretirement = self._start_income_preretirement if self._income_preretirement_years > 0 else 0
                self._income_preretirement2 = self._start_income_preretirement2 if self._income_preretirement_years2 > 0 else 0

                p_tax_free_weight = uniform(self._params.p_tax_free_weight_low, self._params.p_tax_free_weight_high)
                p_tax_deferred_weight = uniform(self._params.p_tax_deferred_weight_low, self._params.p_tax_deferred_weight_high)
                p_taxable_stocks_weight = uniform(self._params.p_taxable_stocks_weight_low, self._params.p_taxable_stocks_weight_high) if self._params.stocks else 0
                p_taxable_real_bonds_weight = uniform(self._params.p_taxable_real_bonds_weight_low, self._params.p_taxable_real_bonds_weight_high) \
                    if self._params.real_bonds else 0
                p_taxable_nominal_bonds_weight = uniform(self._params.p_taxable_nominal_bonds_weight_low, self._params.p_taxable_nominal_bonds_weight_high) \
                    if self._params.nominal_bonds else 0
                p_taxable_iid_bonds_weight = uniform(self._params.p_taxable_iid_bonds_weight_low, self._params.p_taxable_iid_bonds_weight_high) \
                    if self._params.iid_bonds  else 0
                p_taxable_other_weight = uniform(self._params.p_taxable_other_weight_low, self._params.p_taxable_other_weight_high)
                total_weight = p_tax_free_weight + p_tax_deferred_weight + \
                    p_taxable_stocks_weight + p_taxable_real_bonds_weight + p_taxable_nominal_bonds_weight + p_taxable_iid_bonds_weight + p_taxable_other_weight
                p_weighted = self.log_uniform(self._params.p_weighted_low, self._params.p_weighted_high)
                if total_weight == 0:
                    assert p_weighted == 0
                    total_weight = 1
                self._p_tax_free = self.log_uniform(self._params.p_tax_free_low, self._params.p_tax_free_high) + \
                    p_weighted * p_tax_free_weight / total_weight
                self._p_tax_deferred = self.log_uniform(self._params.p_tax_deferred_low, self._params.p_tax_deferred_high) + \
                    p_weighted * p_tax_deferred_weight / total_weight
                taxable_assets: AssetAllocation
                taxable_assets = make_asset_allocation()
                if self._params.stocks:
                    taxable_assets.aa[STOCKS] = self.log_uniform(self._params.p_taxable_stocks_low, self._params.p_taxable_stocks_high) + \
                        p_weighted * p_taxable_stocks_weight / total_weight
                if self._params.real_bonds:
                    taxable_assets.aa[REAL_BONDS] = self.log_uniform(self._params.p_taxable_real_bonds_low, self._params.p_taxable_real_bonds_high) + \
                        p_weighted * p_taxable_real_bonds_weight / total_weight
                if self._params.nominal_bonds:
                    taxable_assets.aa[NOMINAL_BONDS] = self.log_uniform(self._params.p_taxable_nominal_bonds_low, self._params.p_taxable_nominal_bonds_high) + \
                        p_weighted * p_taxable_nominal_bonds_weight / total_weight
                if self._params.iid_bonds:
                    taxable_assets.aa[IID_BONDS] = self.log_uniform(self._params.p_taxable_iid_bonds_low, self._params.p_taxable_iid_bonds_high) + \
                        p_weighted * p_taxable_iid_bonds_weight / total_weight
                taxable_assets_aa_other = self.log_uniform(self._params.p_taxable_other_low, self._params.p_taxable_other_high) + \
                    p_weighted * p_taxable_other_weight / total_weight
                self._p_taxable = taxable_assets.sum() + taxable_assets_aa_other

                taxable_basis: AssetAllocation
                taxable_basis = make_asset_allocation()
                if self._params.stocks:
                    assert not self._params.p_taxable_stocks_basis or not self._params.p_taxable_stocks_basis_fraction_high
                    taxable_basis.aa[STOCKS] = self._params.p_taxable_stocks_basis + \
                        uniform(self._params.p_taxable_stocks_basis_fraction_low,
                                self._params.p_taxable_stocks_basis_fraction_high) * taxable_assets.aa[STOCKS]
                if self._params.real_bonds:
                    assert not self._params.p_taxable_real_bonds_basis or not self._params.p_taxable_real_bonds_basis_fraction_high
                    taxable_basis.aa[REAL_BONDS] = self._params.p_taxable_real_bonds_basis + \
                        uniform(self._params.p_taxable_real_bonds_basis_fraction_low,
                                self._params.p_taxable_real_bonds_basis_fraction_high) * taxable_assets.aa[REAL_BONDS]
                if self._params.nominal_bonds:
                    assert not self._params.p_taxable_nominal_bonds_basis or not self._params.p_taxable_nominal_bonds_basis_fraction_high
                    taxable_basis.aa[NOMINAL_BONDS] = self._params.p_taxable_nominal_bonds_basis + \
                        uniform(self._params.p_taxable_nominal_bonds_basis_fraction_low,
                                self._params.p_taxable_nominal_bonds_basis_fraction_high) * taxable_assets.aa[NOMINAL_BONDS]
                if self._params.iid_bonds:
                    assert not self._params.p_taxable_iid_bonds_basis or not self._params.p_taxable_iid_bonds_basis_fraction_high
                    taxable_basis.aa[IID_BONDS] = self._params.p_taxable_iid_bonds_basis + \
                        uniform(self._params.p_taxable_iid_bonds_basis_fraction_low,
                                self._params.p_taxable_iid_bonds_basis_fraction_high) * taxable_assets.aa[IID_BONDS]
                assert not self._params.p_taxable_other_basis or not self._params.p_taxable_other_basis_fraction_high
                taxable_basis_aa_other = self._params.p_taxable_other_basis + \
                    uniform(self._params.p_taxable_other_basis_fraction_low,
                        self._params.p_taxable_other_basis_fraction_high) * taxable_assets_aa_other
                cg_init = taxable_assets_aa_other - taxable_basis_aa_other
                self._taxes.reset(taxable_assets, taxable_basis, cg_init)

                assert not self._params.consume_preretirement or not self._params.consume_preretirement_income_ratio_high
                income_preretirement = self._income_preretirement + self._income_preretirement2
                regular_tax, capital_gains_tax, _ = self._taxes.calculate_taxes(income_preretirement, 0, 0, 0, 0, not self._couple)
                income_preretirement -= regular_tax + capital_gains_tax
                self._consume_preretirement = self._params.consume_preretirement + \
                    uniform(self._params.consume_preretirement_income_ratio_low, self._params.consume_preretirement_income_ratio_high) * income_preretirement

                self._pre_calculate_wealth(growth_rate = 1.05) # Use a typical stock growth rate for determining expected consume range.
                ce_estimate_ok = self._params.consume_floor <= self._rough_ce_estimate_individual <= self._params.consume_ceiling

                self._pre_calculate_wealth(growth_rate = 1) # By convention use no growth for determining guaranteed income bucket.
                preretirement_ok = self._raw_preretirement_income_wealth + self._p_wealth_pretax >= 0
                    # Very basic sanity check only. Ignores taxation.

                try:
                    gi_fraction = self._retired_income_wealth_pretax / self._net_wealth_pretax
                except ZeroDivisionError:
                    gi_fraction = 1
                gi_ok = self._params.gi_fraction_low <= gi_fraction <= self._params.gi_fraction_high

                if ce_estimate_ok and preretirement_ok and gi_ok or \
                    i == 1 and j == 1 and self._rough_ce_estimate_individual == last_rough_ce_estimate_individual:
                        # ce estimates equal implies fixed parameter values with very high probability. No point in repeatedly retrying.
                    found = True
                    break

                if i == 0 and j == 0:
                    last_rough_ce_estimate_individual = self._rough_ce_estimate_individual

            if found:
                break

        if not ce_estimate_ok:
            self._warn('Expected consumption falls outside model training range.')
        if not preretirement_ok:
            self._warn('Insufficient pre-retirement wages and wealth to support pre-retirement consumption.')
        if not gi_ok:
            self._warn('Net existing guaranteed income in retirement falls outside model training range.')

        #print('wealth:', self._net_wealth_pretax, self._raw_preretirement_income_wealth, self._retired_income_wealth_pretax, self._p_wealth)

        self._pre_calculate()

        self._set_reward_level()

        self._policy = make_policy(self, self._params)

        self._prev_asset_allocation = make_asset_allocation()
        self._prev_taxable_assets = taxable_assets
        self._prev_real_spias_purchase = 0.0
        self._prev_nominal_spias_purchase = 0.0
        self._prev_consume_rate = 0.0
        self._prev_reward = 0.0

        if self._params.verbose:
            print()
            print('Age add:', self._life_table.age_add)
            print('Guaranteed income fraction:', gi_fraction)
            self.render()

        return self._observe()

    def _set_reward_level(self):

        # Taking advantage of iso-elasticity, generalizability will be better if rewards are independent of initial portfolio size.
        #
        # Scale returned rewards.
        # This is helpful for PPO, which clips the value function advantage at 10.0.
        # A rough estimate of a minimal consumption level is 0.3 times a consumption estimate.
        # Having rewards for a minimal consumption level of -0.2 should ensure rewards rarely exceed -10.0, allowing the value function to converge quickly.
        consumption_estimate = self._ce_estimate_individual
        if consumption_estimate == 0:
            self._warn('Using a consumption scale that is incompatible with the default consumption scale.')
            consumption_estimate = 1
        self._consume_scale = consumption_estimate
        consume_charitable = self._params.consume_charitable
        if self._couple:
            consume_charitable /= 1 + self._params.consume_additional # Reward is computed per person with double weight for couple.
        self._utility = make_utility(self._gamma, 0.3 * consumption_estimate,
            consume_charitable, self._params.consume_charitable_utility_factor, self._params.consume_charitable_gamma, self._params.consume_charitable_discount_rate)
        #_, self._reward_expect = self._raw_reward(consumption_estimate)
        #_, self._reward_zero_point = self._raw_reward(self._params.reward_zero_point_factor * consumption_estimate)
        self._reward_scale = 0.2

    def encode_direct_action(self, consume_fraction, *, real_spias_fraction = 0, nominal_spias_fraction = 0,
        real_bonds_duration = None, nominal_bonds_duration = None, **kwargs):

        return (consume_fraction, real_spias_fraction, nominal_spias_fraction, make_asset_allocation(**kwargs), real_bonds_duration, nominal_bonds_duration)

    def _decode_action(self, action_or_list, spare_asset_allocation):

        if len(action_or_list) == 1:
            action_np = action_or_list[0] # Work around spinup returning a single element list of actions.
        else:
            action_np = action_or_list

        if isnan(action_np[0]):
            assert False, 'Action is nan.' # Detect bug in code interacting with model before it messes things up.

        if not self._params.action_space_unbounded:
            # Spinup SAC, and possibly other algorithms return bogus action values like -1.0000002 and 1.0000001. Possibly a bug in tf.tanh.
            clipped_action = np.clip(action_np, -1, 1)
            assert np.allclose(action_np, clipped_action, rtol = 0, atol= 3e-7), 'Out of range action: ' + str(action_np)
            action_np = clipped_action

        action: list
        try:
            action = action_np.tolist() # De-numpify if required.
        except AttributeError:
            action = action_np

        i: cython.int; consume_action: cython.double; spias_action: cython.double; real_spias_action: cython.double; stocks_action: cython.double
        real_bonds_action: cython.double; real_bonds_duration_action: cython.double
        nominal_bonds_action: cython.double; nominal_bonds_duration_action: cython.double; iid_bonds_action: cython.double
        i = 0
        consume_action = action[i]; i += 1
        if self._params.real_spias or self._params.nominal_spias:
            spias_action = action[i]; i += 1
            if self._params.real_spias and self._params.nominal_spias:
                real_spias_action = action[i]; i += 1
        if self._params.stocks:
            stocks_action = action[i]; i += 1
        if self._params.real_bonds:
            real_bonds_action = action[i]; i += 1
            if self._params.real_bonds_duration == -1 or self._params.real_bonds_duration_action_force:
                real_bonds_duration_action = action[i]; i += 1
        if self._params.nominal_bonds:
            nominal_bonds_action = action[i]; i += 1
            if self._params.nominal_bonds_duration == -1 or self._params.nominal_bonds_duration_action_force:
                nominal_bonds_duration_action = action[i]; i += 1
        if self._params.iid_bonds:
            iid_bonds_action = action[i]; i += 1
            if self._params.iid_bonds_duration_action_force:
                _ = action[i]; i += 1
        assert i == len(action)

        def safe_atanh(x):
            try:
                return atanh(x)
            except ValueError:
                assert abs(x) == 1, 'Invalid value to atanh.'
                return copysign(10, x) # Change to 20 if using float64.

        if self._params.action_space_unbounded:
            consume_action = tanh(consume_action / self._params.consume_action_scale_back)
            if self._spias_ever:
                spias_action = tanh(spias_action / 2)
                    # Decreasing initial volatility of spias_action is observed to improve run to run mean certainty equivalent (gamma=6).
                    # Increasing initial volatility of spias_action is observed to improve run to run mean certainty equivalent (gamma=1.5).
                    #
                    # real spias, p_tax_free=2e6, age_start=65, life_expectancy_add=3, bucket-le ensemble results:
                    #                gamma=1.5   gamma=6
                    # tanh(action)     134304    106032
                    # tanh(action/2)   132693    112684
                    # tanh(action/5)   128307    110570
                if self._params.real_spias and self._params.nominal_spias:
                    real_spias_action = tanh(real_spias_action)
            if self._params.real_bonds and self._params.real_bonds_duration == -1:
                real_bonds_duration_action = tanh(real_bonds_duration_action)
            if self._params.nominal_bonds and self._params.nominal_bonds_duration == -1:
                nominal_bonds_duration_action = tanh(nominal_bonds_duration_action)
        else:
            if self._params_stocks:
                stocks_action = safe_atanh(stocks_action)
            if self._params.real_bonds:
                real_bonds_action = safe_atanh(real_bonds_action)
            if self._params.nominal_bonds:
                nominal_bonds_action = safe_atanh(nominal_bonds_action)
            if self._params.iid_bonds:
                iid_bonds_action = safe_atanh(iid_bonds_action)

        consume_action = (consume_action + 1) / 2
        # Define a consume floor and consume ceiling outside of which we won't consume.
        # The mid-point acts as a hint as to the initial consumption values to try.
        consume_estimate = self._consume_fraction_estimate
        consume_floor = 0.1 * consume_estimate
        consume_ceil = 1.9 * consume_estimate
        consume_fraction = consume_floor + (consume_ceil - consume_floor) * consume_action
        try:
            consume_fraction *= self._net_wealth / self._p_plus_income
        except ZeroDivisionError:
            consume_fraction = float('inf')
        consume_fraction *= 1 + self._params.rl_consume_bias

        consume_fraction = max(1e-6, min(consume_fraction, 1 / self._params.time_period))
            # Don't allow consume_fraction of zero as have problems with -inf utility.

        if self._spias:

            if self._spias_required:
                spias_action = 1
            elif self._params.spias_partial:
                spias_action = (spias_action + 1) / 2
            else:
                spias_action = 1 if spias_action > 0 else 0

            # Try and make it easy to learn the optimal amount of guaranteed income,
            # so things function well with differing current amounts of guaranteed income.
            try:
                current_spias_fraction_estimate = self._retired_income_wealth / self._net_wealth
            except ZeroDivisionError:
                current_spias_fraction_estimate = 1
            current_spias_fraction_estimate = max(0, min(current_spias_fraction_estimate, 1))
            if spias_action - current_spias_fraction_estimate < self._params.spias_min_purchase_fraction:
                spias_fraction = 0
            elif spias_action > 1 - self._params.spias_min_purchase_fraction:
                spias_fraction = 1
            else:
                try:
                    spias_fraction = (spias_action - current_spias_fraction_estimate) * self._net_wealth / self._p_plus_income
                except ZeroDivisionError:
                    spias_fraction = 0
                spias_fraction = max(0, min(spias_fraction, 1))

            real_spias_fraction = spias_fraction if self._params.real_spias else 0
            if self._params.real_spias and self._params.nominal_spias:
                real_spias_fraction *= (real_spias_action + 1) / 2
            nominal_spias_fraction = spias_fraction - real_spias_fraction

            spias_purchase = spias_fraction * self._p_plus_income

        else:

            spias_purchase = 0

        if not (self._spias and self._params.real_spias):
            real_spias_fraction = 0
        if not (self._spias and self._params.nominal_spias):
            nominal_spias_fraction = 0

        # A number of different methods of computing the asset allocation were attempted.
        # Reported results are for iid returns, no tax, no SPIAs, gi=20e3, gamma=6 based on the CE distribution of 10 trained models.
        # Note that standard error values are much smaller for lower p values. Hence the performance for high p values is what counts.
        #
        # stocks_action, iid_bonds_action = softmax(stocks_action, iid_bonds_action)
        # stocks_curvature_fraction = 0.5
        #    Baseline case.
        #
        # stocks_action = (1 + tanh(stocks_action)) / 2
        # stocks_curvature_fraction = 0.5
        #    p=2e5: outperforms by 1 standard error
        #    p=5e5: same
        #    p=1e6: underperforms by 1 standard error
        #    p=2e6: underperforms by 1 standard error
        #    p=5e6: underperforms by 1 standard error
        #    Weakly inferior and doesn't generalize to more than two asset classes.
        #
        # stocks_action, iid_bonds_action = softmax(stocks_action, iid_bonds_action)
        # stocks_curvature_fraction = 0.0
        #    p=2e5: underperforms by 10 standard error
        #    p=5e5: underperforms by 1 standard error
        #    p=1e6: outperforms by 0.5 standard error
        #    p=2e6: same
        #    p=5e6: underperforms by 0.5 standard error
        #    Inferior at both extremes.

        # Softmax the asset allocations when guaranteed_income is zero.
        maximum = max(
            stocks_action if self._params.stocks else float('-inf'),
            real_bonds_action if self._params.real_bonds else float('-inf'),
            nominal_bonds_action if self._params.nominal_bonds else float('-inf'),
            iid_bonds_action if self._params.iid_bonds else float('-inf'),
        )
        stocks_action = self.e ** (stocks_action - maximum) if self._params.stocks else 0
        real_bonds_action = self.e ** (real_bonds_action - maximum) if self._params.real_bonds else 0
        nominal_bonds_action = self.e ** (nominal_bonds_action - maximum) if self._params.nominal_bonds else 0
        iid_bonds_action = self.e ** (iid_bonds_action - maximum) if self._params.iid_bonds else 0
        total = stocks_action + real_bonds_action + nominal_bonds_action + iid_bonds_action
        stocks_action /= total
        real_bonds_action /= total
        nominal_bonds_action /= total
        iid_bonds_action /= total

        try:
            wealth_ratio = (self._retired_income_wealth + self._preretirement_income_wealth + spias_purchase) / max(0, self._p_wealth - spias_purchase)
        except ZeroDivisionError:
            wealth_ratio = float('inf')
        wealth_ratio = min(wealth_ratio, 1e100) # Cap so that not calculating with inf.

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
        alloc: cython.double
        alloc = 1.0
        stocks = max(0.0, min(stocks_action + stocks_curvature * wealth_ratio + self._params.rl_stocks_bias, alloc)) if self._params.stocks else 0
        alloc -= stocks
        real_bonds = max(0.0, min(real_bonds_action + real_bonds_curvature * wealth_ratio, alloc)) if self._params.real_bonds else 0
        alloc -= real_bonds
        nominal_bonds = max(0.0, min(nominal_bonds_action + nominal_bonds_curvature * wealth_ratio, alloc)) if self._params.nominal_bonds else 0
        alloc -= nominal_bonds
        iid_bonds = max(0.0, min(iid_bonds_action + iid_bonds_curvature * wealth_ratio, alloc)) if self._params.iid_bonds else 0
        alloc -= iid_bonds
        if self._params.iid_bonds:
            iid_bonds += alloc
        elif self._params.nominal_bonds:
            nominal_bonds += alloc
        elif self._params.real_bonds:
            real_bonds += alloc
        else:
            stocks += alloc

        asset_allocation: AssetAllocation
        asset_allocation = spare_asset_allocation
        if self._params.stocks:
            asset_allocation.aa[STOCKS] = stocks
        if self._params.real_bonds:
            asset_allocation.aa[REAL_BONDS] = real_bonds
        if self._params.nominal_bonds:
            asset_allocation.aa[NOMINAL_BONDS] = nominal_bonds
        if self._params.iid_bonds:
            asset_allocation.aa[IID_BONDS] = iid_bonds

        buckets: cython.int; quantized: cython.double
        buckets = 100 # Quantize duration so that bonds.py:_log_p() _sr_cache can be utilized when sample returns.

        if self._params.real_bonds:
            if self._params.real_bonds_duration == -1:
                quantized = int((real_bonds_duration_action + 1) / 2 * buckets + 0.5)
                quantized /= buckets
                real_bonds_duration = self._params.time_period + (self._params.real_bonds_duration_max - self._params.time_period) * quantized
            else:
                real_bonds_duration = self._params.real_bonds_duration
        else:
            real_bonds_duration = None

        if self._params.nominal_bonds:
            if self._params.nominal_bonds_duration == -1:
                quantized = int((nominal_bonds_duration_action + 1) / 2 * buckets + 0.5)
                quantized /= buckets
                nominal_bonds_duration = self._params.time_period + (self._params.nominal_bonds_duration_max - self._params.time_period) * quantized
            else:
                nominal_bonds_duration = self._params.nominal_bonds_duration
        else:
            nominal_bonds_duration = None

        return consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration

    @cython.locals(consume_rate = cython.double)
    def _raw_reward(self, consume_rate):

        reward_consume: cython.double; reward_weight: cython.double; reward_value: cython.double
        if self._couple:
            reward_consume = consume_rate / (1 + self._params.consume_additional)
            reward_weight = 2 * self._params.time_period
        else:
            reward_consume = consume_rate
            reward_weight = self._alive_single[self._episode_length]
            reward_weight *= self._params.time_period
        reward_value = self._utility.utility(reward_consume, self._episode_length * self._params.time_period)

        return reward_weight, reward_consume, reward_value

    @cython.locals(consume_fraction = cython.double, real_spias_fraction = cython.double, nominal_spias_fraction = cython.double)
    def _spend(self, consume_fraction, real_spias_fraction, nominal_spias_fraction):

        # Sanity check.
        consume_fraction_period = consume_fraction * self._params.time_period
        assert 0 <= consume_fraction_period <= 1

        p: cython.double; consume: cython.double; welfare: cython.double
        p = self._p_plus_income
        if self._age < self._age_retirement:
            consume = self._consume_preretirement * self._params.time_period
            welfare = 0
        else:
            #consume_annual = consume_fraction * p
            consume = consume_fraction_period * max(p, 0)
            welfare = (1 + self._params.consume_additional if self._couple else 1) * self._params.welfare
            consume = max(consume, welfare)
        p -= consume
        if p < 0:
            p = min(p + welfare, 0)
            if p < 0:
                self._warn('Portfolio is sometimes negative.', timestep_ok_fraction = 1e-3)

        p_taxable: cython.double; p_tax_deferred: cython.double; p_tax_free: cython.double
        p_taxable = self._p_taxable + (p - self._p_sum)
        p_tax_deferred = self._p_tax_deferred + min(p_taxable, 0)
        # Required Minimum Distributions (RMDs) not considered. Would need separate p_tax_deferred for each spouse.
        p_tax_free = self._p_tax_free + min(p_tax_deferred, 0)
        p_taxable = max(p_taxable, 0)
        p_tax_deferred = max(p_tax_deferred, 0)
        if p_tax_free < 0:
            p_negative = p_tax_free
            p = 0
            p_tax_free = 0
        else:
            p_negative = 0
        delta_p_tax_deferred = self._p_tax_deferred - p_tax_deferred

        if self._params.income_preretirement_taxable:
            retirement_contribution1: cython.double; retirement_contribution2: cython.double
            retirement_contribution1 = self._taxes.contribution_limit(self._income_preretirement, self._age, self._have_401k) \
                if self._income_preretirement > 0 else 0
            retirement_contribution2 =  self._taxes.contribution_limit(self._income_preretirement2, self._age2, self._have_401k2) \
                if self._income_preretirement2 > 0 else 0
            retirement_contribution = min(retirement_contribution1 + retirement_contribution2, p_taxable)
            p_taxable -= retirement_contribution
            p_tax_deferred += retirement_contribution
        else:
            retirement_contribution = 0
            net_income_preretirement = self._income_preretirement + self._income_preretirement2 - self._consume_preretirement
            net_income_preretirement = max(0, net_income_preretirement)
            p_taxable -= net_income_preretirement
            p_tax_free += net_income_preretirement

        real_spias_fraction *= self._params.time_period
        nominal_spias_fraction *= self._params.time_period
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

        regular_income = self._gi_regular - retirement_contribution + delta_p_tax_deferred
        if regular_income < 0:
            if regular_income < -1e-12 * (self._gi_regular + self._p_tax_deferred):
                self._warn('Negative regular income observed.', 'regular income:', regular_income, timestep_ok_fraction = 1e-3)
                    # Possible if taxable real SPIA non-taxable amount exceeds payout due to deflation.
            regular_income = 0
        social_security = self._gi_social_security
        social_security = min(regular_income, social_security)

        taxable_spias = real_taxable_spias + nominal_taxable_spias
        if taxable_spias > 0:
            # Ensure leave enough taxable assets to cover any taxes due.
            max_capital_gains = self._taxes.unrealized_gains()
            if max_capital_gains > 0:
                regular_tax: cython.double; capital_gains_tax: cython.double; regular_tax_no_cg: cython.double; capital_gains_tax_no_cg: cython.double
                regular_tax, capital_gains_tax, _ = self._taxes.calculate_taxes(regular_income, social_security, max_capital_gains, 0, 0, not self._couple)
                regular_tax_no_cg, capital_gains_tax_no_cg, _ = self._taxes.calculate_taxes(regular_income, social_security, 0, 0, 0, not self._couple)
                assert capital_gains_tax_no_cg == 0
                max_capital_gains_taxes = (regular_tax + capital_gains_tax) - (regular_tax_no_cg + capital_gains_tax_no_cg)
                new_taxable_spias = min(taxable_spias, max(0, p_taxable - max_capital_gains_taxes))
                real_taxable_spias *= new_taxable_spias / taxable_spias
                nominal_taxable_spias *= new_taxable_spias / taxable_spias

        p_taxable -= real_taxable_spias + nominal_taxable_spias
        if p_taxable < 0:
            assert p_taxable > -1e-12 * self._p_plus_income
            p_taxable = 0

        return p_tax_free, p_tax_deferred, p_taxable, p_negative, regular_income, social_security, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias

    def _add_spias(self, inflation_adjustment, tax_free_spias, tax_deferred_spias, taxable_spias):

        bonds = self._bonds.real if inflation_adjustment == 'cpi' else self._bonds.corporate
        adjustment = 0 if inflation_adjustment == 'cpi' else inflation_adjustment
        payout_delay = self._params.time_period
        payout_fraction = 1 / (1 + self._params.consume_additional)
        spia = self._pricing_spia(bonds, adjustment, payout_delay, payout_fraction)

        owner = 'self' if self._couple or not self._only_alive2 else 'spouse'
        age = self._age if owner == 'self' else self._age2
        start = age + payout_delay
        mwr = self._params.real_spias_mwr if inflation_adjustment == 'cpi' else self._params.nominal_spias_mwr
        unit_payout = spia.payout(1, mwr = mwr) / self._params.time_period

        if tax_free_spias > 0:
            self._add_db(owner = owner, start = start, payout = tax_free_spias * unit_payout, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'tax_free')
        if tax_deferred_spias > 0:
            self._add_db(owner = owner, start = start, payout = tax_deferred_spias * unit_payout, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'tax_deferred')
        if taxable_spias > 0:
            exclusion_period = ceil(self._life_expectancy_both[self._episode_length] + self._life_expectancy_one[self._episode_length])
                # Highly imperfect, but total exclusion amount will be correct.
            if inflation_adjustment in ('cpi', 0):
                exclusion_amount = taxable_spias / exclusion_period
            else:
                exclusion_amount = taxable_spias * inflation_adjustment / ((1 + inflation_adjustment) ** exclusion_period - 1)

            self._add_db(owner = owner, start = start, payout = taxable_spias * unit_payout, inflation_adjustment = inflation_adjustment, joint = True, \
                payout_fraction = payout_fraction, source_of_funds = 'taxable', exclusion_period = exclusion_period, exclusion_amount = exclusion_amount)

    tax_efficient_order = (STOCKS, IID_BONDS, NOMINAL_BONDS, REAL_BONDS)
    tax_inefficient_order = tuple(reversed(tax_efficient_order))

    @cython.locals(p_tax_free = cython.double, p_tax_deferred = cython.double, p_taxable = cython.double,
        tax_deferred_tax_rate = cython.double, taxable_tax_rate = cython.double)
    def _allocate_aa(self, p_tax_free, p_tax_deferred, p_taxable, tax_deferred_tax_rate, taxable_tax_rate, target_asset_allocation):

        asset_allocation: AssetAllocation
        asset_allocation = target_asset_allocation

        if not self._params.tax_class_aware_asset_allocation:
            tax_deferred_tax_rate = 0
            taxable_tax_rate = 0

        p = p_tax_free + (1 - tax_deferred_tax_rate) * p_tax_deferred + (1 - taxable_tax_rate) * p_taxable
        tax_free_remaining = p_tax_free
        taxable_remaining = p_taxable

        ac: cython.int; aa: cython.double; alloc: cython.double
        for ac in Fin.tax_inefficient_order:
            if asset_allocation.aa[ac] is not None:
                aa = asset_allocation.aa[ac]
                alloc = min(p * aa, tax_free_remaining)
                self._tax_free_assets.aa[ac] = alloc
                tax_free_remaining = max(tax_free_remaining - alloc, 0)

        for ac in Fin.tax_efficient_order:
            if asset_allocation.aa[ac] is not None:
                aa = asset_allocation.aa[ac]
                alloc = min(p * aa / (1 - taxable_tax_rate), taxable_remaining)
                self._taxable_assets.aa[ac] = alloc
                taxable_remaining = max(taxable_remaining - alloc, 0)

        for ac in Fin.tax_efficient_order:
            if asset_allocation.aa[ac] is not None:
                tax_free: cython.double; taxable: cython.double
                aa = asset_allocation.aa[ac]
                tax_free = self._tax_free_assets.aa[ac]
                taxable = self._taxable_assets.aa[ac]
                self._tax_deferred_assets.aa[ac] = max((p * aa - tax_free - (1 - taxable_tax_rate) * taxable) / (1 - tax_deferred_tax_rate), 0)

    def _normalize_aa(self, assets, p_value):
        aa: AssetAllocation
        aa = assets
        s = aa.sum()
        if p_value > 0 and s > 0:
            return make_asset_allocation(**dict((ac, v / s) for ac, v in zip(assets.classes(), assets.as_list())))
                # Cython gives a runtime type error if use {ac: v /s for ...} above.
        else:
            return None

    empty_info = {}

    def step(self, action):

        if not self._init_done:
            self._reset()

        if self._direct_action:
            decoded_action = action
        elif action is None:
            decoded_action = None
        else:
            decoded_action = self._decode_action(action, self._prev_asset_allocation)
        policified_action = self._policy.policy(decoded_action)
        consume_fraction: cython.double; asset_allocation: AssetAllocation
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = policified_action

        s: cython.double
        s = asset_allocation.sum()
        assert abs(s - 1) < 1e-12

        p_tax_free: cython.double; p_tax_deferred: cython.double; p_taxable: cython.double; p_negative: cython.double
        regular_income: cython.double; social_security: cython.double; consume: cython.double; retirement_contribution: cython.double
        real_tax_free_spias: cython.double; real_tax_deferred_spias: cython.double; real_taxable_spias: cython.double
        nominal_tax_free_spias: cython.double; nominal_tax_deferred_spias: cython.double; nominal_taxable_spias: cython.double

        p_tax_free, p_tax_deferred, p_taxable, p_negative, regular_income, social_security, consume, retirement_contribution, \
            real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias = \
            self._spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)
        consume_rate = consume / self._params.time_period
        real_spias_purchase = real_tax_free_spias + real_tax_deferred_spias + real_taxable_spias
        nominal_spias_purchase = nominal_tax_free_spias + nominal_tax_deferred_spias + nominal_taxable_spias

        if real_spias_purchase > 0:
            self._add_spias('cpi', real_tax_free_spias, real_tax_deferred_spias, real_taxable_spias)

        if nominal_spias_purchase > 0:
            self._add_spias(self._params.nominal_spias_adjust, nominal_tax_free_spias, nominal_tax_deferred_spias, nominal_taxable_spias)

        self._allocate_aa(p_tax_free, p_tax_deferred, p_taxable, self._regular_tax_rate, self._capital_gains_tax_rate, asset_allocation)

        inflation: cython.double
        inflation = self._bonds.inflation.inflation()
        self._cpi *= inflation

        new_p_tax_free: cython.double; new_p_tax_deferred: cython.double; new_p_taxable: cython.double
        new_p_tax_free = 0
        new_p_tax_deferred = 0
        new_p_taxable = 0
        ac: cython.int
        for ac, v in enumerate(asset_allocation.aa):

            ret: cython.double
            if v is None:
                continue
            elif ac == STOCKS:
                ret = self._stocks.sample()
                dividend_yield = self._params.dividend_yield_stocks
                qualified_dividends = self._params.qualified_dividends_stocks
            else:
                dividend_yield = self._params.dividend_yield_bonds
                qualified_dividends = self._params.qualified_dividends_bonds
                if ac == REAL_BONDS:
                    ret = self._bonds.real.sample(real_bonds_duration)
                elif ac == NOMINAL_BONDS:
                    ret = self._bonds.nominal.sample(nominal_bonds_duration)
                elif ac == IID_BONDS:
                    ret = self._iid_bonds.sample()
                else:
                    assert False

            asset_tax_free: cython.double; asset_tax_deferred: cython.double; asset_taxable: cython.double; asset_prev_taxable: cython.double
            asset_tax_free = self._tax_free_assets.aa[ac]
            asset_tax_deferred = self._tax_deferred_assets.aa[ac]
            asset_taxable = self._taxable_assets.aa[ac]
            asset_prev_taxable = self._prev_taxable_assets.aa[ac]

            new_p_tax_free += asset_tax_free * ret
            new_p_tax_deferred += asset_tax_deferred * ret
            new_taxable = asset_taxable * ret
            new_p_taxable += new_taxable
            taxable_buy_sell = asset_taxable - asset_prev_taxable
            self._taxes.buy_sell(ac, taxable_buy_sell, new_taxable, ret, dividend_yield, qualified_dividends)
            self._taxable_assets.aa[ac] = new_taxable

        if p_negative < 0:
            new_p_taxable += p_negative * (1 + self._params.credit_rate) ** self._params.time_period

        self._p_tax_free = new_p_tax_free
        self._p_tax_deferred = new_p_tax_deferred
        self._p_taxable = new_p_taxable

        charitable_contributions = max(0, consume_rate - self._consume_charitable) * self._params.consume_charitable_tax_deductability

        taxes: cython.double
        taxes = self._taxes.tax(regular_income, social_security, charitable_contributions, not self._couple, inflation) - self._taxes_paid
        self._taxes_due += taxes
        # if self._age_retirement - self._params.time_period <= self._age < self._age_retirement:
        #     # Forgive taxes due that can't immediately be repaid upon retirement.
        #     # Otherwise when training if have no investment assets at retirement (consumption greater than income) we would be expected to pay the
        #     # accumulated taxes which could be substantially more than the guaranteed income.
        #     # Instead we forgive these amounts.
        #     ability_to_pay = self._p_sum
        #     self._taxes_due = min(self._taxes_due, ability_to_pay)

        alive0: cython.double; alive1: cython.double
        alive0 = self._alive_single[self._episode_length]
        if alive0 == -1:
            alive0 = 1
        alive1 = self._alive_single[self._episode_length + 1]
        if alive1 == -1:
            alive1 = 1
        estate_weight = alive0 - alive1
        estate_value = max(0, new_p_tax_free + new_p_tax_deferred + new_p_taxable - self._taxes_due) # Assume death occurs at end of period.
            # Ignore future taxation of new_p_tax_deferred; depends upon heirs tax bracket.

        reward_weight: cython.double; reward_consume: cython.double; reward_value: cython.double
        if self._age < self._age_retirement:
            reward_weight = 0
            reward_consume = 0
            reward_value = 0
            reward = 0.0
        else:
            reward_weight, reward_consume, reward_value = self._raw_reward(consume_rate)
            reward_unclipped = reward_weight * self._reward_scale * reward_value
            if isinf(reward_unclipped):
                self._warn('Infinite reward.')
            elif not - self._params.reward_warn <= reward_unclipped <= self._params.reward_warn:
                self._warn('Extreme reward observed.', 'age, consume, reward:', self._age, consume_rate, reward_unclipped)
            reward = min(max(reward_unclipped, - self._params.reward_clip), self._params.reward_clip)
            if reward != reward_unclipped:
                self._warn('Reward clipped.', 'age, consume, reward:', self._age, consume_rate, reward_unclipped)

        if  self._info_rewards:

            info = {
                'age': self._age,
                'reward_weight': reward_weight,
                'reward_consume': reward_consume,
                'reward_value': reward_value,
                'estate_weight': estate_weight,
                'estate_value': estate_value,
            }

        elif self._info_rollouts or self._info_strategy:

            info = {}

        else:

            # Avoid creating a dict, and confirm trainer isn't making use of the empty dict.
            info = Fin.empty_info
            assert not info

        if self._info_rollouts:

            info = dict(info, **{
                'age': self._age,
                'alive_count': self._alive_count[self._episode_length],
                'total_guaranteed_income': self._gi_total,
                'portfolio_wealth_pretax': self._p_wealth_pretax,
                'consume': consume_rate,
                'real_spias_purchase': real_spias_purchase if self._params.real_spias and self._spias else None,
                'nominal_spias_purchase': nominal_spias_purchase if self._params.nominal_spias and self._spias else None,
                'asset_allocation': asset_allocation.clone(),
            })

        if self._info_strategy:

            info = dict(info, **{
                'consume': consume_rate,
                'asset_allocation': asset_allocation.clone(),
                'asset_allocation_tax_free': self._normalize_aa(self._tax_free_assets, p_tax_free),
                'asset_allocation_tax_deferred': self._normalize_aa(self._tax_deferred_assets, p_tax_deferred),
                'asset_allocation_taxable': self._normalize_aa(self._taxable_assets, p_taxable),
                'retirement_contribution': retirement_contribution / self._params.time_period \
                    if self._income_preretirement_years > 0 or self._income_preretirement_years2 > 0 else None,
                'real_spias_purchase': real_spias_purchase if self._params.real_spias and self._spias else None,
                'nominal_spias_purchase': nominal_spias_purchase if self._params.nominal_spias and self._spias else None,
                'nominal_spias_adjust': self._params.nominal_spias_adjust if self._params.nominal_spias and self._spias else None,
                'pv_spias_purchase': real_spias_purchase + nominal_spias_purchase - (real_tax_deferred_spias + nominal_tax_deferred_spias) * self._regular_tax_rate,
                'real_bonds_duration': real_bonds_duration,
                'nominal_bonds_duration': nominal_bonds_duration,
                'pv_preretirement_income': self._preretirement_income_wealth if self._preretirement_years > 0 else None,
                'pv_retired_income': self._retired_income_wealth,
                'pv_future_taxes': self._pv_taxes,
                'portfolio_wealth': self._p_wealth,
            })

        self._step()
        self._bonds_stepper.step()

        alive_single: cython.double; done: cython.bint
        alive_single = self._alive_single[self._episode_length]
        done = alive_single == 0.0
        if done:
            # Return any valid value.
            if self._params.observation_space_ignores_range:
                observation = np.repeat(-1, len(self._observation_space_low)).astype(np.float32)
            else:
                observation = np.array(self._observation_space_low, dtype = np.float32)
        else:
            self._pre_calculate()
            observation = self._observe()

        self._prev_asset_allocation = asset_allocation
        swap = self._prev_taxable_assets
        self._prev_taxable_assets = self._taxable_assets
        self._taxable_assets = swap # Spare asset allocation object ready for next iteration.
        self._prev_real_spias_purchase = real_spias_purchase
        self._prev_nominal_spias_purchase = nominal_spias_purchase
        self._prev_consume_rate = consume_rate
        self._prev_reward = reward

        # Variables used by policy decison rules:
        self._prev_ret = ret
        self._prev_inflation = inflation

        if self._params.verbose:
            self.render()

        return observation, reward, done, info

    @cython.locals(steps = cython.int, force_family_unit = cython.bint, forced_family_unit_couple = cython.bint)
    def _step(self, steps = 1, force_family_unit = False, forced_family_unit_couple = False):

        self._age += steps
        self._age2 += steps

        self._preretirement_years = max(0, self._preretirement_years - steps)
        self._income_preretirement_years = max(0, self._income_preretirement_years - steps)
        self._income_preretirement_years2 = max(0, self._income_preretirement_years2 - steps)

        alive_single: cython.double; couple_became_single: cython.bint
        alive_single = self._alive_single[self._episode_length + steps]
        couple_became_single = self._couple and (not forced_family_unit_couple if force_family_unit else alive_single != -1)
        if couple_became_single:

            self._consume_charitable /= 1 + self._params.consume_additional
            if self._only_alive2:
                self._income_preretirement_years = 0
            else:
                self._income_preretirement_years2 = 0
            if self._params.couple_death_preretirement_consume == 'consume_additional':
                self._consume_preretirement /= 1 + self._params.consume_additional
            elif self._params.couple_death_preretirement_consume == 'pro_rata':
                try:
                    ratio = (self._start_income_preretirement2 if self._only_alive2 else self._start_income_preretirement) / \
                        (self._start_income_preretirement + self._start_income_preretirement2)
                except ZeroDivisionError:
                    ratio = 1
                self._consume_preretirement *= ratio
            elif self._params.couple_death_preretirement_consume == 'none':
                pass
            else:
                assert False

            self._retirement_expectancy_both = [0.0] * len(self._retirement_expectancy_both)
            self._retirement_expectancy_one = self._retirement_expectancy_single

        # for _ in range(steps):
        #     income_fluctuation = lognormvariate(self._params.income_preretirement_mu * self._params.time_period,
        #         self._params.income_preretirement_sigma * sqrt(self._params.time_period))
        #     if self._income_preretirement_years > 0:
        #         self._income_preretirement *= income_fluctuation
        #     if self._income_preretirement_years2 > 0:
        #         if self._params.income_preretirement_concordant:
        #             self._income_preretirement2 *= income_fluctuation
        #         else:
        #             self._income_preretirement2 *= lognormvariate(self._params.income_preretirement_mu2 * self._params.time_period,
        #                 self._params.income_preretirement_sigma2 * sqrt(self._params.time_period))
        if not self._income_preretirement_years > 0:
            self._income_preretirement = 0
        if not self._income_preretirement_years2 > 0:
            self._income_preretirement2 = 0

        retired = self._preretirement_years == 0
        db: DefinedBenefit
        for db in self._defined_benefits.values():
            db.step(self._age, retired, self._couple or alive_single != 0 and not self._only_alive2, self._couple or alive_single != 0 and self._only_alive2)

        self._episode_length += steps
        self._env_timesteps += steps

        self._couple = forced_family_unit_couple if force_family_unit else alive_single == -1

        self._date = (self._date_start + timedelta(days = self._episode_length * self._params.time_period * 365.25)).isoformat()

    def goto(self, step = None, age = None, real_oup_x = None, inflation_oup_x = None, p_tax_free = None, p_tax_deferred = None, p_taxable_assets = None,
             p_taxable_basis = None, taxes_due = None, force_family_unit = False, forced_family_unit_couple = True):
        '''Goto a reproducable time step. Useful for benchmarking and plotting surfaces.'''

        assert (step is None) != (age is None)

        if step is not None:
            age = self._age_start + step / self._params.time_period

        if age < self._age or force_family_unit and not self._couple and forced_family_unit_couple:
            self._reset()
            assert not force_family_unit or self._couple or not forced_family_unit_couple

        step = round((age - self._age) / self._params.time_period)
        assert step >= 0

        if step != 0:
            self._step(step, force_family_unit, forced_family_unit_couple)

        assert (real_oup_x is None) == (inflation_oup_x is None)

        if real_oup_x is not None:
            self._bonds.real.oup.next_x = real_oup_x
            assert self._bonds.inflation.inflation_a == self._bonds.inflation.bond_a and self._bonds.inflation.inflation_sigma == self._bonds.inflation.bond_sigma
            self._bonds.inflation.oup.next_x = inflation_oup_x
            self._bonds.inflation.inflation_oup.next_x = inflation_oup_x
            self._bonds_stepper.step()

        if p_tax_free is not None: self._p_tax_free = p_tax_free
        if p_tax_deferred is not None: self._p_tax_deferred = p_tax_deferred
        if p_taxable_assets is None:
            assert p_taxable_basis is None
        else:
            assert p_taxable_basis is not None
            self._p_taxable = p_taxable_assets.sum()
            self._taxes.reset(p_taxable_assets, p_taxable_basis, 0)
        if taxes_due is not None:
            self._taxes_due = 0

        self._pre_calculate()
        return self._observe()

    def render(self, mode = 'human'):

        print('    ', self._prev_asset_allocation, self._prev_consume_rate, self._prev_real_spias_purchase, self._prev_nominal_spias_purchase, self._prev_reward)

        for db in self._defined_benefits.values():
            db.render(self._cpi)

        pv_income_preretirement = self._income_preretirement * self._income_preretirement_years
        pv_income_preretirement2 = self._income_preretirement2 * self._income_preretirement_years2
        pv_consume_preretirement = self._consume_preretirement * self._preretirement_years

        print(self._age, self._p_tax_free, self._p_tax_deferred, self._p_taxable,
            pv_income_preretirement, pv_income_preretirement2, pv_consume_preretirement, - self._taxes_due)

        stdout.flush()

    def seed(self, seed=None):

        return

    @cython.locals(growth_rate = cython.double)
    def _pre_calculate_wealth(self, growth_rate = 1.0):
        # By default use a conservative growth rate for determining the present value of wealth.
        # Also reflects the fact that we won't get to consume all wealth before we are expected to die.
        # Leave it to the AI to map to actual value.

        self._pv_preretirement_income = [0.0] * len(TaxStatus)
        self._pv_retired_income = [0.0] * len(TaxStatus)
        self._pv_social_security = 0
        type_of_funds: str; is_social_security: cython.bint; db: DefinedBenefit
        for (type_of_funds, real, is_social_security), db in self._defined_benefits.items():
            tax_status: cython.int; pv: cython.double
            if type_of_funds == 'tax_free':
                tax_status = TAX_FREE
            elif type_of_funds == 'tax_deferred':
                tax_status = TAX_DEFERRED
            elif type_of_funds == 'taxable':
                tax_status = TAXABLE
            if self._preretirement_years > 0:
                pv = db.pv(self._cpi, preretirement = True)
                self._pv_preretirement_income[tax_status] += pv
                if is_social_security:
                    self._pv_social_security += pv
            pv = db.pv(self._cpi, retired = True)
            self._pv_retired_income[tax_status] += pv
            if is_social_security:
                self._pv_social_security += pv
        source: cython.int
        source = TAXABLE if self._params.income_preretirement_taxable else TAX_FREE
        if self._preretirement_years > 0:
            income: cython.double
            income = self._income_preretirement * min(self._income_preretirement_years, self._preretirement_years) + \
                self._income_preretirement2 * min(self._income_preretirement_years2, self._preretirement_years)
            self._pv_preretirement_income[source] += income
            self._pv_preretirement_income[TAX_FREE] -= self._consume_preretirement * self._preretirement_years
            # Currently no need to reduce taxable and increase tax_deferred by 401(k)/IRA contributions as only ever consider pre-retirement taxable + tax_deferred.
        self._pv_retired_income[source] += self._income_preretirement * max(0, self._income_preretirement_years - self._preretirement_years)
        self._pv_retired_income[source] += self._income_preretirement2 * max(0, self._income_preretirement_years2 - self._preretirement_years)

        self._retired_income_wealth_pretax = sum(self._pv_retired_income)

        if self._couple:
            self._years_retired = float(self._retirement_expectancy_both[self._episode_length]) + \
                float(self._retirement_expectancy_one[self._episode_length]) / (1 + self._params.consume_additional)
            self._couple_weight = 2
        else:
            self._years_retired = self._retirement_expectancy_one[self._episode_length]
            self._couple_weight = 1
        self._years_retired = max(self._years_retired, self._params.time_period) # Prevent divide by zeros later.

        if growth_rate != 1:
            preretirement_growth = growth_rate ** self._preretirement_years
            retirement_growth = 1 if growth_rate == 1 else self._years_retired * (1 - 1 / growth_rate) / (1 - 1 / growth_rate ** self._years_retired)
            total_growth = preretirement_growth * retirement_growth
        else:
            total_growth = 1

        self._wealth_tax_free = self._p_tax_free * total_growth
        self._wealth_tax_deferred = self._p_tax_deferred * total_growth
        self._wealth_taxable = self._p_taxable * total_growth

        if not self._params.tax and self._params.income_aggregate:
            # Aggregating wealth results in better training.
            self._pv_retired_income = [0.0] * len(TaxStatus)
            self._pv_retired_income[TAX_FREE] = self._retired_income_wealth_pretax
            self._wealth_tax_free += self._wealth_tax_deferred + self._wealth_taxable
            self._wealth_tax_deferred = 0
            self._wealth_taxable = 0

        self._p_wealth_pretax = self._wealth_tax_free + self._wealth_tax_deferred + self._wealth_taxable
        self._raw_preretirement_income_wealth = sum(self._pv_preretirement_income) # Should factor in investment growth.
        self._net_wealth_pretax = self._p_wealth_pretax + self._retired_income_wealth_pretax + self._raw_preretirement_income_wealth

        self._rough_ce_estimate_individual = max(self._params.welfare, self._net_wealth_pretax / self._years_retired / self._couple_weight)

    def _pre_calculate(self):

        self._pre_calculate_wealth()

        p_basis: cython.double; cg_carry: cython.double
        p_basis, cg_carry = self._taxes.observe()
        assert p_basis >= 0

        average_asset_years = self._preretirement_years + self._years_retired / 2
        total_years = self._preretirement_years + self._years_retired

        pv_regular_income = float(self._pv_preretirement_income[TAX_DEFERRED]) + float(self._pv_preretirement_income[TAXABLE]) + \
            float(self._pv_retired_income[TAX_DEFERRED]) + float(self._pv_retired_income[TAXABLE]) + self._wealth_tax_deferred
        pv_social_security = self._pv_social_security
        discount: cython.double
        discount = float(self._bonds_constant_inflation.discount_rate(average_asset_years)) ** average_asset_years
        pv_capital_gains = cg_carry + self._wealth_taxable - p_basis / discount
            # Fails to take into consideration non-qualified dividends.
            # Taxable basis does not get adjusted for inflation.
        pv_nii = pv_capital_gains
        regular_tax: cython.double; capital_gains_tax: cython.double
        regular_tax, capital_gains_tax, _ = \
            self._taxes.calculate_taxes(pv_regular_income / total_years, pv_social_security / total_years, pv_capital_gains / total_years, pv_nii / total_years, 0,
                not self._couple)
                # Assumes income smoothing.
                # Ignores any charitable income tax deduction.
        pv_regular_tax = total_years * regular_tax
        pv_capital_gains_tax = total_years * capital_gains_tax
        self._pv_taxes = pv_regular_tax + pv_capital_gains_tax

        try:
            self._regular_tax_rate = pv_regular_tax / pv_regular_income
        except ZeroDivisionError:
            self._regular_tax_rate = 0
        try:
            self._capital_gains_tax_rate = pv_capital_gains_tax / pv_capital_gains
        except ZeroDivisionError:
            self._capital_gains_tax_rate = 0
        self._p_wealth = max(0, self._p_wealth_pretax - self._regular_tax_rate * self._wealth_tax_deferred - pv_capital_gains_tax - self._taxes_due)
        self._raw_preretirement_income_wealth -= self._regular_tax_rate * \
            (float(self._pv_preretirement_income[TAX_DEFERRED]) + float(self._pv_preretirement_income[TAXABLE]))
        self._preretirement_income_wealth = max(0, self._raw_preretirement_income_wealth)
        self._net_wealth = max(0, self._net_wealth_pretax - self._pv_taxes - self._taxes_due)
        self._retired_income_wealth = max(0, self._net_wealth - self._p_wealth - self._preretirement_income_wealth)

        income_estimate = self._net_wealth / self._years_retired
        self._ce_estimate_individual = max(self._params.welfare, income_estimate / self._couple_weight)

        try:
            self._consume_fraction_estimate = 1 / self._years_retired
        except ZeroDivisionError:
            self._consume_fraction_estimate = float('inf')

        try:
            self._p_fraction = min(self._p_wealth / self._net_wealth, 1)
            self._preretirement_fraction = min(self._preretirement_income_wealth / self._net_wealth, 1)
        except ZeroDivisionError:
            self._p_fraction = 1
            self._preretirement_fraction = 1

        self._gi_sum()
        self._p_sum = self._p_tax_free + self._p_tax_deferred + self._p_taxable
        gi = self._gi_total * self._params.time_period
        self._taxes_paid = self._taxes_due
        self._p_plus_income = self._p_sum + gi - self._taxes_paid
        self._net_gi = (1 - self._regular_tax_rate) * gi

        self._spias_ever = self._params.real_spias or self._params.nominal_spias
        if self._spias_ever and (self._params.preretirement_spias or self._preretirement_years <= self._params.time_period + 1e-12):
            min_age: cython.double; max_age: cython.double; age_permitted: cython.bint
            if self._couple:
                min_age = min(self._age, self._age2)
                max_age = max(self._age, self._age2)
            else:
                min_age = max_age = self._age2 if self._only_alive2 else self._age
            age_permitted = min_age >= self._params.spias_permitted_from_age and max_age <= self._params.spias_permitted_to_age
            self._spias_required = age_permitted and max_age >= self._params.spias_from_age
            self._spias = age_permitted and (self._params.couple_spias or not self._couple) or self._spias_required
        else:
            self._spias = False

    def _pricing_spia(self, bonds, adjustment, payout_delay, payout_fraction):

        life_table = make_life_table(self._params.life_table_spia, self._params.sex, ae = 'aer2005_13-summary') if self._couple or not self._only_alive2 else None
        life_table2 = make_life_table(self._params.life_table_spia, self._sex2, ae = 'aer2005_13-summary') if self._couple or self._only_alive2 else None

        spia = make_income_annuity(bonds, life_table, life_table2 = life_table2, age = self._age, age2 = self._age2, payout_delay = 12 * payout_delay, joint = True,
            payout_fraction = payout_fraction, adjust = adjustment, frequency = 1 / self._params.time_period, price_adjust = 'all', date_str = self._date)

        return spia

    _spia_years_cache = {}

    def _compute_spia_years(self):

        payout_delay = self._params.time_period
        payout_fraction = 1 / (1 + self._params.consume_additional)
        spia: IncomeAnnuity
        spia = self._pricing_spia(self._bonds_zero, 0, payout_delay, payout_fraction)
        duration = spia.premium(1) * self._params.time_period

        return duration

    def _observe(self):

        couple: cython.double; num_401k: cython.double; one_on_gamma: cython.double

        if self._couple:
            if self._params.couple_hide:
                couple = 0
                num_401k = 1 if self._have_401k or self._have_401k2 else 0
            else:
                couple = 1
                num_401k = (1 if self._have_401k else 0) + (1 if self._have_401k2 else 0)
        else:
            couple = 0
            num_401k = (1 if self._have_401k2 else 0) if self._only_alive2 else (1 if self._have_401k else 0)
        one_on_gamma = 1 / self._gamma

        lifespan_percentile_years: cython.double; spia_expectancy_years: cython.double; final_spia_purchase: cython.doouble

        if self._spias_ever:
            # We siplify by comparing life expectancies and SPIA payouts rather than retirement expectancies and DIA payouts.
            # DIA payouts depend on retirement age, which would make the _spia_years_cache sigificiantly larger and less effective.
            lifespan_percentile_years = self._life_percentile[self._episode_length]

            k_age = self._age if self._couple or not self._only_alive2 else -1
            k_age2 = self._age2 if self._couple or self._only_alive2 else -1
            k_date = self._date
            key = (k_age, k_age2, self._date)
            try:
                spia_expectancy_years = Fin._spia_years_cache[key]
            except KeyError:
                spia_expectancy_years = self._compute_spia_years()
                Fin._spia_years_cache[key] = spia_expectancy_years

            max_age: cython.double; final_spias_purchase_bool: cython.bint; final_spias_purchase: cython.double

            if self._couple:
                max_age = max(self._age, self._age2) # Determines age cut-off and thus final purchase signal for the purchase of SPIAs.
            else:
                max_age = self._age2 if self._only_alive2 else self._age
            final_spias_purchase_bool = max_age <= self._params.spias_permitted_to_age < max_age + self._params.time_period
            final_spias_purchase = 1 if final_spias_purchase_bool else 0
        else:
            lifespan_percentile_years = 0
            spia_expectancy_years = 0
            final_spias_purchase = 0

        alive_single: cython.double; reward_weight: cython.double; reward_value: cython.double;
        reward_to_go_estimate: cython.double; relative_ce_estimate_individual: cython.double

        alive_single = self._alive_single[self._episode_length]
        if alive_single == -1:
            alive_single = 1
        reward_weight = (2 * float(self._retirement_expectancy_both[self._episode_length])
            + alive_single * float(self._retirement_expectancy_one[self._episode_length])) \
            * self._params.time_period
        _, _, reward_value = self._raw_reward(self._ce_estimate_individual)
        reward_to_go_estimate = reward_weight * self._reward_scale * reward_value
        reward_to_go_estimate = max(-1e30, reward_to_go_estimate) # Prevent observation of -inf reward estimate during training.
        relative_ce_estimate_individual = self._ce_estimate_individual / self._consume_scale

        # Existence of taxes and welfare breaks scale invariance, so allow model to see scale.
        log_ce_estimate_individual: cython.double
        log_ce_estimate_individual = log(max(1, self._ce_estimate_individual))

        # When mean reversion rate is zero, avoid observing spurious noise for better training.
        stocks_price: cython.double; stocks_volatility: cython.double; real_interest_rate: cython.double
        stocks_price, stocks_volatility = self._stocks.observe()
        if not self._params.observe_stocks_price or self._params.stocks_mean_reversion_rate == 0:
            stocks_price = 1
        if not self._params.observe_stocks_volatility:
            stocks_volatility = 1
        if self._params.observe_interest_rate:
            real_interest_rate = self._bonds.real.observe()
        else:
            real_interest_rate = self._bonds.real.mean_short_interest_rate

        # Want to populate observe in a Cython efficient manner. Makes use of a Cython memory view.
        observe_len: cython.int; observe: cython.float[:]; i : cython.int
        observe_len = len(self._observation_space_items)
        observe = np.zeros(observe_len, dtype = np.float32)
        i = 0
        # Scenario description observations.
        observe[i] = couple; i += 1
        observe[i] = num_401k; i += 1
        observe[i] = one_on_gamma; i += 1
        # Nature of lifespan observations.
        observe[i] = self._preretirement_years; i += 1
        observe[i] = self._years_retired; i += 1
        # Annuitization related observations.
        observe[i] = lifespan_percentile_years; i += 1
        observe[i] = spia_expectancy_years; i += 1
        observe[i] = final_spias_purchase; i += 1
        # Value function related observations.
        # Best results (especially when gamma=6) if provide both a rewards to go estimate that can be fine tuned and a relative CE estimate.
        observe[i] = reward_to_go_estimate; i += 1
        observe[i] = relative_ce_estimate_individual; i += 1
        # Nature of wealth/income observations.
        observe[i] = log_ce_estimate_individual; i += 1
        # Obseve fractionality to hopefully take advantage of iso-elasticity of utility.
        observe[i] = self._p_fraction; i += 1
        observe[i] = self._preretirement_fraction; i += 1
        # Market condition obsevations.
        observe[i] = stocks_price; i += 1
        observe[i] = stocks_volatility; i += 1
        observe[i] = real_interest_rate; i += 1
        assert i == observe_len

        ok: cython.bint; ob: cython.double; lo: cython.double; hi: cython.double; element_ok: cython.bint

        ok = True
        for i in range(observe_len):
            # Inner loop is performance critical.
            ob = observe[i]
            lo = self._observation_space_low[i]
            hi = self._observation_space_high[i]
            try:
                element_ok = lo <= ob <= hi
            except FloatingPointError:
                self._warn('Invalid observation.', observe)
                assert False, 'Invalid observation.'
                element_ok = False # Cython - prevent checking that element_ok is defined on next line.
            if not element_ok:
                ok = False
                item = self._observation_space_items[i]
                self._observation_space_range_exceeded[i] += 1
                if self._observation_space_range_exceeded[i] > 1 + 1e-4 * self._env_timesteps:
                    self._warn('Frequently out of range ' + item + '.', 'frequency:', self._observation_space_range_exceeded[i] / self._env_timesteps,
                        timestep_ok_fraction = 1e-3)
                if not self._observation_space_high[i] - self._observation_space_extreme_range[i] < \
                        observe[i] < \
                        self._observation_space_low[i] + self._observation_space_extreme_range[i]:
                    self._warn('Extreme ' + item + '.', 'value, age:', observe[i], self._age, timestep_ok_fraction = 1e-4)
                    if isinf(observe[i]):
                        assert False, 'Infinite observation.'
                    if isnan(observe[i]):
                        assert False, 'Undetected invalid observation.'
        if self._params.observation_space_ignores_range:
            try:
                for i in range(len(observe)):
                    observe[i] = observe[i] * self._observation_space_scale[i] + self._observation_space_shift[i]
                scaled_obs = observe
            except FloatingPointError:
                assert False, 'Overflow in observation rescaling.'
        else:
            scaled_obs = observe
        if not ok:
            if self._params.observation_space_clip:
                if self._params.observation_space_ignores_range:
                    scaled_obs = np.clip(scaled_obs, -1, 1)
                else:
                    scaled_obs = np.clip(scaled_obs, self._observation_space_low_np, self._observation_space_high_np)
        return scaled_obs

    def decode_observation(self, obs):

        return {item: value for item, value in zip(self._observation_space_items, obs.tolist())}
