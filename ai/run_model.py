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

from math import exp

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
    gamma = env.params.gamma
    mu = env.stocks.mu
    sigma = env.stocks.sigma
    r = env.risk_free.mu
    alpha = mu + sigma ** 2 / 2
    asset_allocation = (alpha - r) / (sigma ** 2 * gamma)
    nu = ((gamma - 1) / gamma) * ((alpha - r) * asset_allocation / 2 + r)
    if nu == 0:
        consume_fraction = 1 / observation['life_expectancy']
    elif continuous_time:
        # Merton.
        consume_fraction = nu / (1 - exp(- nu * observation['life_expectancy']))
    else:
        # Samuelson.
        a = exp(nu * env.params.time_period)
        t = max(observation['life_expectancy'] / env.params.time_period - 1, 0)
        consume_fraction = a ** t * (a - 1) / (a ** (t + 1) - 1) / env.params.time_period
    return consume_fraction, asset_allocation

def run(eval_model_params, *, merton, eval_seed, eval_num_timesteps, eval_render, model_dir):

    assert not (model_dir != 'aiplanner.tf' and merton)

    set_global_seeds(eval_seed)
    eval_env = make_fin_env(**eval_model_params, action_space_unbounded = not merton, direct_action = merton)
    env = eval_env.unwrapped
    obs = eval_env.reset()

    if merton:

        consume_fraction, asset_allocation = pi_merton(env, obs)
        consume_annual = env.consume_rate(consume_fraction)
        print('Initial consume rate (Samuelson):', consume_annual)
        consume_fraction, asset_allocation = pi_merton(env, obs, continuous_time = True)
        consume_annual = env.consume_rate(consume_fraction)
        print('Initial consume rate (Merton):', consume_annual)
        print('Initial asset allocation:', asset_allocation)

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
        print('Initial consume rate:', consume_annual)
        print('Initial asset allocation:', asset_allocation)
        v, = session.run(v_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
        observation = env.decode_observation(obs)
        life_expectancy = observation['life_expectancy']
        print('Prediction certainty equivalent:', env.utility.inverse(v / life_expectancy))

    evaluator = Evaluator(eval_env, eval_seed, eval_num_timesteps, eval_render)

    def pi(obs):

        if merton:

            consume_fraction, asset_allocation = pi_merton(env, obs)
            return env.unwrapped.encode_direct_action(consume_fraction, asset_allocation)

        else:

            action, = session.run(action_tf, feed_dict = {train_tf: np.array(False), observation_tf: [obs]})
            return action

    evaluator.evaluate(pi)

    env.close()

def main():
    parser = arg_parser()
    boolean_flag(parser, 'merton', default = False)
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False)
    logger.configure()
    run(eval_model_params, **args)

if __name__ == '__main__':
    main()
