# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
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

import argparse
import os

from baselines.common import boolean_flag, set_global_seeds

from ai.gym_fin import FinEnv, ModelParams
from ai.gym_fin.model_params import dump_params

def make_fin_env(training = False, allow_early_resets = None, **kwargs):
    env = FinEnv(**kwargs)
    return env

def _config_parser():

    config_parser = argparse.ArgumentParser(add_help = False)
    config_parser.add_argument('-c', '--config-file', action = 'append', default = [])

    return config_parser

def arg_parser(training = True, evaluate = True):

    parser = argparse.ArgumentParser(formatter_class = argparse.ArgumentDefaultsHelpFormatter, parents = [_config_parser()])

    if training:
        parser.add_argument('--train-num-timesteps', type = int, default = int(50e6))
        parser.add_argument('--train-single-num-timesteps', type = int, default = int(1e9))
        parser.add_argument('--train-couple-num-timesteps', type = int, default = int(1e9))
    if evaluate and training:
        boolean_flag(parser, 'evaluation', default = False)
        parser.add_argument('--eval-frequency', type = int, default = 20000) # During training with evaluation on evaluate every this many env steps.
            # Should also set eval_num_timesteps to around 2000 for acceptable performance.
    if evaluate:
        parser.add_argument('--eval-seed', type = int, default = 0)
        parser.add_argument('--eval-num-timesteps', type = int, default = 2000000) # Per evaluation.
            # Above value is good for computing the true policy certainty equivalence to within perhaps 0.1-0.2%.
            # A lower value such as 10000 may be more appropriate when performing inter-run comparisons, as the evaluation episodes are identical for each run.
        boolean_flag(parser, 'eval-render', default = False)
    parser.add_argument('--nice', type = int, default = 0)
    parser.add_argument('--num-cpu', type = int, default = 1)
        # Change default to None to use system selected value.
        # Using a value of 1 appears to give slightly faster run times, significiantly higher throughput, and possibly even determinism.

    parser.add_argument('--model-dir', default = 'aiplanner.tf')
    parser.add_argument('--train-seed', type = int, default = 0)

    model_params = ModelParams()
    model_params.add_arguments(parser, training = training, evaluate = evaluate)

    return parser

def parse_args(parser, *, training = True, evaluate = True, args = None):

    arguments = parser.parse_args(args = args)

    config = {}
    for config_file in arguments.config_file:
        with open(config_file) as f:
            config_str = f.read()
        exec(config_str, {'inf': float('inf')}, config)

    # Hack to ensure config files dosn't contain any misspelled parameters.
    defaults = {}
    for action in parser._actions:
        if action.dest in config:
            defaults[action.dest] = config[action.dest]
            del config[action.dest]
    config = {param: value for param, value in config.items()
        if (training if param.startswith('train_') else (evaluate if param.startswith('eval_') else True))}
    if config:
        parser.error('Unrecognised configuration file parameters: ' + ','.join(config.keys()))
    parser.set_defaults(**defaults)

    arguments = parser.parse_args(args = args)

    return arguments

def fin_arg_parse(parser, *, training = True, evaluate = True, dump = True, args = None):

    model_params = ModelParams()
    model_params.add_arguments(None, training = training, evaluate = evaluate)

    arguments = parse_args(parser, training = training, evaluate = evaluate, args = args)
    dict_args = vars(arguments)
    model_params.set_params(dict_args)
    if dump:
        dump_params(dict_args)
    training_model_params = model_params.get_params(training = True) if training else {}
    eval_model_params = model_params.get_params(training = False) if evaluate else {}
    dict_args = model_params.remaining_params()
    return training_model_params, eval_model_params, dict_args
