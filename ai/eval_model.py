#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import ceil, exp

import numpy as np

import tensorflow as tf

from baselines import logger
from baselines.common import (
    tf_util as U,
    boolean_flag,
)
from baselines.common.misc_util import set_global_seeds

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator

def pi_merton(env, obs, continuous_time = False):
    observation = env.decode_observation(obs)
    life_expectancy = observation['life_expectancy']
    gamma = env.params.gamma
    mu = env.stocks.mu
    sigma = env.stocks.sigma
    r = env.bills.mu
    alpha = mu + sigma ** 2 / 2
    stocks_allocation = (alpha - r) / (sigma ** 2 * gamma)
    nu = ((gamma - 1) / gamma) * ((alpha - r) * stocks_allocation / 2 + r)
    if nu == 0:
        consume_fraction = 1 / life_expectancy
    elif continuous_time:
        # Merton.
        consume_fraction = nu / (1 - exp(- nu * life_expectancy))
    else:
        # Samuelson.
        a = exp(nu * env.params.time_period)
        t = ceil(life_expectancy / env.params.time_period) - 1
        consume_fraction = a ** t * (a - 1) / (a ** (t + 1) - 1) / env.params.time_period
    return consume_fraction, stocks_allocation

def run(eval_model_params, *, merton, samuelson, annuitize, eval_seed, eval_num_timesteps, eval_render, model_dir):

    assert sum((model_dir != 'aiplanner.tf', merton, samuelson, annuitize)) <= 1
    merton_or_samuelson_or_annuitize = merton or samuelson or annuitize

    eval_seed += 1000000 # Use a different seed than might have been used during training.
    set_global_seeds(eval_seed)
    eval_env = make_fin_env(**eval_model_params, action_space_unbounded = not merton_or_samuelson_or_annuitize, direct_action = merton_or_samuelson_or_annuitize)
    env = eval_env.unwrapped
    obs = eval_env.reset()

    if merton or samuelson:

        consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
        p, consume, real_spias_purchase, nominal_spias_purchase = env.spend(consume_fraction)
        asset_allocation = AssetAllocation(stocks = stocks_allocation, bills = 1 - stocks_allocation)
        real_bonds_duration = nominal_bonds_duration = None

    elif annuitize:

        consume_initial = env.gi_real + env.gi_nominal + env.p_notax / (1 + env.real_spia.premium(1, mwr = env.params.real_spias_mwr))
        consume_fraction_initial = consume_initial / env.p_plus_income()
        consume_fraction_initial /= env.params.time_period
        p, consume, real_spias_purchase, nominal_spias_purchase = env.spend(consume_fraction_initial, real_spias_fraction = 1)
        asset_allocation = AssetAllocation(stocks = 1)
        real_bonds_duration = nominal_bonds_duration = None

    else:

        session = U.make_session(num_cpu=1).__enter__()
        tf.saved_model.loader.load(session, [tf.saved_model.tag_constants.SERVING], model_dir)
        g = tf.get_default_graph()
        train_tf = g.get_tensor_by_name('pi/train:0')
        action_tf = g.get_tensor_by_name('pi/action:0')
        v_tf = g.get_tensor_by_name('pi/v:0')
        observation_tf = g.get_tensor_by_name('pi/ob:0')
        action, = session.run(action_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = env.decode_action(action)
        p, consume, real_spias_purchase, nominal_spias_purchase = env.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)

    logger.info()
    logger.info('Initial properties for first episode:')
    logger.info('    Consume: ', consume / env.params.time_period)
    logger.info('    Asset allocation: ', asset_allocation)
    logger.info('    Real immediate annuities purchase: ', real_spias_purchase / env.params.time_period if env.params.real_spias or annuitize else None)
    logger.info('    Nominal immediate annuities purchase: ', nominal_spias_purchase / env.params.time_period if env.params.nominal_spias else None)
    logger.info('    Real bonds duration: ', real_bonds_duration)
    logger.info('    Nominal bonds duration: ', nominal_bonds_duration)

    if not merton_or_samuelson_or_annuitize:

        v, = session.run(v_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
        sum_alive = sum(env.alive)
        logger.info('    Predicted certainty equivalent: ', env.utility.inverse(v / (sum_alive * env.params.time_period)))
            # Only valid if train and eval have identical age_start and life table.
            # Otherwise need to simulate to determine CE; this also provides percentile ranges.

    logger.info()

    evaluator = Evaluator(eval_env, eval_seed, eval_num_timesteps, eval_render)

    def pi(obs):

        if merton or samuelson:

            consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
            observation = env.decode_observation(obs)
            life_expectancy = observation['life_expectancy']
            t = ceil(life_expectancy / env.params.time_period) - 1
            if t == 0:
                consume_fraction = min(consume_fraction, 1 / env.params.time_period) # Bound may be exceeded in continuous time case.
            return env.encode_direct_action(consume_fraction, stocks_allocation, bills_allocation = 1 - stocks_allocation)

        elif annuitize:

            consume_fraction = consume_fraction_initial if env.episode_length == 0 else 1 / env.params.time_period
            return env.encode_direct_action(consume_fraction, 1, real_spias_fraction = 1)

        else:

            action, = session.run(action_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
            return action

    evaluator.evaluate(pi)

    env.close()

def main():
    parser = arg_parser()
    boolean_flag(parser, 'merton', default = False)
    boolean_flag(parser, 'samuelson', default = False)
    boolean_flag(parser, 'annuitize', default = False)
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False)
    logger.configure()
    run(eval_model_params, **args)

if __name__ == '__main__':
    main()
