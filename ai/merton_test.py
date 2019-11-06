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

# To train:
#
#     ./merton_test.py
#
# To evaluate:
#
#     ./merton_test.py ~/ray_results/PPO/PPO_MertonEnv_<sample>_<dir>/checkpoint_<n>/checkpoint-<n> \
#         --run PPO --config '{"sample_mode":true}' --steps 1000000 > /dev/null

from math import exp, isnan, log, sqrt, tanh
from os import remove
import pickle
from random import lognormvariate
from statistics import mean, stdev
from sys import argv, stderr
from tempfile import mkstemp

import numpy as np

from gym import Env
from gym.spaces import Box

import ray
from ray import tune
from ray.rllib import rollout
from ray.tune.registry import register_env

class MertonEnv(Env):

    def __init__(self, config):
        self.observation_space = Box(-1, 1, shape=[3], dtype='float32')
        self.action_space = Box(-10, 10, shape=[3], dtype='float32')
        self.rra = 6 # Relative risk aversion.
        self.income = 20000
        self.wealth0 = 2000000
        self.stocks_mu, self.stocks_sigma = self._mu_sigma(1.065, 0.174)
        self.bonds_mu, self.bonds_sigma = self._mu_sigma(1.010, 0.110)
        # Gompertz-Makeham mortality parameters.
        self.age_start = 65
        self.alpha = 0
        self.m = 82.3
        self.b = 11.4
        self._le_cache = {}
        self._alive_cache = {}

    def _mu_sigma(self, m, vol):
        # Convert return to lognormal.
        mu = log(m / sqrt(1 + (vol / m) ** 2))
        sigma = sqrt(log(1 + (vol / m) ** 2))
        return mu, sigma

    def _q(self, t):
        # Probability of dying in time period.
        age = self.age_start + t
        return max(0, min(self.alpha + exp((age - self.m) / self.b) / self.b, 1))

    def _alive(self, t):
        # Probability alive.
        try:
            return self._alive_cache[t]
        except KeyError:
            if t <= 0:
                alive = 1
            else:
                alive = self._alive(t - 1) * (1 - self._q(t - 1))
            self._alive_cache[t] = alive
            return alive

    def _le(self, t):
        # Life expectancy.
        try:
            return self._le_cache[t]
        except KeyError:
            q = self._q(t)
            if q < 1:
                le = 1 + (1 - q) * self._le(t + 1)
            else:
                le = 0
            self._le_cache[t] = le
            return le

    def reset(self):
        self.t = 0
        self.wealth = self.wealth0
        return self._observe()

    def _observe(self):
        if self._q(self.t) < 1:
            wealth_fraction = self.wealth / (self.income * self._le(self.t) + self.wealth)
            reward_to_go_estimate = self._alive(self.t) * self._le(self.t) * self._utility(self.income + self.wealth / self._le(self.t))
            scaled_reward_to_go_estimate = reward_to_go_estimate / 100 + 1
            obs = np.array([self._le(self.t) / 100, wealth_fraction, scaled_reward_to_go_estimate], dtype='float32')
            return np.clip(obs * 2 - 1, -1, 1)
        else:
            return np.repeat(-1, 3)

    def step(self, action):

        consume_action, stocks_action, bonds_action = action.tolist() # De-numpify,
        assert not isnan(consume_action) and not isnan(stocks_action) and not isnan(bonds_action)

        self.wealth += self.income
        consume_fraction = 0.1 + 0.9 * (1 + tanh(consume_action / 5))
        consume_estimate = self.wealth / self._le(self.t)
        consume = consume_fraction * consume_estimate
        consume = min(consume, self.wealth)
        self.wealth -= consume

        max_action = max(stocks_action, bonds_action)
        stocks = exp(stocks_action - max_action)
        bonds = exp(bonds_action - max_action)
        stocks = stocks / (stocks + bonds)
        try:
            wealth_ratio = self.income * self._le(self.t + 1) / self.wealth
        except ZeroDivisionError:
            wealth_ratio = 1e10
        stocks_fraction = max(0, min(stocks + 0.5 * wealth_ratio, 1))
        self.wealth *= stocks_fraction * lognormvariate(self.stocks_mu, self.stocks_sigma) + (1 - stocks_fraction) * lognormvariate(self.bonds_mu, self.bonds_sigma)

        self.t += 1
        done = self._q(self.t) == 1
        reward = self._alive(self.t) * self._utility(consume) / 1000
        return self._observe(), reward, done, {}

    def _utility(self, consume):
        return (consume / 100000) ** (1 - self.rra) / (1 - self.rra)

def train(address):

    ray.init(redis_address=address)

    tune.run(
        'PPO',
        num_samples = 10,
        config = {
            'env': MertonEnv,
            'clip_actions': False,
            'gamma': 1, # Finite time horizon with no discounting of the future.
            'lr': 5e-6, # Use small step size due to stochasticity of problem.
            'train_batch_size': 200000, # Should probably use a large batch size due to stochasticity of problem. Besides which 4000 fails with nans in the optimizer.
            'kl_coeff': 0.0, # Disable PPO KL-Penalty. Use PPO Clip only.
            'num_workers': 0,
        },
        stop = {
            'timesteps_total': 50000000,
        },
        checkpoint_freq = 10,
        checkpoint_at_end = True,
        max_failures = 20,
    )

def evaluate():

    register_env('Merton', lambda config: MertonEnv(config))
    parser = rollout.create_parser()
    args = parser.parse_args()
    args.env = 'Merton'
    f, args.out = mkstemp(prefix='rollout')
    del f
    args.no_render = True
    rollout.run(args, parser)
    rollouts = pickle.load(open(args.out, 'rb'))
    remove(args.out)
    rollouts = [rollout for rollout in rollouts if rollout[-1][-1]] # Complete rollouts only.
    rewards = [sum([reward for obs, action, next_obs, reward, done in rollout]) for rollout in rollouts]
    print('Mean episode reward:', mean(rewards), file = stderr)
    print('Standard error:', stdev(rewards) / sqrt(len(rewards)), file = stderr)

if __name__ == '__main__':
    if len(argv) <= 1:
        train(address='localhost:6379')
    else:
        evaluate()
