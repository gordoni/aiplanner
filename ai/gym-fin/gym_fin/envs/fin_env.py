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

foo = 2

class FinEnv(Env):

    metadata = {'render.modes': ['human']}

    def __init__(self, **kwargs):

        self.params = kwargs

        self.action_space = Box(low = -0.5, high = 0.5, shape = (1,), dtype = 'float32') # consume_action; DDPG implementation assumes symmetric actions.
        self.observation_space = Box(# life_expectancy, portfolio size
                                     low =  np.array((0,   0)),
                                     high = np.array((100, 1e7)),
                                     dtype = 'float32')

        self.gamma = self.params['gamma']

        # Utility needs to be scaled to [-1, 1] for DDPG implementation.
        self.consume_high_level = self.params['p_notax_high'] # Also sets scale for _utility(), so we don't underflow.
        self.consume_low_level = 1e-3 * self.params['p_notax_low']
        self.utility_scale = max(abs(self._utility(self.consume_high_level)), abs(self._utility(self.consume_low_level)))

        self.reset()

    def step(self, action):

        consume_action = float(action) # De-numpify if required.

        # Prevent rewards from spanning 5-10 orders of magnitude.
        # Fitting of the critic would then perform poorly as large negative reward values would swamp accuracy of more reasonable reward values.
        # We do this by defining a consume ceiling above which we don't consume.
        # Without a consume ceiling we would initially consume on average half the portfolio at each step,
        # leading to very small consumption and large negative rewards at advanced ages.
        consume_ceil = min(2 / (self.age_terminal - self.age), 1)
        consume_fraction = consume_ceil * (consume_action + 0.5)
        consume = consume_fraction * self.p_notax

        try:
            utility = self._utility(consume)
        except ZeroDivisionError:
            utility = float('-inf')

        self.p_notax = self.p_notax - consume
        self.age += 1

        observation = self._observe()
        reward = utility / self.utility_scale
        if not -1 <= reward <= 1:
            print('reward out of range')
        reward = min(max(reward, -1), 1) # Bound rewards for DDPG implementation. Could also try "--popart --normalize-returns" (see setup_popart() in ddpg.py).
        done = self.age >= self.age_terminal
        info = {}

        self.prev_consume = consume
        self.prev_reward = reward

        return observation, reward, done, info

    def reset(self):

        self.age_terminal = 75

        self.age = 65
        self.p_notax = exp(uniform(log(self.params['p_notax_low']), log(self.params['p_notax_high'])))

        self.prev_consume = None
        self.prev_reward = None

        return self._observe()

    def render(self, mode = 'human'):

        print(self.age, self.p_notax, self.prev_consume, self.prev_reward)

    def seed(self, seed=None):

        return

    def _observe(self):

        life_expectancy = self.age_terminal - self.age

        return np.array((life_expectancy, self.p_notax), dtype = 'float32')

    def _utility(self, c):

        if self.gamma == 1:
            if c == 0:
                return float('-inf')
            else:
                return log(c / self.consume_high_level)
        else:
            return ((c / self.consume_high_level) ** (1 - self.gamma) - 1) / (1 - self.gamma)
