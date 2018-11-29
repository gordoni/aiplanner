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

from csv import writer
from sys import stdout

from baselines.common import boolean_flag
from baselines.common.misc_util import set_global_seeds

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.model_params import load_params_file
from gym_fin.envs.policies import policy
from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator
from gym_fin.common.tf_util import TFRunner

def extract_model(eval_model_params, *, eval_couple_net, eval_seed, eval_num_timesteps, eval_render, nice, num_cpu, model_dir,
                  output_file, num_grid_steps, age_range, p_range, p_type):

    set_global_seeds(0) # Seed shouldn't matter, but just to be ultra-deterministic.

    assets_dir = model_dir + '/assets.extra'
    train_model_params = load_params_file(assets_dir + '/params.txt')
    eval_model_params['action_space_unbounded'] = train_model_params['action_space_unbounded']
    eval_model_params['observation_space_ignores_range'] = train_model_params['observation_space_ignores_range']
    eval_model_params['display_returns'] = False
    # Ensure episode_length is never negative.
    offset = age_range[0] - eval_model_params['age_start_low']
    eval_model_params['age_start_low'] += offset
    eval_model_params['age_start_high'] += offset
    eval_model_params['age_start2_low'] += offset
    eval_model_params['age_start2_high'] += offset
    env = make_fin_env(**eval_model_params)
    env = env.unwrapped

    runner = TFRunner(model_dir = model_dir, couple_net = eval_couple_net, num_cpu = num_cpu)

    c = writer(output_file)
    for age_index in range(num_grid_steps + 1):
        for p_index in range(num_grid_steps + 1):
            age = age_range[0] + age_index * (age_range[1] - age_range[0]) / num_grid_steps
            p = p_range[0] + p_index * (p_range[1] - p_range[0]) / num_grid_steps
            p_tax_free = p if p_type == 'tax_free' else None
            p_tax_deferred = p if p_type == 'tax_deferred' else None
            p_taxable = p if p_type == 'taxable' else None
            obs = env.goto(age = age, p_tax_free = p_tax_free, p_tax_deferred = p_tax_deferred, p_taxable = p_taxable)
            action, = runner.run([obs])
            act = env.interpret_action(action)
            c.writerow((age, p, act['consume'], act['retirement_contribution'], act['real_spias_purchase'], act['nominal_spias_purchase'],
                act['real_bonds_duration'], act['nominal_bonds_duration'], *act['asset_allocation'].as_list()))
        c.writerow(())

def main():
    parser = arg_parser()
    boolean_flag(parser, 'eval-couple-net', default = True)
    parser.add_argument('-o', '--output-file', type = lambda f: open(f, 'w'), default = stdout)
    parser.add_argument('--num-grid-steps', type = int, default = 30)
    parser.add_argument('--age-range', type = float, nargs = 2, default = (20, 100))
    parser.add_argument('--p-range', type = float, nargs = 2, default = (0, int(1e6)))
    parser.add_argument('--p-type', default = 'taxable', choices = ('tax_free', 'tax_deferred', 'taxable'))
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False, evaluate = True)
    extract_model(eval_model_params, **args)

if __name__ == '__main__':
    main()
