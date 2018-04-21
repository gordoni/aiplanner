# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

import numpy as np
import gym
from gym.spaces import Box, Tuple
from gym.utils import seeding

class FinEnv(gym.Env):

    metadata = {'render.modes': ['human']}

    def __init__(self):

        self.action_space = Box(low = -0.5, high = 0.5, shape = (1,), dtype = 'float32') # consume fraction - 0.5; DDPG implementation assumes symmetric actions.
        self.observation_space = Box(# life_expectancy, portfolio size
                                     low =  np.array((0,   0)),
                                     high = np.array((100, 1e7)),
                                     dtype = 'float32')

    def step(self, action):

        action = float(action) # De-numpify if required.
        consume_fraction = action + 0.5
        consume = consume_fraction * self.p

        try:
            utility = self._utility(consume)
        except ZeroDivisionError:
            utility = float('-inf')

        self.p = self.p - consume
        self.age += 1

        observation = self._observe()
        reward = utility / self.utility_scale
        reward = min(max(reward, -1), 1) # Bound rewards for DDPG implementation. Could also try "--popart --normalize-returns" (see setup_popart() in ddpg.py).
        done = self.age >= self.terminal_age
        info = {}

        self.prev_consume = consume
        self.prev_reward = reward

        return observation, reward, done, info

    def reset(self):

        self.gamma = 3
        self.age_terminal = 75

        self.age = 65
        self.p = 100000

        # Utility needs to be scaled to [-1, 1] for DDPG implementation.
        self.consume_high_level = 2.0 * self.p # Also sets scale for _utility(), so we don't underflow.
        self.consume_low_level = 0.5 * self.p / (self.age_terminal - self.age)
        self.utility_scale = max(abs(self._utility(self.consume_high_level)), abs(self._utility(self.consume_low_level)))

        return self._observe()

    def render(self, mode = 'human'):

        print(self.age, self.p, self.prev_consume, self.prev_reward)

    def seed(self, seed=None):

        return

    def _observe(self):

        life_expectancy = self.age_terminal - self.age

        return np.array((life_expectancy, self.p), dtype = 'float32')

    def _utility(self, c):

        return (c / self.consume_high_level) ** (1 - self.gamma) / (1 - self.gamma)
