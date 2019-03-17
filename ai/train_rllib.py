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

from os import getpriority, mkdir, PRIO_PROCESS, setpriority
from os.path import abspath
from shutil import rmtree

from baselines.common import boolean_flag
#from baselines.common.misc_util import set_global_seeds

import ray
from ray.tune import run_experiments, function
from ray.tune.config_parser import make_parser

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse
from gym_fin.envs.model_params import dump_params_file
from gym_fin.envs.fin_env import FinEnv

class RayFinEnv(FinEnv):

    def __init__(self, config):
        super().__init__(**config)

def train(training_model_params, *, train_couple_net,
          train_timesteps_per_epoch,
          train_num_timesteps, train_single_num_timesteps, train_couple_num_timesteps, train_seed,
          nice, num_cpu, model_dir, **dummy_kwargs):

    priority = getpriority(PRIO_PROCESS, 0)
    priority += nice
    setpriority(PRIO_PROCESS, 0, priority)

    while model_dir and model_dir[-1] == '/':
        model_dir = model_dir[:-1]
    assert model_dir.endswith('.tf')
    try:
        rmtree(model_dir)
    except FileNotFoundError:
        pass

    #set_global_seeds(train_seed)
        # Training is currently non-deterministic.
        # Would probably need to call rllib.utils.seed.seed() from rllib.agents.agent.__init__() with a triply repeated config["seed"] parameter to fix.

    training_model_params['action_space_unbounded'] = True
    training_model_params['observation_space_ignores_range'] = True

    mkdir(model_dir)
    dump_params_file(model_dir + '/params.txt', training_model_params)

    couple = training_model_params['sex2'] != None
    couple_net = couple and train_couple_net

    ray.init(num_gpus=1)
    #ray.init(object_store_memory=int(2e9))

    algorithm = training_model_params['algorithm']

    agent_config = {

        'A2C': {
        },

        'A3C': {
        },

        'PG': {
        },

        'DDPG': {
        },

        'APPO': {
        },

        'PPO': {
            'lambda': 0.95, # Increasing lambda results in an increased stocks allocation.
            'num_sgd_iter': 5, # If alter, might want to inversely alter learning rate.
            'lr_schedule': (
                (0, 1e-4),
                (train_num_timesteps, 0)
            ),
            #'clip_param': 0.2,
            'vf_clip_param': float('inf'),
            'batch_mode': 'complete_episodes', # Observe poor CE if set to 'truncate_episodes'.
        },

        'PPO.baselines': {

            'model': {
                'fcnet_hiddens': (64, 64),
            },

            'lambda': 0.95,
            'sample_batch_size': 256,
            'train_batch_size': train_timesteps_per_epoch,
            #'sgd_minibatch_size': 128,
            'num_sgd_iter': 10,
            'lr_schedule': (
                (0, 3e-4),
                (train_num_timesteps, 0)
            ),
            'clip_param': 0.2,
            'vf_clip_param': float('inf'),
            'batch_mode': 'complete_episodes',
            #'observation_filter': 'NoFilter',
        },

    }[algorithm]

    run = algorithm[:-len('.baselines')] if algorithm.endswith('.baselines') else algorithm

    model_seed_dir = model_dir + '/seed_' + str(train_seed)
    mkdir(model_seed_dir)

    run_experiments({
        'rllib': {

            'run': run,

            'config': dict({
                'env': RayFinEnv,
                'env_config': training_model_params,
                'clip_actions': False,
                'gamma': 1,

                #'num_gpus': 0,
                #'num_cpus_for_driver': 1,
                'num_workers': 1 if algorithm in ('A3C', 'APPO') else 0,
                #'num_envs_per_worker': 1,
                #'num_cpus_per_worker': 1,
                #'num_gpus_per_worker': 0,

                'local_evaluator_tf_session_args': {
                    'intra_op_parallelism_threads': num_cpu,
                    'inter_op_parallelism_threads': num_cpu,
                }
            }, **agent_config),

            'stop': {
                'timesteps_total': train_num_timesteps,
            },

            'local_dir': abspath(model_seed_dir),
            'checkpoint_at_end': True,
        },
    })

def main():
    parser = make_parser(arg_parser)
    boolean_flag(parser, 'train-couple-net', default=True)
    parser.add_argument('--train-timesteps-per-epoch', type=int, default=4096)
    training_model_params, _, args = fin_arg_parse(parser, evaluate=False)
    if not training_model_params['algorithm']:
         training_model_params['algorithm'] = 'PPO'
    train(training_model_params, **args)

if __name__ == '__main__':
    main()
