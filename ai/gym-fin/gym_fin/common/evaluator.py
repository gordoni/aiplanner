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

    def __init__(self, eval_env, eval_seed, nb_eval_steps, render_eval):

        self.tstart = time.time()

        self.eval_env = eval_env
        self.eval_seed = eval_seed
        self.nb_eval_steps = nb_eval_steps
        self.render_eval = render_eval

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
            for _ in range(self.nb_eval_steps):
                if self.render_eval:
                    self.eval_env.render()
                action = pi(obs)
                obs, r, done, info = self.eval_env.step(action)
                rewards.append(r)
                if done:
                    if self.render_eval:
                        self.eval_env.render()
                    obs = self.eval_env.reset()

            batchrew = sum(rewards)
            rew = mean(rewards)
            std = stdev(rewards)
            utility = self.eval_env.unwrapped.utility
            ce = utility.inverse(rew)
            ce_stdev = ce - utility.inverse(rew - std)

            print('Evaluation CE:', ce, '+/-', ce_stdev)

            batchinfo = {'r': round(batchrew, 6), 'l': self.nb_eval_steps, 't': round(time.time() - self.tstart, 6), 'ce': ce, 'ce_stdev': ce_stdev}
            self.logger.writerow(batchinfo)
            self.f.flush()

            setstate(state)

        return False
