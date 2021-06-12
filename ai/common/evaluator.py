# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

import csv
from math import ceil, sqrt
from itertools import chain
import os
from random import getstate, seed
from statistics import mean, stdev, StatisticsError

import numpy as np

from scipy.signal import savgol_filter

from common.utils import AttributeObject

def weighted_percentiles(value_weights, pctls):
    if len(value_weights[0]) == 0:
        return [float('nan')] * len(pctls)
    results = []
    pctls = list(pctls)
    tot = sum(value_weights[1])
    weight = 0
    for v, w in zip(*value_weights):
        v = float(v) # De-numpyify.
        w = float(w)
        weight += w
        if weight >= pctls[0] / 100 * tot:
            results.append(v)
            pctls.pop(0)
            if not pctls:
                return results
    while pctls:
        results.append(v)
        pctls.pop()
    return results

def weighted_mean(value_weights):
    n = 0
    s = 0
    for v, w in zip(*value_weights):
        v = float(v)
        w = float(w)
        n += w
        s += w * v
    try:
        return s / n
    except ZeroDivisionError:
        return float('nan')

def weighted_stdev(value_weights):
    n0 = 0
    n = 0
    s = 0
    ss = 0
    for v, w in zip(*value_weights):
        v = float(v)
        w = float(w)
        if w != 0:
            n0 += 1
        n += w
        s += w * v
        ss += w * v ** 2
    try:
        return sqrt(n0 / (n0 - 1) * (n * ss - s ** 2) / (n ** 2))
    except ValueError:
        return 0
    except (FloatingPointError, ZeroDivisionError):
        return float('nan')

def weighted_ppf(value_weights, q):
    if len(value_weights[0]) == 0:
        return float('nan')
    n = 0
    ppf = 0
    for v, w in zip(*value_weights):
        v = float(v)
        w = float(w)
        n += w
        if v <= q:
            ppf += w
    return ppf / n * 100

def pack_value_weights(value_weights, length = 2):

    if len(value_weights) > 0:
        return np.array(value_weights).T
    else:
        return np.array([()] * length)

def unpack_value_weights(value_weights):

    return np.array(value_weights).T

class Evaluator(object):

    def __init__(self, eval_envs, eval_seed, eval_num_timesteps, *,
        remote_evaluators = None, render = False, eval_batch_monitor = False,
        num_trace_episodes = 0, pdf_buckets = 100, cdf_buckets = 100, pdf_raw_buckets = 10000, pdf_smoothing_window = 0.02, pdf_constant_initial_consume = False,
        cr_cls = [0.80, 0.95]):

        self.eval_envs = eval_envs
        self.eval_seed = eval_seed
        self.eval_num_timesteps = eval_num_timesteps
        self.remote_evaluators = remote_evaluators
        self.eval_render = render
        self.eval_batch_monitor = eval_batch_monitor # Unused.
        self.num_trace_episodes = num_trace_episodes
        self.pdf_buckets = pdf_buckets
        self.cdf_buckets = cdf_buckets
        self.pdf_raw_buckets = pdf_raw_buckets
        self.pdf_smoothing_window = pdf_smoothing_window
        self.pdf_constant_initial_consume = pdf_constant_initial_consume
        self.cr_cls = cr_cls

        if self.remote_evaluators:
            self.eval_num_timesteps = ceil(self.eval_num_timesteps / len(self.remote_evaluators))
            self.num_trace_episodes = ceil(self.num_trace_episodes / len(self.remote_evaluators))

        self.trace = []
        self.episode = {}

    def trace_step(self, i, done, info = None):

        try:
            episode = self.episode[i]
        except KeyError:
            episode = {}
            self.episode[i] = episode

        if done:

            self.trace.append(episode)
            del self.episode[i]

        else:

            for item in (
                'age',
                'alive_count',
                'total_guaranteed_income',
                'portfolio_wealth_pretax',
                'consume',
                'real_spias_purchase',
                'nominal_spias_purchase',
                'asset_allocation',
            ):
                value = info[item]
                if item == 'asset_allocation':
                    value = value.as_list()
                try:
                    episode[item].append(value)
                except KeyError:
                    episode[item] = [value]

    def merge_warnings(self, warnings_list):

        warnings = {}
        for warnings in warnings_list:
            for msg, data in warnings.items():
                try:
                    warnings[msg]['count'] += data['count']
                except KeyError:
                    warnings[msg] = dict(data)

        return warnings

    def evaluate(self, pi):

        def rollout(eval_envs, pi):

            envs = tuple(eval_env.fin for eval_env in eval_envs)
            for env in envs:
                env.set_info(rewards = True)
            tracing = [False] * len(eval_envs)
            for i in range(min(self.num_trace_episodes, len(eval_envs))):
                envs[i].set_info(rollouts = True)
                tracing[i] = True
            rewards = []
            erewards = []
            estates = []
            obss = [eval_env.reset() for eval_env in eval_envs]
            et = sum(tracing)
            e = 0
            s = 0
            erews = [0 for _ in eval_envs]
            eweights = [0 for _ in eval_envs]
            reward_initial = None
            weight_sum = 0
            consume_mean = 0
            consume_m2 = 0
            finished = [False] * len(eval_envs)
            anticipated = 0
            for i, env in enumerate(envs):
                if anticipated < self.eval_num_timesteps:
                    anticipated += env.anticipated_episode_length
                else:
                    finished[i] = True
            while True:
                actions = pi(obss)
                if self.eval_render:
                    eval_envs[0].render()
                for i, (eval_env, env, action) in enumerate(zip(eval_envs, envs, actions)):
                    if not finished[i]:
                        obs, r, done, info = eval_env.step(action)
                        if tracing[i]:
                            self.trace_step(i, False, info)
                        s += 1
                        age = info['age']
                        weight = info['reward_weight']
                        consume = info['reward_consume']
                        reward = info['reward_value']
                        estate_weight = info['estate_weight']
                        estate_value = info['estate_value']
                        estates.append((estate_value, estate_weight))
                        if weight != 0:
                            rewards.append((reward, weight, age))
                            erews[i] += reward * weight
                            eweights[i] += weight
                            if reward_initial is None and s == 1:
                                reward_initial = reward
                            # https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
                            weight_sum += weight
                            delta = consume - consume_mean
                            consume_mean += (weight / weight_sum) * delta
                            delta2 = consume - consume_mean
                            consume_m2 += weight * delta * delta2
                        if done:
                            if tracing[i]:
                                self.trace_step(i, True)
                                if et < self.num_trace_episodes:
                                    et += 1
                                else:
                                    env.set_info(rollouts = False)
                                    tracing[i] = False
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
                            if anticipated >= self.eval_num_timesteps:
                                finished[i] = True
                            else:
                                obss[i] = eval_env.reset()
                                anticipated += env.anticipated_episode_length
                        else:
                            obss[i] = obs
                if all(finished):
                    break

            assert s == anticipated

            warnings = self.merge_warnings(tuple(env.warnings for env in envs))

            return pack_value_weights(sorted(rewards), length = 3), pack_value_weights(sorted(erewards)), pack_value_weights(sorted(estates)), \
                reward_initial, weight_sum, consume_mean, consume_m2, self.trace, warnings

        self.object_ids = None
        self.exception = None

        if self.eval_envs is None:

            return False

        elif self.remote_evaluators and self.eval_num_timesteps > 0:

            # New workers are assigned consecutive seeds, currently starting at the TFRunner runner_seed parameter value * 1000.

            def make_pi(policy_graph):
                return lambda obss: policy_graph.compute_actions(obss)[0]

            # Rllib developer API way:
            #     self.object_ids = [e.apply.remote(lambda e: e.foreach_env(lambda env: rollout([env], make_pi(e.get_policy())))) for e in self.remote_evaluators]
            # Fast way (rollout() batches calls to policy when multiple envs):
            self.object_ids = [e.apply.remote(lambda e: [rollout(e.async_env.get_unwrapped(), make_pi(e.get_policy()))]) for e in self.remote_evaluators]

            return self.object_ids

        else:

            # Seed used here is not compatible with seed used when Ray workers are employed.

            seed(self.eval_seed)
            np.random.seed(self.eval_seed)

            try:
                self.reward_ages, self.erewards, self.estates, self.reward_initial, self.weight_sum, self.consume_mean, self.consume_m2, self.trace, self.warnings = \
                    rollout(self.eval_envs, pi)
            except Exception as e:
                self.exception = e # Only want to know about failures in one place; later in summarize().

            return None

    def summarize(self):

        if self.object_ids:

            import ray

            rollouts = ray.get(self.object_ids)

            rewards, erewards, estates, reward_initials, weight_sums, consume_means, consume_m2s, traces, warnings = zip(*chain(*rollouts))
            if len(rewards) > 1:
                self.reward_ages = pack_value_weights(np.sort(np.concatenate([unpack_value_weights(reward) for reward in rewards], axis = 0)), length = 3)
                self.erewards = pack_value_weights(np.sort(np.concatenate([unpack_value_weights(ereward) for ereward in erewards], axis = 0)))
                self.estates = pack_value_weights(np.sort(np.concatenate([unpack_value_weights(estate) for estate in estates], axis = 0)))
            else:
                self.reward_ages = rewards[0]
                self.erewards = erewards[0]
                self.estates = estates[0]

            self.reward_initial = reward_initials[0]

            # https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
            self.weight_sum = 0
            self.consume_mean = 0
            self.consume_m2 = 0
            for weight_sum, consume_mean, consume_m2 in zip(weight_sums, consume_means, consume_m2s):
                if weight_sum > 0:
                    self.weight_sum += weight_sum
                    delta = consume_mean - self.consume_mean
                    self.consume_mean += (weight_sum / self.weight_sum) * delta
                    self.consume_m2 += consume_m2 + delta ** 2 * (self.weight_sum - weight_sum) * weight_sum / self.weight_sum

            self.trace = tuple(chain(*traces))[:self.num_trace_episodes]

            self.warnings = self.merge_warnings(warnings)

        else:

            if self.exception:
                raise self.exception

        estate_max, = weighted_percentiles(self.estates, [98])
        if estate_max == 0:
            estate_max = 1
        estate_step = estate_max / self.pdf_raw_buckets
        estate_pdf, estate_cdf = self.pdf_cdf('estate', self.estates, 0, 0, estate_max, estate_step)

        del self.estates # Conserve RAM.

        self.rewards = self.reward_ages[0:2]

        rew = weighted_mean(self.erewards)
        try:
            std = weighted_stdev(self.erewards)
        except ZeroDivisionError:
            std = float('nan')
        try:
            stderr = std / sqrt(len(self.erewards[0]))
                # Standard error is ill-defined for a weighted sample.
                # Here we are incorrectly assuming each episode carries equal weight.
                # Use erewards rather than rewards because episode rewards are correlated.
        except ZeroDivisionError:
            stderr = float('nan')
        env = self.eval_envs[0].fin
        params = AttributeObject(env.params_dict)
        env.reset()
        utility = env.utility
        unit_ce = indiv_ce = utility.inverse(rew)
        unit_ce_stderr = indiv_ce_stderr = indiv_ce - utility.inverse(rew - stderr)
        ce_min, indiv_low, indiv_high, ce_max = (utility.inverse(u) for u in weighted_percentiles(self.rewards, [2, 10, 90, 98]))
        unit_low = indiv_low
        unit_high = indiv_high

        unit_consume_mean = indiv_consume_mean = self.consume_mean
        try:
            unit_consume_stdev = indiv_consume_stdev = sqrt(self.consume_m2 / (self.weight_sum - 1))
        except (ValueError, ZeroDivisionError):
            unit_consume_stdev = indiv_consume_stdev = float('nan')

        couple = env.sex2 is not None

        if ce_max == 0:
            ce_max = 1
        ce_step = max((ce_max - ce_min) / self.pdf_raw_buckets, ce_max / 100000)
        if not self.pdf_constant_initial_consume and self.reward_initial is not None:
            # Removing any constant initial reward gets rid of a spike in pdf at first consumption value for retirement scenarios.
            # Doing this is technically incorrect, but less confusing to niave users.
            # Additionally the spike doesn't smooth well. It typically produces a trough before and after, which may be captured in the plot depending on where the steps fall.
            j = np.where(self.rewards[0] == self.reward_initial)[0][0]
            assert all(self.rewards[0][i] == self.reward_initial for i in range(j, j + len(self.erewards[0])))
            self.rewards = tuple(np.delete(self.rewards[i], np.s_[j:j + len(self.erewards[0])]) for i in range(2))
                # Should really only remove matching weights, but likelihood of non-initial reward matching exact floating point initial reward is minimal.
        consume_pdf, consume_cdf = self.pdf_cdf('consume', self.rewards, 0, ce_min, ce_max, ce_step, utility.utility, 1 + params.consume_additional if couple else 1)

        del self.rewards # Conserve RAM.
        del self.erewards

        age_rewards = np.vstack((self.reward_ages[2], self.reward_ages[0:2])) # Age row first.
        del self.reward_ages # Conserve RAM.
        consume_cr = self.age_cr('consume', age_rewards, self.cr_cls, utility.inverse, 1 + params.consume_additional if couple else 1)

        if couple:
            unit_ce *= 1 + params.consume_additional
            unit_ce_stderr *= 1 + params.consume_additional
            unit_low *= 1 + params.consume_additional
            unit_high *= 1 + params.consume_additional
            unit_consume_mean *= 1 + params.consume_additional
            unit_consume_stdev *= 1 + params.consume_additional

        ages = []
        for i in range(max(len(env.alive_both), len(env.alive_one))):
            ages.append(env.age + i * params.time_period)
        alive = {'age': ages, 'couple': env.alive_both, 'single': env.alive_one}

        warnings = sorted(msg for msg, data in self.warnings.items() if data['count'] > data['timestep_ok_fraction'] * self.eval_num_timesteps)

        return {
            'couple': couple,
            'ce': unit_ce,
            'ce_stderr': unit_ce_stderr,
            'consume10': unit_low,
            'consume90': unit_high,
            'consume_mean': unit_consume_mean,
            'consume_stdev': unit_consume_stdev,
            'ce_individual': indiv_ce,
            'ce_stderr_individual': indiv_ce_stderr,
            'consume10_individual': indiv_low,
            'consume90_individual': indiv_high,
            'consume_pdf': consume_pdf,
            'consume_cdf': consume_cdf,
            'estate_pdf': estate_pdf,
            'estate_cdf': estate_cdf,
            'consume_cr': consume_cr,
            'paths': self.trace,
            'alive': alive,
            'warnings': warnings,
        }

    def pdf_cdf(self, what, value_weights, de_minus_low, low, high, step, f = lambda x: x, multiplier = 1):

        pdf = {what: [], 'weight': []}
        cdf = {what: [], 'probability': []}
        try:
            buckets = ceil((high - de_minus_low) / step)
        except ValueError:
            pdf[what].append(0)
            pdf['weight'].append(0)
            cdf[what].append(0)
            cdf['probability'].append(0)
            return pdf, cdf
        polyorder = 3
        half_window_size = max(2, self.pdf_smoothing_window * (high - low) / step // 2) # 2 * half_window_size + 1 must exceed polyorder.
        bucket_weights = []
        c_ceil = de_minus_low
        u_ceil = f(c_ceil)
        u_floor = u_ceil
        for r, w in zip(*value_weights):
            r = float(r)
            w = float(w)
            while r >= u_ceil and len(bucket_weights) < buckets + half_window_size:
                bucket_weights.append(0)
                u_floor = u_ceil
                c_ceil += step
                u_ceil = f(c_ceil)
            if u_floor <= r < u_ceil:
                bucket_weights[-1] += w
        while len(bucket_weights) < buckets + half_window_size:
            bucket_weights.append(0)
        w_tot = sum(value_weights[1])

        cdf_weights = [0.0]
        cdf_weight = 0
        bucket = 0
        while bucket < buckets:
            cdf_weight += bucket_weights[bucket]
            bucket += 1
            while len(cdf_weights) < bucket * self.cdf_buckets / buckets:
                cdf_weights.append(cdf_weight)
        for bucket in range(len(cdf_weights)):
            unit_c = (de_minus_low + step * buckets / self.cdf_buckets * bucket) * multiplier
            try:
                prob = cdf_weights[bucket] / w_tot
            except ZeroDivisionError:
                prob = float('nan')
            cdf[what].append(unit_c)
            cdf['probability'].append(prob)

        bucket_weights = savgol_filter(bucket_weights, half_window_size * 2 + 1, polyorder, mode = 'constant')
        bucket_weights = tuple(max(0, bucket_weights[round(bucket / self.pdf_buckets * buckets)]) for bucket in range(self.pdf_buckets))
        for bucket in range(self.pdf_buckets):
            unit_c = (de_minus_low + step * buckets / self.pdf_buckets * (bucket + 0.5)) * multiplier
            try:
                w_ratio = bucket_weights[bucket] / w_tot / step
            except ZeroDivisionError:
                w_ratio = float('nan')
            pdf[what].append(unit_c)
            pdf['weight'].append(w_ratio)

        return pdf, cdf

    def age_cr(self, what, age_value_weights, cls, f = lambda x: x, multiplier = 1):
        '''Compute age-based confidence region.'''

        consume_cr = []

        if age_value_weights.shape[1] > 0:

            age_value_weights = age_value_weights.T # Each row comprises an age value, and weight.
            age_value_weights = age_value_weights[age_value_weights[:, 1].argsort(kind = 'stable')]
            age_value_weights = age_value_weights[age_value_weights[:, 0].argsort(kind = 'stable')] # Sorted by age and value.
            age_value_weights = np.split(age_value_weights, np.where(np.diff(age_value_weights[:, 0]))[0] + 1) # Split by age.
            cweight_age_value_weights = []
            for age_value_weight in age_value_weights:
                low_sum = np.cumsum(age_value_weight[:, 2])
                high_sum = np.flip(np.cumsum(np.flip(age_value_weight[:, 2])))
                use_high = high_sum <= low_sum
                i = np.where(use_high)[0][0]
                bi_sum = np.concatenate((low_sum[:i], high_sum[i:]))
                cweight_age_value_weight = np.c_[bi_sum, age_value_weight]
                cweight_age_value_weights.append(cweight_age_value_weight)
            del age_value_weights
            cweight_age_value_weights = np.concatenate(cweight_age_value_weights) # Weights are now bidirectionally cumulative by age.
            cweight_age_value_weights = cweight_age_value_weights[cweight_age_value_weights[:, 0].argsort(kind = 'stable')] # Sorted by cumulative weight.
            tot_weight = np.sum(cweight_age_value_weights[:, 3])

            for cl in cls:

                cutoff = (1 - cl) * tot_weight
                i = np.where(np.cumsum(cweight_age_value_weights[:, 3]) >= cutoff)[0][0]
                age_values = cweight_age_value_weights[i:, 1:3] # Confidence region.
                age_values = age_values[age_values[:, 1].argsort(kind = 'stable')]
                age_values = age_values[age_values[:, 0].argsort(kind = 'stable')]
                w = np.where(np.diff(age_values[:, 0]))[0]
                cr_age = np.concatenate((age_values[w, 0], [age_values[-1, 0]]))
                cr_low = np.concatenate(([age_values[0, 1]], age_values[w + 1, 1]))
                cr_high = np.concatenate((age_values[w, 1], [age_values[-1, 1]]))
                cr_low = np.vectorize(f)(cr_low) * multiplier
                cr_high = np.vectorize(f)(cr_high) * multiplier
                cr_age = cr_age.tolist() # De-numpyify.
                cr_low = cr_low.tolist()
                cr_high = cr_high.tolist()

                consume_cr.append({
                    'confidence_level': cl,
                    'age': cr_age,
                    'low': cr_low,
                    'high': cr_high,
                })

        return consume_cr
