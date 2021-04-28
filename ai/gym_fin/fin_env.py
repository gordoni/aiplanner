# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
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

from ai.gym_fin.fin import Fin

class FinEnv(Env):

    def __init__(self, direct_action = False, **params):

        actions = 1 # consume_action
        if params['real_spias'] or params['nominal_spias']:
            actions += 1 # spias_action
            if params['real_spias'] and params['nominal_spias']:
                actions += 1 # real_spias_action
        if params['stocks']:
            actions += 1 # stocks_action
            actions += 1 # stocks_curvature_action
        if params['real_bonds']:
            actions += 1 # real_bonds_action
            if params['real_bonds_duration'] == -1 or params['real_bonds_duration_action_force']:
                actions += 1 # real_bonds_duration_action
        if params['nominal_bonds']:
            actions += 1 # nominal_bonds_action
            if params['nominal_bonds_duration'] == -1 or params['nominal_bonds_duration_action_force']:
                actions += 1 # nominal_bonds_duration_action
        if params['iid_bonds']:
            actions += 1 # iid_bonds_action
            if params['iid_bonds_duration_action_force']:
                actions += 1 # dummy iid_bonds_duration_action

        self.action_space = Box(low = -1.0, high = 1.0, shape = (actions, ), dtype = 'float32')
            # DDPG implementation assumes [-x, x] symmetric actions.
            # ppo1 and Rllib PPO implementation ignores size and very roughly initially assumes N(0, 1) actions, but potentially trainable to any value.
        self.observation_space_items = [
            'couple', 'num_401k', 'one_on_gamma',
            'years_expected',
            'lifespan_percentile_years', 'spia_expectancy_years', 'final_spias_purchase',
            'reward_to_go_estimate', 'relative_ce_estimate_individual',
            'log_ce_estimate_individual',
            'wealth_fraction',
            'stocks_price', 'stocks_volatility', 'real_interest_rate']
        self.observation_space_low  = [0, 0, 0,   0,   0,   0, 0, -2e3,   0,  0, 0, 0, 0, -0.15]
        self.observation_space_high = [1, 2, 1, 100, 100, 100, 1,   10, 200, 20, 1, 4, 7,  0.15]
        self.observation_space = Box(
            # Note: Couple status must be observation[0], or else change is_couple()
            #    in common/tf_util.py and baselines/baselines/ppo1/pposgd_dual.py.
            #
            # Values listed above are intended as an indicative ranges, not the absolute range limits.
            # Values are not used by ppo1. It is only the length that matters.
            low = np.repeat(-1, len(self.observation_space_low)).astype(np.float32) if params['observation_space_ignores_range']
                else np.array(self.observation_space_low, dtype = np.float32),
            high = np.repeat(1, len(self.observation_space_high)).astype(np.float32) if params['observation_space_ignores_range']
                else np.array(self.observation_space_high, dtype = np.float32),
            dtype = 'float32'
        )

        assert params['action_space_unbounded'] in (False, True)
        assert params['observation_space_ignores_range'] in (False, True)
        assert params['observation_space_clip'] in (False, True)

        self.fin = Fin(self, direct_action, params)

    def reset(self):

        return self.fin.reset()

    def step(self, action):

        return self.fin.step(action)
