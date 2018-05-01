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

def make_fin_env(action_space_unbounded = False, training = False, **kwargs):
    """
    Create a wrapped, monitored gym.Env for Fin.
    """
    env = FinEnv(action_space_unbounded = action_space_unbounded, **kwargs)
    filename = logger.get_dir()
    if filename:
        filename = os.path.join(filename, '' if training else 'gym_eval')
    env = Monitor(env, filename, allow_early_resets=not training, info_keywords = ('ce', ))
    return env

def arg_parser():
    """
    Create an empty argparse.ArgumentParser.
    """
    import argparse
    return argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

def fin_arg_parse(parser, training = True, evaluate = True):
    """
    Create an argparse.ArgumentParser for run_fin.py.
    """
    if training:
        parser.add_argument('--seed', help = 'RNG seed', type = int, default = 0)
        parser.add_argument('--num-timesteps', type = int, default = int(1e6))
    if evaluate and training:
        boolean_flag(parser, 'evaluation', default = False)
        parser.add_argument('--eval-frequency', type = int, default = 20000) # During training with evaluation on evaluate every this many env steps.
            # Should also set eval_num_timesteps to around 2000 for acceptable performance.
    if evaluate:
        parser.add_argument('--eval-seed', help = 'evaluation RNG seed', type = int, default = 0)
        parser.add_argument('--eval-num-timesteps', type = int, default = 1000000) # Per evaluation.
            # Above value is good for computing the true policy certainty equivalence to within perhaps 0.1%.
            # A lower value such as 10000 may be more appropriate when performing inter-run comparisons, since the evaluation episodes are identical for each run.
        boolean_flag(parser, 'eval-render', default = False)
    parser.add_argument('--model-dir', default = 'aiplanner.tf')
    model_params = ModelParams()
    model_params.add_arguments(parser, training = training, evaluate = evaluate)
    args = parser.parse_args()
    dict_args = vars(args)
    model_params.set_params(dict_args)
    training_model_params = model_params.get_params(training = True) if training else {}
    eval_model_params = model_params.get_params(training = False) if evaluate else {}
    dict_args = model_params.remaining_params()
    return training_model_params, eval_model_params, dict_args
