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
from random import getstate, seed, setstate
from statistics import mean, stdev
import time

from baselines import logger

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
        self.logger = csv.DictWriter(self.f, fieldnames=('r', 'l', 't', 'ce', 'ce_stdev'))
        self.logger.writeheader()
        self.f.flush()

    def evaluate(self, pi):

        if self.eval_env is not None:

            state = getstate()
            seed(self.eval_seed)

            rewards = []
            obs = self.eval_env.reset()
            observation = self.eval_env.unwrapped.decode_observation(obs)
            life_expectancy = observation['life_expectancy']
            eprew = []
            t = 0
            while True:
                if self.eval_render:
                    self.eval_env.render()
                action = pi(obs)
                obs, r, done, info = self.eval_env.step(action)
                t += 1
                eprew.append(r)
                if done:
                    rewards.append(sum(eprew))
                    if self.eval_render:
                        self.eval_env.render()
                    obs = self.eval_env.reset()
                    eprew = []
                    if t >= self.eval_num_timesteps:
                        break

            batchrew = sum(rewards)
            rew = mean(rewards) / life_expectancy
            std = stdev(rewards) / life_expectancy
            utility = self.eval_env.unwrapped.utility
            ce = utility.inverse(rew)
            ce_stdev = ce - utility.inverse(rew - std)

            print('Evaluation certainty equivalent:', ce, '+/-', ce_stdev)

            batchinfo = {'r': round(batchrew, 6), 'l': self.eval_num_timesteps, 't': round(time.time() - self.tstart, 6), 'ce': ce, 'ce_stdev': ce_stdev}
            self.logger.writerow(batchinfo)
            self.f.flush()

            setstate(state)

        return False
