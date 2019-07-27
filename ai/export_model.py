#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from gym_fin.envs.model_params import load_params_file
from gym_fin.common.cmd_util import arg_parser, fin_arg_parse
from gym_fin.common.tf_util import TFRunner

def export_models(*, redis_address, checkpoint_name, train_seeds, nice, train_seed, model_dir, **kwargs):

    while model_dir and model_dir[-1] == '/':
        model_dir = model_dir[:-1]
    assert model_dir.endswith('.tf')

    for i in range(train_seed, train_seed + train_seeds):

        train_dir_seed = train_seed + i
        train_dirs = [model_dir + '/seed_' + str(train_dir_seed)]

        train_model_params = load_params_file(model_dir + '/params.txt')

        TFRunner(train_dirs = train_dirs, checkpoint_name = checkpoint_name, eval_model_params = train_model_params,
            redis_address = redis_address, evaluator = False, export_model = True)

def main():
    parser = arg_parser(training = True, evaluate = False)
    parser.add_argument('--redis-address')
    parser.add_argument('--train-seeds', type = int, default = 1) # Number of seeds to export.
    parser.add_argument('--checkpoint-name')
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = True, evaluate = False, dump = False)
    export_models(**args)

if __name__ == '__main__':
    main()
