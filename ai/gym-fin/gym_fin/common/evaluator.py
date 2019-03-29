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
import time
from itertools import chain
from math import sqrt
from random import getstate, seed, setstate
from statistics import mean, stdev, StatisticsError

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
    try:
        return sqrt(n0 / (n0 - 1) * (n * ss - s ** 2) / (n ** 2))
    except ValueError:
        return 0

def weighted_ppf(value_weights, q):
    n = 0
    ppf = 0
    for value, weight in sorted(value_weights, key = lambda x: abs(x[1])):
        n += weight
        if value <= q:
            ppf += weight
    return ppf / n * 100

class Evaluator(object):

    LOGFILE = 'gym_eval_batch.monitor.csv'

    def __init__(self, eval_envs, eval_seed, eval_num_timesteps, *,
        remote_evaluators = None, render = False, eval_batch_monitor = False, num_trace_episodes = 0, pdf_buckets = 10):

        self.tstart = time.time()

        self.eval_envs = eval_envs
        self.eval_seed = eval_seed
        self.eval_num_timesteps = eval_num_timesteps
        self.remote_evaluators = remote_evaluators
        self.eval_render = render
        self.eval_batch_monitor = eval_batch_monitor
        self.num_trace_episodes = num_trace_episodes
        self.pdf_buckets = pdf_buckets

        if self.remote_evaluators:
            self.eval_num_timesteps /= len(self.remote_evaluators)

        self.trace = []
        self.episode = []

        if eval_batch_monitor:
            filename = os.path.join(logger.get_dir(), Evaluator.LOGFILE)
            self.f = open(filename, "wt")
            self.f.write('#%s\n'%json.dumps({"t_start": self.tstart, 'env_id' : self.eval_envs[0].spec and self.eval_envs[0].spec.id}))
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
            'real_spias_purchase': decoded_action['real_spias_purchase'] if not done else None,
            'nominal_spias_purchase': decoded_action['nominal_spias_purchase'] if not done else None,
            'asset_allocation': decoded_action['asset_allocation'] if not done else None,
        })

        if done:
            self.trace.append(self.episode)
            self.episode = []

    def evaluate(self, pi):

        def rollout(eval_envs, pi):

            envs = tuple(eval_env.unwrapped for eval_env in eval_envs)
            rewards = []
            erewards = []
            obss = [eval_env.reset() for eval_env in eval_envs]
            et = 0
            e = 0
            s = 0
            erews = [0 for _ in eval_envs]
            eweights = [0 for _ in eval_envs]
            finished = [False for _ in eval_envs]
            while True:
                actions = pi(obss)
                if et < self.num_trace_episodes:
                    self.trace_step(envs[0], actions[0], False)
                if self.eval_render:
                    eval_envs[0].render()
                for i, (eval_env, env, action) in enumerate(zip(eval_envs, envs, actions)):
                    if not finished[i]:
                        obs, r, done, info = eval_env.step(action)
                        reward = env.reward_value
                        weight = env.reward_weight
                        erews[i] += reward * weight
                        eweights[i] += weight
                        s += 1
                        if weight != 0:
                            rewards.append((reward, weight))
                        if done:
                            if i == 0 and et < self.num_trace_episodes:
                                self.trace_step(env, None, done)
                                et += 1
                            e += 1
                            try:
                                er = erews[i] / eweights[i]
                            except ZeroDivisionError:
                                er = 0
                            erewards.append((er, eweights[i]))
                            erews[i] = 0
                            eweights[i] = 0
                            if i == 0 and self.eval_render:
                                eval_env.render()
                            obss[i] = eval_env.reset()
                            if s >= self.eval_num_timesteps:
                                finished[i] = True
                        else:
                            obss[i] = obs
                if all(finished):
                    break

            return rewards, erewards, self.trace

        state = getstate()

        if self.eval_envs == None:

            return False

        elif self.remote_evaluators:

            # Have no control over the random seed used by each remote evaluator.
            # If they are ever always the same, we would be restricted to a single remote evaluator.
            # Currently the remote seed is random.

            import ray

            def make_pi(policy_graph):
                return lambda obss: policy_graph.compute_actions(obss)[0]

            rollouts = ray.get([e.apply.remote(lambda e: e.foreach_env(lambda env: rollout([env], make_pi(e.get_policy())))) for e in self.remote_evaluators])

            rewards, erewards, trace = (tuple(chain(*l)) for l in zip(*chain(*rollouts))) # Flatten remote environments.

            self.trace = trace[:self.num_trace_episodes]

        else:

            seed(self.eval_seed)

            rewards, erewards, trace = rollout(self.eval_envs, pi)

        rew = weighted_mean(erewards)
        try:
            std = weighted_stdev(erewards)
        except ZeroDivisionError:
            std = float('nan')
        stderr = std / sqrt(len(erewards))
            # Standard error is ill-defined for a weighted sample.
            # Here we are incorrectly assuming each episode carries equal weight.
        env = self.eval_envs[0].unwrapped
        utility = env.utility
        unit_ce = indiv_ce = utility.inverse(rew)
        unit_ce_stderr = indiv_ce_stderr = indiv_ce - utility.inverse(rew - stderr)
        unit_low = indiv_low = utility.inverse(weighted_percentile(rewards, 10))
        unit_high = indiv_high = utility.inverse(weighted_percentile(rewards, 90))

        utility_preretirement = utility.utility(env.params.consume_preretirement_low)
        self.preretirement_ppf = weighted_ppf(rewards, utility_preretirement) / 100

        u_min = utility.inverse(weighted_percentile(rewards, 2))
        u_max = utility.inverse(weighted_percentile(rewards, 98))
        pdf_bucket_weights = [0] * (self.pdf_buckets + 4)
        w_tot = 0
        for r, w in rewards:
            try:
                bucket = 2 + int((utility.inverse(r) - u_min) / (u_max - u_min) * self.pdf_buckets)
            except ZeroDivisionError:
                bucket = 2
            try:
                pdf_bucket_weights[bucket] += w
            except IndexError:
                pass
            w_tot += w
        self.consume_pdf = []
        for bucket, w in enumerate(pdf_bucket_weights):
            unit_consume = u_min + (bucket - 1.5) * (u_max - u_min) / self.pdf_buckets
            if env.params.sex2 != None:
                unit_consume *= 1 + env.params.consume_additional
            self.consume_pdf.append((unit_consume, w / w_tot))

        if env.params.sex2 != None:
            unit_ce *= 1 + env.params.consume_additional
            unit_ce_stderr *= 1 + env.params.consume_additional
            unit_low *= 1 + env.params.consume_additional
            unit_high *= 1 + env.params.consume_additional
            print('Couple certainty equivalent:', unit_ce, '+/-', unit_ce_stderr, '(80% confidence interval:', unit_low, '-', str(unit_high) + ')')

        print('Evaluation certainty equivalent:', indiv_ce, '+/-', indiv_ce_stderr, '(80% confidence interval:', indiv_low, '-', str(indiv_high) + ')')

        if self.eval_batch_monitor:
            batchrew = sum((v * w for v, w in erewards))
            batchinfo = {'r': round(batchrew, 6), 'l': s, 't': round(time.time() - self.tstart, 6), 'ce': indiv_ce}
            self.logger.writerow(batchinfo)
            self.f.flush()

        setstate(state)

        return unit_ce, unit_ce_stderr, unit_low, unit_high
