#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

import numpy as np

from gym import Env
from gym.spaces import Box

import ray
from ray import tune

class MyEnv(Env):

    def __init__(self, config):
        self.observation_space = Box(-1, 1, shape=(1, ))
        self.action_space = Box(-1, 1, shape=(1, ))

    def reset(self):
        return np.zeros(1)

    def step(self, action):
        return np.zeros(1), 0, True, {}

ray.init(num_cpus=4, object_store_memory=int(100e6))

tune.run(
    'PPO',
    config = {
        'env': MyEnv,
    },
)
