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

# Code based on baselines/common/cmd_util.py

"""
Helpers for scripts like train_ppo1.py.
"""

import os

from baselines import logger
from baselines.bench import Monitor
from baselines.common import boolean_flag, set_global_seeds

from gym_fin.envs import FinEnv, ModelParams

def make_fin_env(*, action_space_unbounded, training, **kwargs):
    """
    Create a wrapped, monitored gym.Env for Fin.
    """
    env = FinEnv(action_space_unbounded=action_space_unbounded, **kwargs)
    filename = logger.get_dir()
    if filename:
        filename = os.path.join(filename, '' if training else 'gym_eval')
    env = Monitor(env, filename, allow_early_resets=not training, info_keywords = ('certainty_equivalent', ))
    return env

def arg_parser():
    """
    Create an empty argparse.ArgumentParser.
    """
    import argparse
    return argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

def fin_arg_parse(parser):
    """
    Create an argparse.ArgumentParser for run_fin.py.
    """
    parser.add_argument('--seed', help='RNG seed', type=int, default=0)
    parser.add_argument('--num-timesteps', type=int, default=int(1e6))
    boolean_flag(parser, 'evaluation', default=False)
    parser.add_argument('--nb-eval-steps', type=int, default=100)  # per epoch cycle
    boolean_flag(parser, 'render-eval', default=False)
    model_params = ModelParams()
    model_params.add_arguments(parser, training = True)
    model_params.add_arguments(parser, training = False)
    args = parser.parse_args()
    dict_args = vars(args)
    model_params.set_params(dict_args)
    training_model_params = model_params.get_params(training = True)
    for param in training_model_params:
        del dict_args['model_' + param]
    eval_model_params = model_params.get_params(training = False)
    for param in eval_model_params:
        del dict_args['eval_model_' + param]
    return training_model_params, eval_model_params, dict_args
