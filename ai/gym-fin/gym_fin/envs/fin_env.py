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
from math import exp, log
from random import uniform

import numpy as np

from gym import Env
from gym.spaces import Box

from gym_fin.envs.returns import Returns
from gym_fin.envs.utility import Utility

from spia import LifeTable

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
        print(life_expectancy[0])

        return tuple(alive), tuple(life_expectancy)

    def __init__(self, action_space_unbounded = False, direct_action = False, **kwargs):

        self.action_space_unbounded = action_space_unbounded
        self.direct_action = direct_action
        self.params = AttributeObject(kwargs)

        self.action_space = Box(low = -1.0, high = 1.0, shape = (3,), dtype = 'float32') # consume_action, stocks_action, bonds_action
            # DDPG implementation assumes [-x, x] symmetric actions.
            # PPO1 implementation ignores size and assumes [-inf, inf] output.
        self.observation_space = Box(# life_expectancy, guaranteed_income, portfolio size
                                     low =  np.array((  0,   0,   0)),
                                     high = np.array((100, 1e6, 1e7)),
                                     dtype = 'float32')

        self.alive, self.life_expectancy = self._compute_vital_stats(self.params.life_table, self.params.sex, self.params.age_start, self.params.age_end,
            self.params.life_expectancy_additional, self.params.life_table_date, self.params.time_period)
        self.age_start = self.params.age_start
        self.risk_free = Returns(self.params.risk_free_return, 0, self.params.time_period)
        self.stocks = Returns(self.params.stocks_return, self.params.stocks_volatility, self.params.time_period)
        self.bonds = Returns(self.params.bonds_return, self.params.bonds_volatility, self.params.time_period)

        if self.params.verbose:
            print('Asset classes:')
            print('    risk_free - mu:', round(self.risk_free.mu, 4))
            print('    stocks - mu, sigma:', round(self.stocks.mu, 4), round(self.stocks.sigma, 4))
            print('    bonds - mu, sigma:', round(self.bonds.mu, 4), round(self.bonds.sigma, 4))

        self.utility = Utility(self.params.gamma, self.params.consume_floor)

        self.reset()

    def reset(self):

        self.age = self.age_start

        found = False
        for _ in range(1000):

            if self.params.guaranteed_income_low == self.params.guaranteed_income_high:
                self.guaranteed_income = self.params.guaranteed_income_low # Handles guaranteed_income == 0.
            else:
                self.guaranteed_income = exp(uniform(log(self.params.guaranteed_income_low), log(self.params.guaranteed_income_high)))
            if self.params.p_notax_low == self.params.p_notax_high:
                self.p_notax = self.params.p_notax_low
            else:
                self.p_notax = exp(uniform(log(self.params.p_notax_low), log(self.params.p_notax_high)))

            consume_expect = self.guaranteed_income + self.p_notax / self.life_expectancy[0]

            found = self.params.consume_floor <= consume_expect <= self.params.consume_ceiling
            if found:
                break

        if not found:
            raise Exception('Expected consumption falls outside model training range.')

        self.prev_asset_allocation = None
        self.prev_consume_annual = None
        self.prev_reward = None

        self.episode_utility_sum = 0
        self.episode_length = 0

        return self._observe()

    def encode_direct_action(self, consume_fraction, stocks_allocation, bonds_allocation):

        risk_free_allocation = 1 - (stocks_allocation + bonds_allocation)

        return (consume_fraction, (stocks_allocation, bonds_allocation, risk_free_allocation))

    def decode_action(self, action):

        if self.action_space_unbounded:
            action = np.tanh(action)

        try:
            action = action.tolist() # De-numpify if required.
        except AttributeError:
            pass

        for a in action:
            assert -1 <= a <= 1

        consume_action, stocks_action, bonds_action = action

        consume_floor = 0
        # Define a consume ceiling above which we won't consume.
        # One half this value acts as a hint as to the initial consumption values to try.
        # With 1 as the consume ceiling (when time_period = 1) we will initially consume on average half the portfolio at each step.
        # This leads to very small consumption at advanced ages. The utilities and thus rewards for these values will be highly negative.
        # In the absence of guaranteed income this very small consumption will initially result in many warnings aboout out of bound rewards (if verbose is set).
        # For DDPG the resulting reward values will be sampled from the replay buffer, leading to a good DDPG fit for them.
        # This will be to the detriment of the fit for more likely reward values.
        # For PPO the policy network either never fully retrains after the initial poor fit, or requires more training time.
        consume_ceil = 2 * (self.p_notax / self.life_expectancy[self.episode_length] + self.guaranteed_income) / self._p_income()
            # Set:
            #     consume_ceil = 1 / self.params.time_period
            # to explore the full range of possible consume_fraction values.
        consume_fraction = consume_floor + (consume_ceil - consume_floor) * (consume_action + 1) / 2
        consume_fraction = min(consume_fraction, 1 / self.params.time_period)

        stocks_allocation = (stocks_action + 1) / 2
        if self.params.bonds:
            bonds_allocation = (1 - stocks_action) * (bonds_action + 1) / 2
        else:
            bonds_allocation = 0
        risk_free_allocation = 1 - (stocks_allocation + bonds_allocation)

        return (consume_fraction, (stocks_allocation, bonds_allocation, risk_free_allocation))

    def _p_income(self):

        return self.p_notax + self.guaranteed_income * self.params.time_period

    def consume_rate(self, consume_fraction):

        # Sanity check.
        consume_fraction_period = consume_fraction * self.params.time_period
        assert 0 <= consume_fraction_period <= 1

        return consume_fraction * self._p_income()

    def step(self, action):

        if self.direct_action:
            consume_fraction, asset_allocation = action
        else:
            consume_fraction, asset_allocation = self.decode_action(action)

        consume_annual = self.consume_rate(consume_fraction)
        consume = consume_annual * self.params.time_period

        p = self._p_income() - consume
        nonneg_p = max(p, 0)
        if p != nonneg_p:
            assert p / self.p_notax > -1e-15
            p = 0

        stocks_allocation, bonds_allocation, risk_free_allocation = asset_allocation
        ret = stocks_allocation * self.stocks.sample() + bonds_allocation * self.bonds.sample() + risk_free_allocation * self.risk_free.sample()

        self.p_notax = p * ret

        utility = self.utility.utility(consume_annual)
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

        self.prev_asset_allocation = asset_allocation
        self.prev_consume_annual = consume_annual
        self.prev_reward = reward

        return observation, reward, done, info

    def render(self, mode = 'human'):

        print(self.age, self.p_notax, self.prev_asset_allocation, self.prev_consume_annual, self.prev_reward)

    def seed(self, seed=None):

        return

    def _observe(self):

        life_expectancy = self.life_expectancy[self.episode_length]

        return np.array((life_expectancy, self.guaranteed_income, self.p_notax), dtype = 'float32')

    def decode_observation(self, obs):

        life_expectancy, guaranteed_income, p_notax = obs.tolist()

        return {'life_expectancy': life_expectancy, 'guaranteed_income': guaranteed_income, 'p_notax': p_notax}
