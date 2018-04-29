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

from baselines import logger
from baselines.common import tf_util as U
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

def run(eval_model_params, *, eval_seed, eval_num_timesteps, eval_render):
    set_global_seeds(eval_seed)
    U.make_session(num_cpu=1).__enter__()
    eval_env = make_fin_env(**eval_model_params, direct_action = True)
    obs = eval_env.reset()
    env = eval_env.unwrapped
    consume_fraction, asset_allocation = pi_merton(env, obs)
    consume_annual = env.consume_rate(consume_fraction)
    print('Initial consume rate (Samuelson):', consume_annual)
    consume_fraction, asset_allocation = pi_merton(env, obs, continuous_time = True)
    consume_annual = env.consume_rate(consume_fraction)
    print('Initial consume rate (Merton):', consume_annual)
    print('Initial asset allocation:', asset_allocation)
    evaluator = Evaluator(eval_env, eval_seed, eval_num_timesteps, eval_render)
    def pi(obs):
        consume_fraction, asset_allocation = pi_merton(env.unwrapped, obs)
        return env.unwrapped.encode_direct_action(consume_fraction, asset_allocation)
    evaluator.evaluate(pi)
    env.close()

def main():
    parser = arg_parser()
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False)
    logger.configure()
    run(eval_model_params, **args)

if __name__ == '__main__':
    main()
