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
from os import scandir
from sys import stdout

#from baselines.common.misc_util import set_global_seeds

from ai.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from ai.common.tf_util import TFRunner
from ai.common.utils import boolean_flag
from ai.gym_fin.asset_allocation import AssetAllocation
from ai.gym_fin.model_params import load_params_file
from ai.gym_fin.policies import policy

def extract_model(eval_model_params, *, train_seed, redis_address, train_seeds, ensemble, checkpoint_name, result_dir,
    eval_couple_net, eval_seed, eval_num_timesteps, eval_render, nice, num_cpu, model_dir,
    num_age_steps, num_p_steps, age_range, p_range, p_type):

    def extract_timestep(train_dirs, checkpoint_name, output_fname):

        with TFRunner(train_dirs = train_dirs, checkpoint_name = checkpoint_name, eval_model_params = eval_model_params,
                      couple_net = eval_couple_net, redis_address = redis_address, num_workers = 0, num_cpu = num_cpu) as runner:
            with open(output_fname, 'w') as f:
                c = writer(f)
                for age_index in range(num_age_steps + 1):
                    for p_index in range(num_p_steps + 1):
                        age = age_range[0]
                        if num_age_steps > 0:
                            age += age_index * (age_range[1] - age_range[0]) / num_age_steps
                        p = p_range[0]
                        if num_p_steps > 0:
                            p += p_index * (p_range[1] - p_range[0]) / num_p_steps
                        p_tax_free = p if p_type == 'tax_free' else None
                        p_tax_deferred = p if p_type == 'tax_deferred' else None
                        if p_type.startswith('taxable_'):
                            assets = {}
                            if env.params.stocks:
                                assert env.params.p_taxable_stocks_low == env.params.p_taxable_stocks_high
                                assets['stocks'] = p if p_type == 'taxable_stocks' else env.params.p_taxable_stocks_low
                            if env.params.real_bonds:
                                assert env.params.p_taxable_real_bonds_low == env.params.p_taxable_real_bonds_high
                                assets['real_bonds'] = p if p_type == 'taxable_real_bonds' else env.params.p_taxable_real_bonds_low
                            if env.params.nominal_bonds:
                                assert env.params.p_taxable_nominal_bonds_low == env.params.p_taxable_nominal_bonds_high
                                assets['nominal_bonds'] = p if p_type == 'taxable_nominal_bonds' else env.params.p_taxable_nominal_bonds_low
                            if env.params.iid_bonds:
                                assert env.params.p_taxable_iid_bonds_low == env.params.p_taxable_iid_bonds_high
                                assets['iid_bonds'] = p if p_type == 'taxable_iid_bonds' else env.params.p_taxable_iid_bonds_low
                            if env.params.bills:
                                assert env.params.p_taxable_bills_low == env.params.p_taxable_bills_high
                                assets['bills'] = p if p_type == 'taxable_bills' else env.params.p_taxable_bills_low
                            p_taxable_assets = AssetAllocation(fractional = False, **assets)
                            assert env.params.p_taxable_stocks_basis_fraction_low == env.params.p_taxable_stocks_basis_fraction_high
                            p_taxable_stocks_basis_fraction = env.params.p_taxable_stocks_basis_fraction_low
                        else:
                            p_taxable_assets = None
                            p_taxable_stocks_basis_fraction = None
                        obs = env.goto(age = age, p_tax_free = p_tax_free, p_tax_deferred = p_tax_deferred, p_taxable_assets = p_taxable_assets,
                            p_taxable_stocks_basis_fraction = p_taxable_stocks_basis_fraction, force_family_unit = True, forced_family_unit_couple = bool(env.sex2))
                        action, = runner.run([obs])
                        act = env.interpret_action(action)
                        c.writerow((age, p, act['consume'], act['retirement_contribution'], act['real_spias_purchase'], act['nominal_spias_purchase'],
                            act['real_bonds_duration'], act['nominal_bonds_duration'], *act['asset_allocation'].as_list()))
                    c.writerow(())

    #set_global_seeds(0) # Seed shouldn't matter, but just to be ultra-deterministic.

    assert ensemble == (train_seeds > 1)

    train_model_params = load_params_file(model_dir + '/params.txt')
    eval_model_params['action_space_unbounded'] = train_model_params['action_space_unbounded']
    eval_model_params['observation_space_ignores_range'] = train_model_params['observation_space_ignores_range']
    eval_model_params['display_returns'] = False
    env = make_fin_env(**eval_model_params)
    env = env.unwrapped
    env.reset()

    train_dirs = [model_dir + '/seed_' + str(train_seed + i) for i in range(train_seeds)]
    if result_dir == None:
        result_dir = model_dir
    if checkpoint_name:
        checkpoint_names = [checkpoint_name]
    else:
        checkpoints = glob(train_dirs[0] + '/*/checkpoint_*')
        checkpoint_names = [checkpoint.split('/')[-1] for checkpoint in checkpoints]

    for checkpoint in checkpoint_names:
        extract_timestep(train_dirs, checkpoint, result_dir + '/aiplanner-linear-' + checkpoint + '.csv')

def main():
    parser = arg_parser(training = False, evaluate = True)
    parser.add_argument('--redis-address')
    parser.add_argument('--train-seeds', type = int, default = 1) # Number of seeds to evaluate for an ensemble.
    boolean_flag(parser, 'ensemble', default = False)
    parser.add_argument('--checkpoint-name')
    parser.add_argument('--result-dir')
    boolean_flag(parser, 'eval-couple-net', default = True)
    parser.add_argument('--num-age-steps', type = int, default = 30)
    parser.add_argument('--num-p-steps', type = int, default = 30)
    parser.add_argument('--age-range', type = float, nargs = 2, default = (20, 100))
    parser.add_argument('--p-range', type = float, nargs = 2, default = (0, 1e7))
    parser.add_argument('--p-type', default = 'tax_free',
        choices = ('tax_free', 'tax_deferred', 'taxable_stocks', 'taxable_real_bonds', 'taxable_nominal_bonds', 'taxable_iid_bonds', 'taxable_bills'))
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False, evaluate = True)
    extract_model(eval_model_params, **args)

if __name__ == '__main__':
    main()
