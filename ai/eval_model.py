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

from math import ceil, exp, sqrt

import tensorflow as tf

from baselines import logger
from baselines.common import (
    tf_util as U,
    boolean_flag,
)
from baselines.common.misc_util import set_global_seeds

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.policies import policy
from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator

def pi_merton(env, obs, continuous_time = False):
    observation = env.decode_observation(obs)
    assert observation['life_expectancy_both'] == 0
    life_expectancy = observation['life_expectancy_one']
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

def run(eval_model_params, *, merton, samuelson, annuitize, eval_seed, eval_num_timesteps, eval_render, model_dir, search_consume_initial_around):

    assert sum((model_dir != 'aiplanner.tf', merton, samuelson, annuitize)) <= 1
    model = not (merton or samuelson or annuitize)

    eval_seed += 1000000 # Use a different seed than might have been used during training.
    set_global_seeds(eval_seed)
    eval_env = make_fin_env(**eval_model_params, action_space_unbounded = model, direct_action = not model)
    env = eval_env.unwrapped

    if env.params.consume_policy != 'rl' and env.params.annuitization_policy != 'rl' and env.params.asset_allocation_policy != 'rl' and \
        (not env.params.real_bonds or env.params.real_bonds_duration != None) and \
        (not env.params.nominal_bonds or env.params.nominal_bonds_duration != None):
        model = False

    obs = eval_env.reset()

    if merton or samuelson:

        consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
        p, consume, real_spias_purchase, nominal_spias_purchase = env.spend(consume_fraction)
        asset_allocation = AssetAllocation(stocks = stocks_allocation, bills = 1 - stocks_allocation)
        real_bonds_duration = nominal_bonds_duration = None

    elif annuitize:

        consume_initial = env.gi_sum() + env.p_notax / (env.params.time_period + env.real_spia.premium(1, mwr = env.params.real_spias_mwr))
        consume_fraction_initial = consume_initial / env.p_plus_income()
        p, consume, real_spias_purchase, nominal_spias_purchase = env.spend(consume_fraction_initial, real_spias_fraction = 1)
        asset_allocation = AssetAllocation(stocks = 1)
        real_bonds_duration = nominal_bonds_duration = None

    else:

        if model:
            session = U.make_session(num_cpu=1).__enter__()
            tf.saved_model.loader.load(session, [tf.saved_model.tag_constants.SERVING], model_dir)
            g = tf.get_default_graph()
            action_tf = g.get_tensor_by_name('pi/action:0')
            v_tf = g.get_tensor_by_name('pi/v:0')
            observation_tf = g.get_tensor_by_name('pi/ob:0')
            action, = session.run(action_tf, feed_dict = {observation_tf: [obs]})
            decoded_action = env.decode_action(action)
        else:
            decoded_action = None
        policified_action = policy(env, decoded_action)
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = policified_action
        p, consume, real_spias_purchase, nominal_spias_purchase = env.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)

    logger.info()
    logger.info('Initial properties for first episode:')
    logger.info('    Consume: ', consume / env.params.time_period)
    logger.info('    Asset allocation: ', asset_allocation)
    logger.info('    Real immediate annuities purchase: ', real_spias_purchase if env.params.real_spias or annuitize else None)
    logger.info('    Nominal immediate annuities purchase: ', nominal_spias_purchase if env.params.nominal_spias else None)
    logger.info('    Real bonds duration: ', real_bonds_duration)
    logger.info('    Nominal bonds duration: ', nominal_bonds_duration)

    if model:

        v, = session.run(v_tf, feed_dict = {observation_tf: [obs]})
        logger.info('    Predicted certainty equivalent: ', env.utility.inverse(v / env.alive_years))
            # Only valid if train and eval have identical age_start and life table.
            # Otherwise need to simulate to determine CE; this also provides percentile ranges.

    logger.info()

    evaluator = Evaluator(eval_env, eval_seed, eval_num_timesteps, eval_render)

    def pi(obs):

        if model:

            action, = session.run(action_tf, feed_dict = {observation_tf: [obs]})
            return action

        elif merton or samuelson:

            consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
            observation = env.decode_observation(obs)
            assert observation['life_expectancy_both'] == 0
            life_expectancy = observation['life_expectancy_one']
            t = ceil(life_expectancy / env.params.time_period) - 1
            if t == 0:
                consume_fraction = min(consume_fraction, 1 / env.params.time_period) # Bound may be exceeded in continuous time case.
            return env.encode_direct_action(consume_fraction, stocks = stocks_allocation, bills = 1 - stocks_allocation)

        elif annuitize:

            consume_fraction = consume_fraction_initial if env.episode_length == 0 else 1 / env.params.time_period
            return env.encode_direct_action(consume_fraction, stocks = 1, real_spias_fraction = 1)

        else:

            return None

    if search_consume_initial_around == None:

        evaluator.evaluate(pi)

    else:

        f_cache = {}

        def f(x):

            try:

                return f_cache[x]

            except KeyError:

                logger.info('    Consume: ', x)
                env.params.consume_initial = x
                results = evaluator.evaluate(pi)
                f_cache[x] = results
                return results

        x, f_x = gss(f, search_consume_initial_around / 2, search_consume_initial_around * 2)
        f_cache = {}
        f(x)

    env.close()

def gss(f, a, b):
    '''Golden segment search for maximum of f on [a, b].'''

    f_a, tol_a = f(a)
    f_b, tol_b = f(b)
    tol = (tol_a + tol_b) / 2
    g = (1 + sqrt(5)) / 2
    while (b - a) > tol:
        c = b - (b - a) / g
        d = a + (b - a) / g
        f_c, tol_c = f(c)
        f_d, tol_d = f(d)
        if f_c >= f_d:
            b = d
            f_b = f_d
        else:
            a = c
            f_a = f_c
        tol = (tol_c + tol_d) / 2
    if f_a > f_b:
        found = a
        f_found = f_a
    else:
        found = b
        f_found = f_b

    return found, f_found

def main():
    parser = arg_parser()
    boolean_flag(parser, 'merton', default = False)
    boolean_flag(parser, 'samuelson', default = False)
    boolean_flag(parser, 'annuitize', default = False)
    parser.add_argument('--search-consume-initial-around', type = float)
        # Search for the initial consumption that maximizes the certainty equivalent using the supplied value as a hint as to where to search.
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False)
    logger.configure()
    run(eval_model_params, **args)

if __name__ == '__main__':
    main()
