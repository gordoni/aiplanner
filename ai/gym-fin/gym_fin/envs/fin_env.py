# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from datetime import datetime
from math import atanh, exp, isnan, log, sqrt, tanh
from random import uniform

import numpy as np

from gym import Env
from gym.spaces import Box

from life_table import LifeTable
from spia import IncomeAnnuity

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.bonds import bonds_init
from gym_fin.envs.returns import Returns, returns_report, yields_report
from gym_fin.envs.returns_sample import ReturnsSample
from gym_fin.envs.utility import Utility

class AttributeObject(object):

    def __init__(self, dict):
        self.__dict__.update(dict)

class FinEnv(Env):

    metadata = {'render.modes': ['human']}

    def _compute_vital_stats(self, life_table, sex, age_start, age_end, life_expectancy_additional, life_table_date, time_period):

        le_add = 0 if life_table == 'fixed' else life_expectancy_additional
        death_age = age_end - time_period
        table = LifeTable(life_table, sex, age_start, death_age = death_age, le_add = le_add, date_str = life_table_date)

        start_date = datetime.strptime(life_table_date, '%Y-%m-%d')
        this_year = datetime(start_date.year, 1, 1)
        next_year = datetime(start_date.year + 1, 1, 1)
        start_decimal_year = start_date.year + (start_date - this_year) / (next_year - this_year)

        alive = [1]
        _alive = 1

        y = 0
        q_y = -1
        q = 0
        remaining_fract = 0
        a_y = time_period
        while True:
            append_time = a_y - y
            fract = min(remaining_fract, append_time)
            _alive *= (1 - q) ** fract
            remaining_fract -= fract
            y += fract
            if y >= a_y:
                alive.append(_alive)
                a_y += time_period
            if y - q_y >= 1:
                q_y += 1
                q = table.q(age_start + q_y, year = start_decimal_year + q_y)
                remaining_fract = 1
                if q == 1:
                    break

        if life_table == 'fixed':
            # Death occurs at end of death_age period.
            remainder = 1
        else:
            # Death occurs half way through each period.
            remainder = 0.5
        life_expectancy = [(sum(alive[y + 1:]) / alive[y] + remainder) * time_period for y in range(len(alive))]
        life_expectancy.append(0)

        return table, tuple(alive), tuple(life_expectancy)

    def __init__(self, action_space_unbounded = False, direct_action = False, **kwargs):

        self.action_space_unbounded = action_space_unbounded
        self.direct_action = direct_action
        self.params = AttributeObject(kwargs)

        self.action_space = Box(low = -1.0, high = 1.0, shape = (10, ), dtype = 'float32')
            # consume_action, spias_action, real_spias_action,
            # stocks_action, real_bonds_action, nominal_bonds_action, iid_bonds_action, bills_action,
            # real_bonds_duration_action, nominal_bonds_duration_action,
            # DDPG implementation assumes [-x, x] symmetric actions.
            # PPO1 implementation ignores size and assumes [-inf, inf] output.
        self.observation_space = Box(
            # life_expectancy, real guaranteed income, nominal guaranteed income, portfolio size, short real interest rate, short inflation rate
            low =  np.array((  0,   0,   0,   0, -0.05, 0.0)),
            high = np.array((100, 1e6, 1e6, 1e7,  0.05, 0.1)),
            dtype = 'float32'
        )

        self.life_table, self.alive, self.life_expectancy = \
            self._compute_vital_stats(self.params.life_table, self.params.sex, self.params.age_start, self.params.age_end,
            self.params.life_expectancy_additional, self.params.life_table_date, self.params.time_period)
        self.age_start = self.params.age_start

        self.utility = Utility(self.params.gamma, self.params.consume_floor)

        self.stocks = Returns(self.params.stocks_return, self.params.stocks_volatility,
            self.params.stocks_standard_error if self.params.returns_standard_error else 0, self.params.time_period)
        self.iid_bonds = Returns(self.params.iid_bonds_return, self.params.iid_bonds_volatility,
            self.params.bonds_standard_error if self.params.returns_standard_error else 0, self.params.time_period)
        self.bills = Returns(self.params.bills_return, self.params.bills_volatility,
            self.params.bills_standard_error if self.params.returns_standard_error else 0, self.params.time_period)

        self.real_bonds, self.nominal_bonds, self.inflation = bonds_init(
            real_standard_error = self.params.bonds_standard_error if self.params.returns_standard_error else 0,
            inflation_standard_error = self.params.inflation_standard_error if self.params.returns_standard_error else 0,
            time_period = self.params.time_period)
        self.bonds_stepper = self.nominal_bonds

        if self.params.iid_bonds:
            if self.params.iid_bonds_type == 'real':
                self.iid_bonds = ReturnsSample(self.real_bonds, self.params.iid_bonds_duration,
                    self.params.bonds_standard_error if self.params.returns_standard_error else 0,
                    stepper = self.bonds_stepper, time_period = self.params.time_period)
            elif self.params.iid_bonds_type == 'nominal':
                self.iid_bonds = ReturnsSample(self.nominal_bonds, self.params.iid_bonds_duration,
                    self.params.bonds_standard_error if self.params.returns_standard_error else 0,
                    stepper = self.bonds_stepper, time_period = self.params.time_period)

        self.real_spia = IncomeAnnuity(self.real_bonds, self.life_table, payout_delay = 12, frequency = 1, cpi_adjust = 'all',
            date_str = self.params.life_table_date)
        self.nominal_spia = IncomeAnnuity(self.nominal_bonds, self.life_table, payout_delay = 12, frequency = 1,
            date_str = self.params.life_table_date)

        print()
        print('Real/nominal yields:')

        if self.params.real_bonds:
            if self.params.real_bonds_duration:
                yields_report('real bonds {:2d}'.format(int(self.params.real_bonds_duration)), self.real_bonds,
                    duration = self.params.real_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
            else:
                yields_report('real bonds  5', self.real_bonds, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                yields_report('real bonds 15', self.real_bonds, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

        if self.params.nominal_bonds:
            if self.params.nominal_bonds_duration:
                yields_report('nominal bonds {:2d}'.format(int(self.params.nominal_bonds_duration)), self.nominal_bonds,
                    duration = self.params.nominal_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
            else:
                yields_report('nominal bonds  5', self.nominal_bonds, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                yields_report('nominal bonds 15', self.nominal_bonds, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

        print()
        print('Real returns:')

        returns_report('stocks', self.stocks, time_period = self.params.time_period)

        if self.params.real_bonds:
            if self.params.real_bonds_duration:
                returns_report('real bonds {:2d}'.format(int(self.params.real_bonds_duration)), self.real_bonds,
                    duration = self.params.real_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
            else:
                returns_report('real bonds  5', self.real_bonds, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                returns_report('real bonds 15', self.real_bonds, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

        if self.params.nominal_bonds:
            if self.params.nominal_bonds_duration:
                returns_report('nominal bonds {:2d}'.format(int(self.params.nominal_bonds_duration)), self.nominal_bonds,
                    duration = self.params.nominal_bonds_duration, stepper = self.bonds_stepper, time_period = self.params.time_period)
            else:
                returns_report('nominal bonds  5', self.nominal_bonds, duration = 5, stepper = self.bonds_stepper, time_period = self.params.time_period)
                returns_report('nominal bonds 15', self.nominal_bonds, duration = 15, stepper = self.bonds_stepper, time_period = self.params.time_period)

        if self.params.iid_bonds:
            returns_report('iid bonds', self.iid_bonds, time_period = self.params.time_period)

        if self.params.nominal_bonds or self.params.nominal_spias:
            returns_report('inflation', self.inflation, duration = 1, stepper = self.bonds_stepper, time_period = self.params.time_period)

        self.reset()

    def reset(self):

        self.age = self.age_start

        found = False
        for _ in range(1000):

            if self.params.gi_real_low == self.params.gi_real_high:
                self.gi_real = self.params.gi_real_low # Handles gi_real == 0.
            else:
                self.gi_real = exp(uniform(log(self.params.gi_real_low), log(self.params.gi_real_high)))

            if self.params.gi_nominal_low == self.params.gi_nominal_high:
                self.gi_nominal = self.params.gi_nominal_low
            else:
                self.gi_nominal = exp(uniform(log(self.params.gi_nominal_low), log(self.params.gi_nominal_high)))

            if self.params.p_notax_low == self.params.p_notax_high:
                self.p_notax = self.params.p_notax_low
            else:
                self.p_notax = exp(uniform(log(self.params.p_notax_low), log(self.params.p_notax_high)))

            consume_expect = self.gi_real + self.gi_nominal + self.p_notax / self.life_expectancy[0]

            found = self.params.consume_floor <= consume_expect <= self.params.consume_ceiling
            if found:
                break

        if not found:
            raise Exception('Expected consumption falls outside model training range.')

        self.stocks.reset()
        self.iid_bonds.reset()
        self.bills.reset()

        self.bonds_stepper.reset()

        self.prev_asset_allocation = None
        self.prev_real_spias_rate = None
        self.prev_nominal_spias_rate = None
        self.prev_consume_rate = None
        self.prev_reward = None

        self.episode_utility_sum = 0
        self.episode_length = 0

        return self._observe()

    def encode_direct_stock_bill_action(self, consume_fraction, stocks_allocation):

        bills_allocation = 1 - stocks_allocation

        return (consume_fraction, None, None, AssetAllocation(stocks = stocks_allocation, bills = bills_allocation), None, None)

    def decode_action(self, action):

        if isnan(action[0]):
            assert False # Detect bug in code interacting with model before it messes things up.

        try:
            action = action.tolist() # De-numpify if required.
        except AttributeError:
            pass

        consume_action, spias_action, real_spias_action, \
            stocks_action, real_bonds_action, nominal_bonds_action, iid_bonds_action, bills_action, \
            real_bonds_duration_action, nominal_bonds_duration_action = action

        if self.action_space_unbounded:
            spias_action = tanh(spias_action)
            real_spias_action = tanh(real_spias_action)
            real_bonds_duration_action = tanh(real_bonds_duration_action)
            nominal_bonds_duration_action = tanh(nominal_bonds_duration_action)
        else:
            consume_action = atanh(consume_action)
            stocks_action = atanh(stocks_action)
            real_bonds_action = atanh(real_bonds_action)
            nominal_bonds_action = atanh(nominal_bonds_action)
            iid_bonds_action = atanh(iid_bonds_action)
            bills_action = atanh(bills_action)

        consume_estimate = (self.gi_real + self.gi_nominal + self.p_notax / self.life_expectancy[self.episode_length]) / self._p_income()

        consumption_bounded = True # Bounding consumption gives better certainty equivalents.
        if consumption_bounded:

            consume_action = tanh(consume_action / 5)
                # Scaling back initial volatility of consume_action is observed to improve run to run mean and reduce standard deviation of certainty equivalent.
            consume_action = (consume_action + 1) / 2
            # Define a consume floor and consume ceiling outside of which we won't consume.
            # The mid-point acts as a hint as to the initial consumption values to try.
            # With 0.5 as the mid-point (when time_period = 1) we will initially consume on average half the portfolio at each step.
            # This leads to very small consumption at advanced ages. The utilities and thus rewards for these values will be highly negative.
            # For DDPG the resulting reward values will be sampled from the replay buffer, leading to a good DDPG fit for the negative rewards.
            # This will be to the detriment of the fit for more likely reward values.
            # For PPO the policy network either never fully retrains after the initial poor fit, or requires more training time.
            consume_floor = 0
            consume_ceil = 2 * consume_estimate
            consume_fraction = consume_floor + (consume_ceil - consume_floor) * consume_action

        else:

            consume_action = tanh(consume_action / 10)
                # Scale back initial volatility of consume_action to improve run to run mean and reduce standard deviation of certainty equivalent.
            consume_action = (consume_action + 1) / 2
            consume_weight = 2 * log((1 + sqrt(1 - 4 * consume_estimate * (1 - consume_estimate))) / (2 * consume_estimate))
                # So that consume_fraction = consume_estimate when consume_action = 0.5.
            consume_weight = max(1e-3, consume_weight) # Don't allow weight to become zero.
            # consume_action is in the range [0, 1]. Make consume_fraction also in the range [0, 1], but weight consume_fraction towards zero.
            # Otherwise by default consume 50% of assets each year. Quickly end up with few assets, and large negative utilities, making learning difficult.
            consume_fraction = (exp(consume_weight * consume_action) - 1) / (exp(consume_weight) - 1)

        consume_fraction = min(consume_fraction, 1 / self.params.time_period)

        if self.params.real_spias or self.params.nominal_spias:
            spias_action = (spias_action + 1) / 2
            # spias_action is in the range [0, 1]. Make spias_fraction also in the range [0, 1], but weight spias_fraction towards zero.
            # Otherwise the default is to annuitize 50% of assets each year. Quickly end up with few non-spia assets, making learning difficult.
            #
            #     spias_weight    spias_fraction when spias_action = 0.5
            #          5                         7.6%
            #          6                         4.7%
            #          7                         2.9%
            #          8                         1.8%
            #          9                         1.1%
            spias_weight = 7
            spias_fraction = (exp(spias_weight * spias_action) - 1) / (exp(spias_weight) - 1)
            real_spias_fraction = spias_fraction if self.params.real_spias else 0
            if self.params.nominal_spias:
                real_spias_fraction *= (real_spias_action + 1) / 2
            nominal_spias_fraction = spias_fraction - real_spias_fraction

        if not self.params.real_spias:
            real_spias_fraction = None
        if not self.params.nominal_spias:
            nominal_spias_fraction = None

        # Softmax.
        stocks = exp(stocks_action)
        real_bonds = exp(real_bonds_action) if self.params.real_bonds else 0
        nominal_bonds = exp(nominal_bonds_action) if self.params.nominal_bonds else 0
        iid_bonds = exp(iid_bonds_action) if self.params.iid_bonds else 0
        bills = exp(bills_action) if self.params.bills else 0
        total = stocks + real_bonds + nominal_bonds + iid_bonds + bills
        stocks /= total
        real_bonds /= total
        nominal_bonds /= total
        iid_bonds /= total
        bills /= total

        if not self.params.real_bonds:
            real_bonds = None
        if not self.params.nominal_bonds:
            nominal_bonds = None
        if not self.params.iid_bonds:
            iid_bonds = None
        if not self.params.bills:
            bills = None

        if not self.params.real_bonds:
            real_bonds_duration = None
        elif self.params.real_bonds_duration == None:
            real_bonds_duration = self.params.time_period + \
                (self.params.real_bonds_duration_max - self.params.time_period) * (real_bonds_duration_action + 1) / 2
        else:
            real_bonds_duration = self.params.real_bonds_duration

        if not self.params.nominal_bonds:
            nominal_bonds_duration = None
        elif self.params.nominal_bonds_duration == None:
            nominal_bonds_duration = self.params.time_period + \
                (self.params.nominal_bonds_duration_max - self.params.time_period) * (nominal_bonds_duration_action + 1) / 2
        else:
            nominal_bonds_duration = self.params.nominal_bonds_duration

        asset_allocation = AssetAllocation(stocks = stocks, real_bonds = real_bonds, nominal_bonds = nominal_bonds, iid_bonds = iid_bonds, bills = bills)
        return (consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration)

    def _p_income(self):

        return self.p_notax + (self.gi_real + self.gi_nominal) * self.params.time_period

    def spend(self, consume_fraction, real_spias_fraction, nominal_spias_fraction):

        # Sanity check.
        consume_fraction_period = consume_fraction * self.params.time_period
        assert 0 <= consume_fraction_period <= 1

        consume_annual = consume_fraction * self._p_income()
        consume = consume_annual * self.params.time_period

        p = self._p_income() - consume
        nonneg_p = max(p, 0)

        if self.params.real_spias:
            real_spias_fraction *= self.params.time_period
        else:
            real_spias_fraction = 0
        if self.params.nominal_spias:
            nominal_spias_fraction *= self.params.time_period
        else:
            nominal_spias_fraction = 0
        total = real_spias_fraction + nominal_spias_fraction
        if total > 1:
            real_spias_fraction /= total
            nominal_spias_fraction /= total
        real_spias_purchase = real_spias_fraction * nonneg_p
        nominal_spias_purchase = nominal_spias_fraction * nonneg_p
        p -= real_spias_purchase + nominal_spias_purchase
        nonneg_p = max(p, 0)

        if p != nonneg_p:
            assert p / self.p_notax > -1e-15
            p = 0

        return p, consume, real_spias_purchase, nominal_spias_purchase

    def step(self, action):

        if self.direct_action:
            consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = action
        else:
            consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = \
                self.decode_action(action)

        p, consume, real_spias_purchase, nominal_spias_purchase = self.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)
        consume_rate = consume / self.params.time_period
        real_spias_rate = real_spias_purchase / self.params.time_period
        nominal_spias_rate = nominal_spias_purchase / self.params.time_period

        if real_spias_purchase > 0:
            self.real_spia.set_age(self.age)
            self.gi_real += self.real_spia.payout(real_spias_purchase, mwr = self.params.real_spias_mwr)
        if nominal_spias_purchase > 0:
            self.nominal_spia.set_age(self.age)
            self.gi_nominal += self.nominal_spia.payout(nominal_spias_purchase, mwr = self.params.nominal_spias_mwr)

        inflation = self.inflation.inflation()
        self.gi_nominal /= inflation

        ret = 0
        if asset_allocation.stocks != None:
            ret += asset_allocation.stocks * self.stocks.sample()
        if asset_allocation.real_bonds != None:
            ret += asset_allocation.real_bonds * self.real_bonds.sample(real_bonds_duration)
        if asset_allocation.nominal_bonds != None:
            ret += asset_allocation.nominal_bonds * self.nominal_bonds.sample(nominal_bonds_duration)
        if asset_allocation.iid_bonds != None:
            ret += asset_allocation.iid_bonds * self.iid_bonds.sample()
        if asset_allocation.bills != None:
            ret += asset_allocation.bills * self.bills.sample()

        self.p_notax = p * ret

        utility = self.utility.utility(consume_rate)
        reward_annual = min(max(utility, - self.params.reward_clip), self.params.reward_clip)
        if self.params.verbose and reward_annual != utility:
            print('Reward out of range - age, p_notax, consume_fraction, utility:', self.age, self.p_notax, consume_fraction, utility)
        reward = reward_annual * self.alive[self.episode_length] * self.params.time_period

        self.age += self.params.time_period

        self.episode_utility_sum += utility
        self.episode_length += 1

        observation = self._observe()
        done = self.episode_length >= len(self.alive)
        info = {}
        if done:
            info['ce'] = self.utility.inverse(self.episode_utility_sum / self.episode_length)

        if not self.params.static_bonds:
            self.bonds_stepper.step()

        self.prev_asset_allocation = asset_allocation
        self.prev_real_spais_rate = real_spias_rate
        self.prev_nominal_spias_rate = nominal_spias_rate
        self.prev_consume_rate = consume_rate
        self.prev_reward = reward

        return observation, reward, done, info

    def render(self, mode = 'human'):

        print(self.age, self.gi_real, self.gi_nominal, self.p_notax, self.prev_asset_allocation, \
            self.prev_consume_rate, self.prev_real_spias_rate, self.prev_nominal_spias_rate, self.prev_reward)

    def seed(self, seed=None):

        return

    def _observe(self):

        life_expectancy = self.life_expectancy[self.episode_length]

        if self.params.observe_interest_rate:
            real_interest_rate, = self.real_bonds.observe()
        else:
            real_interest_rate = 0

        if self.params.observe_inflation_rate:
            inflation_rate, = self.inflation.observe()
        else:
            inflation_rate = 0

        observe = (life_expectancy, self.gi_real, self.gi_nominal, self.p_notax, real_interest_rate, inflation_rate)
        return np.array(observe, dtype = 'float32')

    def decode_observation(self, obs):

        life_expectancy, gi_real, gi_nominal, p_notax, real_interest_rate, inflation_rate = obs.tolist()

        return {
            'life_expectancy': life_expectancy,
            'gi_real': gi_real,
            'gi_nominal': gi_nominal,
            'p_notax': p_notax,
            'real_interest_rate': real_interest_rate,
            'inflation_rate': inflation_rate
        }
