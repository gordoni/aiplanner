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

def weighted_stdev(value_weights, n0):
    n = 0
    s = 0
    ss = 0
    for value, weight in sorted(value_weights, key = lambda x: abs(x[1])):
        n += weight
        s += weight * value
        ss += weight * value ** 2
    return sqrt(n0 / (n0 - 1) * (n * ss - s ** 2) / (n ** 2))

class Evaluator(object):

    LOGFILE = 'gym_eval_batch.monitor.csv'

    def __init__(self, eval_env, eval_seed, eval_num_timesteps, eval_render):

        self.tstart = time.time()

        self.eval_env = eval_env
        self.eval_seed = eval_seed
        self.eval_num_timesteps = eval_num_timesteps
        self.eval_render = eval_render

        filename = os.path.join(logger.get_dir(), Evaluator.LOGFILE)
        self.f = open(filename, "wt")
        self.f.write('#%s\n'%json.dumps({"t_start": self.tstart, 'env_id' : self.eval_env.spec and self.eval_env.spec.id}))
        self.logger = csv.DictWriter(self.f, fieldnames=('r', 'l', 't', 'ce'))
        self.logger.writeheader()
        self.f.flush()

    def evaluate(self, pi):

        if self.eval_env == None:

            return False

        else:

            state = getstate()
            seed(self.eval_seed)

            env = self.eval_env.unwrapped
            rewards = []
            obs = self.eval_env.reset()
            s = 0
            e = 0
            while True:
                if self.eval_render:
                    self.eval_env.render()
                action = pi(obs)
                obs, r, done, info = self.eval_env.step(action)
                s += 1
                rewards.append((env.reward_value, env.reward_weight))
                if done:
                    e += 1
                    if self.eval_render:
                        self.eval_env.render()
                    obs = self.eval_env.reset()
                    if s >= self.eval_num_timesteps:
                        break

            batchrew = sum((v * w for v, w in rewards))
            rew = weighted_mean(rewards)
            try:
                std = weighted_stdev(rewards, e)
            except ZeroDivisionError:
                std = float('nan')
            stderr = std / sqrt(e) # Upper bound since assume episodes are not independent.
            utility = self.eval_env.unwrapped.utility
            ce = utility.inverse(rew)
            ce_stderr = utility.inverse(rew + stderr) - ce
            low = weighted_percentile(rewards, 2.5)
            high = weighted_percentile(rewards, 97.5)

            logger.info('Evaluation certainty equivalent: ', ce, ' +/- ', ce_stderr, ' (95% confidence interval: ', utility.inverse(low), ' - ', utility.inverse(high), ')')

            batchinfo = {'r': round(batchrew, 6), 'l': s, 't': round(time.time() - self.tstart, 6), 'ce': ce}
            self.logger.writerow(batchinfo)
            self.f.flush()

            setstate(state)

            return ce, ce_stderr
