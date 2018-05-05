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

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator

def pi_merton(env, obs, continuous_time = False):
    observation = env.decode_observation(obs)
    life_expectancy = observation['life_expectancy']
    gamma = env.params.gamma
    mu = env.stocks.mu
    sigma = env.stocks.sigma
    r = env.risk_free.mu
    alpha = mu + sigma ** 2 / 2
    asset_allocation = (alpha - r) / (sigma ** 2 * gamma)
    nu = ((gamma - 1) / gamma) * ((alpha - r) * asset_allocation / 2 + r)
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
    return consume_fraction, asset_allocation

def run(eval_model_params, *, merton, samuelson, eval_seed, eval_num_timesteps, eval_render, model_dir):

    assert sum((model_dir != 'aiplanner.tf', merton, samuelson)) <= 1
    merton_or_samuelson = merton or samuelson

    set_global_seeds(eval_seed)
    eval_env = make_fin_env(**eval_model_params, action_space_unbounded = not merton_or_samuelson, direct_action = merton_or_samuelson)
    env = eval_env.unwrapped
    obs = eval_env.reset()

    logger.info('Properties for first episode:')

    if merton_or_samuelson:

        consume_fraction, asset_allocation = pi_merton(env, obs, continuous_time = merton)
        consume_annual = env.consume_rate(consume_fraction)

    else:

        session = U.make_session(num_cpu=1).__enter__()
        tf.saved_model.loader.load(session, [tf.saved_model.tag_constants.SERVING], model_dir)
        g = tf.get_default_graph()
        train_tf = g.get_tensor_by_name('pi/train:0')
        action_tf = g.get_tensor_by_name('pi/action:0')
        v_tf = g.get_tensor_by_name('pi/v:0')
        observation_tf = g.get_tensor_by_name('pi/ob:0')
        action, = session.run(action_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
        consume_fraction, asset_allocation = env.decode_action(action)
        consume_annual = env.consume_rate(consume_fraction)

    logger.info('    Initial consume rate: ', consume_annual)
    logger.info('    Initial asset allocation: ', asset_allocation)

    if not merton_or_samuelson:

        v, = session.run(v_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
        observation = env.decode_observation(obs)
        life_expectancy = observation['life_expectancy']
        logger.info('    Predicted certainty equivalent: ', env.utility.inverse(v / life_expectancy))

    evaluator = Evaluator(eval_env, eval_seed, eval_num_timesteps, eval_render)

    def pi(obs):

        if merton or samuelson:

            consume_fraction, asset_allocation = pi_merton(env, obs, continuous_time = merton)
            observation = env.decode_observation(obs)
            life_expectancy = observation['life_expectancy']
            t = ceil(life_expectancy / env.params.time_period) - 1
            if t == 0:
                consume_fraction = min(consume_fraction, 1 / env.params.time_period) # Bound may be exceeded in continuous time case.
            return env.encode_direct_action(consume_fraction, asset_allocation)

        else:

            action, = session.run(action_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
            return action

    evaluator.evaluate(pi)

    env.close()

def main():
    parser = arg_parser()
    boolean_flag(parser, 'merton', default = False)
    boolean_flag(parser, 'samuelson', default = False)
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False)
    logger.configure()
    run(eval_model_params, **args)

if __name__ == '__main__':
    main()
