# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, log
import numpy as np
from random import uniform

from gym import Env
from gym.spaces import Box, Tuple
from gym.utils import seeding

from gym_fin.envs.returns import Returns

class AttributeObject(object):

    def __init__(self, dict):
        self.__dict__.update(dict)

class FinEnv(Env):

    metadata = {'render.modes': ['human']}

    def __init__(self, action_space_unbounded=False, **kwargs):

        self.action_space_unbounded = action_space_unbounded
        self.params = AttributeObject(kwargs)

        self.action_space = Box(low = -1.0, high = 1.0, shape = (2,), dtype = 'float32') # consume_action, asset_allocation_action
            # DDPG implementation assumes [-x, x] symmetric actions.
            # PPO1 implementation ignores size and assumes [-inf, inf] output.
        self.observation_space = Box(# life_expectancy, guaranteed_income, portfolio size
                                     low =  np.array((  0,   0,   0)),
                                     high = np.array((100, 1e6, 1e7)),
                                     dtype = 'float32')

        self.age_start = 65
        self.age_terminal = 75
        self.gamma = self.params.gamma
        self.risk_free = Returns(self.params.risk_free_return, 0, self.params.time_period)
        self.stocks = Returns(self.params.stocks_return, self.params.stocks_volatility, self.params.time_period)

        # Utility needs to be scaled to roughly have an average absolute value of 1 for DDPG implementation (presumably due to optimizer step size).
        consume_floor = self.params.consume_floor
        self.utility_scale = 1 # Temporary scale for _inverse_utility().
        self.utility_scale = consume_floor / self._utility_inverse(-1) # Make utility(consume_floor) = -1.

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

            consume_expect = self.guaranteed_income + self.p_notax / (self.age_terminal - self.age_start)

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

    def step(self, action):

        if self.action_space_unbounded:
            action = np.tanh(action)
        try:
            action = action.tolist() # De-numpify if required.
        except AttributeError:
            pass
        consume_action, asset_allocation_action = action
        assert -1 <= consume_action <= 1
        assert -1 <= asset_allocation_action <= 1

        # Define a consume ceiling above which we won't consume.
        # One half this value acts as a hint as to the initial consumption values to try.
        # With 1 as the consume ceiling (when time_period = 1) we will initially consume on average half the portfolio at each step.
        # This leads to very small consumption at advanced ages. The utilities and thus rewards for these values will be highly negative.
        # In the absence of guaranteed income this very small consumption will initially result in many warnings aboout out of bound rewards.
        # For DDPG the resulting reward values will be sampled from the replay buffer, leading to a good DDPG fit for them.
        # This will be to the detriment of the fit for more likely reward values.
        # For PPO the policy network never fully retrains after the initial poor fit, and the results would be sub-optimal.
        consume_ceil = 2 / (self.age_terminal - self.age)
            # Set:
            #     consume_ceil = 1 / self.params.time_period
            # to explore the full range of possible consume_fraction values.
        consume_floor = 0
        consume_fraction = consume_floor + (consume_ceil - consume_floor) * (consume_action + 1) / 2
        consume_fraction = min(consume_fraction, 1 / self.params.time_period)
        consume_annual = consume_fraction * self.p_notax
        consume = consume_annual * self.params.time_period

        asset_allocation = (asset_allocation_action + 1) / 2

        self.p_notax = self.p_notax - consume
        self.p_notax *= asset_allocation * self.stocks.sample() + (1 - asset_allocation) * self.risk_free.sample()

        consume_annual += self.guaranteed_income

        utility = self._utility(consume_annual)
        reward = min(max(utility, -10), 10) # Bound rewards for DDPG implementation.
        if reward != utility:
            print('Reward out of range - age, p_notax, consume_fraction, utility:', self.age, self.p_notax, consume_fraction, utility)
            # Clipping to prevent rewards from spanning 5-10 or more orders of magnitude in the absence of guaranteed income.
            # Fitting of the critic would then perform poorly as large negative reward values would swamp accuracy of more reasonable reward values.
            #
            # In DDPG could also try "--popart --normalize-returns" (see setup_popart() in ddpg/ddpg.py).
            # Need to first fix a bug in ddpg/models.py: set name='output' in final critic tf.layers.dense().
            # But doesn't appear to work well becasuse in the absense of guaranteed income the rewards may span a large many orders of magnitude range.
            # In particular some rewards can be -inf, or close there to, which appears to swamp the Pop-Art scaling of the other rewards.

        self.age += self.params.time_period

        observation = self._observe()
        done = self.age >= self.age_terminal

        self.episode_utility_sum += utility
        self.episode_length += 1
        info = {}
        if done:
            info['certainty_equivalent'] = self._utility_inverse(self.episode_utility_sum / self.episode_length)

        self.prev_asset_allocation = asset_allocation
        self.prev_consume_annual = consume_annual
        self.prev_reward = reward

        return observation, reward, done, info

    def render(self, mode = 'human'):

        print(self.age, self.p_notax, self.prev_asset_allocation, self.prev_consume_annual, self.prev_reward)

    def seed(self, seed=None):

        return

    def _observe(self):

        life_expectancy = self.age_terminal - self.age

        return np.array((life_expectancy, self.guaranteed_income, self.p_notax), dtype = 'float32')

    def _utility(self, c):

        if c == 0:
            return float('-inf')

        if self.gamma == 1:
            return log(c / self.utility_scale)
        else:
            return ((c / self.utility_scale) ** (1 - self.gamma) - 1) / (1 - self.gamma)

    def _utility_inverse(self, u):

        if self.gamma == 1:
            return exp(u) * self.utility_scale
        else:
            return (u * (1 - self.gamma) + 1) ** (1 / (1 - self.gamma)) * self.utility_scale
