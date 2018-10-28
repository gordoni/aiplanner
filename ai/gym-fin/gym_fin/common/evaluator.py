#!/usr/bin/python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

import csv
import json
import os
from math import sqrt
from random import getstate, seed, setstate
from statistics import mean, stdev, StatisticsError
import time

import numpy as np

from baselines import logger

def weighted_percentile(value_weights, pctl):
    assert value_weights
    tot = sum((w for v, w in value_weights))
    weight = 0
    for v, w in sorted(value_weights):
        weight += w
        if weight >= pctl / 100 * tot:
            return v
    return v

def weighted_mean(value_weights):
    n = 0
    s = 0
    for value, weight in sorted(value_weights, key = lambda x: abs(x[1])):
        n += weight
        s += weight * value
    return s / n

def weighted_stdev(value_weights):
    n0 = 0
    n = 0
    s = 0
    ss = 0
    for value, weight in sorted(value_weights, key = lambda x: abs(x[1])):
        if weight != 0:
            n0 += 1
        n += weight
        s += weight * value
        ss += weight * value ** 2
    return sqrt(n0 / (n0 - 1) * (n * ss - s ** 2) / (n ** 2))

class Evaluator(object):

    LOGFILE = 'gym_eval_batch.monitor.csv'

    def __init__(self, eval_env, eval_seed, eval_num_timesteps, *, render = False, eval_batch_monitor = False, num_trace_episodes = 0):

        self.tstart = time.time()

        self.eval_env = eval_env
        self.eval_seed = eval_seed
        self.eval_num_timesteps = eval_num_timesteps
        self.eval_render = render
        self.eval_batch_monitor = eval_batch_monitor
        self.num_trace_episodes = num_trace_episodes

        self.trace = []
        self.episode = []

        if eval_batch_monitor:
            filename = os.path.join(logger.get_dir(), Evaluator.LOGFILE)
            self.f = open(filename, "wt")
            self.f.write('#%s\n'%json.dumps({"t_start": self.tstart, 'env_id' : self.eval_env.spec and self.eval_env.spec.id}))
            self.logger = csv.DictWriter(self.f, fieldnames=('r', 'l', 't', 'ce'))
            self.logger.writeheader()
            self.f.flush()

    def trace_step(self, env, action, done):

        if not done:
            decoded_action = env.interpret_action(action)
        self.episode.append({
            'age': env.age,
            'alive_count': env.alive_count[env.episode_length],
            'gi_sum': env.gi_sum() if not done else None,
            'p_sum': env.p_sum(),
            'consume': decoded_action['consume'] if not done else None,
        })

        if done:
            self.trace.append(self.episode)
            self.episode = []

    def evaluate(self, pi):

        if self.eval_env == None:

            return False

        else:

            state = getstate()
            seed(self.eval_seed)

            env = self.eval_env.unwrapped
            rewards = []
            erewards = []
            obs = self.eval_env.reset()
            s = 0
            e = 0
            erew = 0
            eweight = 0
            while True:
                action = pi(obs)
                if e < self.num_trace_episodes:
                    self.trace_step(env, action, False)
                if self.eval_render:
                    self.eval_env.render()
                obs, r, done, info = self.eval_env.step(action)
                erew += r
                eweight += env.reward_weight
                s += 1
                rewards.append((env.reward_value, env.reward_weight))
                if done:
                    if e < self.num_trace_episodes:
                        self.trace_step(env, None, done)
                    try:
                        er = erew / eweight
                    except ZeroDivisionError:
                        er = 0
                    erewards.append((er, eweight))
                    erew = 0
                    eweight = 0
                    e += 1
                    if self.eval_render:
                        self.eval_env.render()
                    obs = self.eval_env.reset()
                    if s >= self.eval_num_timesteps:
                        break

            rew = weighted_mean(erewards)
            try:
                std = weighted_stdev(erewards)
            except ZeroDivisionError:
                std = float('nan')
            stderr = std / sqrt(e)
            utility = env.utility
            ce = utility.inverse(rew)
            ce_stderr = utility.inverse(rew + stderr) - ce
            low = utility.inverse(weighted_percentile(rewards, 10))
            high = utility.inverse(weighted_percentile(rewards, 90))

            logger.info('Evaluation certainty equivalent: ', ce, ' +/- ', ce_stderr, ' (80% confidence interval: ', low, ' - ', high, ')')

            if self.eval_batch_monitor:
                batchrew = sum((v * w for v, w in erewards))
                batchinfo = {'r': round(batchrew, 6), 'l': s, 't': round(time.time() - self.tstart, 6), 'ce': ce}
                self.logger.writerow(batchinfo)
                self.f.flush()

            setstate(state)

            return ce, ce_stderr, low, high
