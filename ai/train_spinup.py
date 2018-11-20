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

from math import ceil
from os import getpriority, mkdir, PRIO_PROCESS, setpriority
from shutil import rmtree

import numpy as np

import tensorflow as tf

from baselines.common import boolean_flag
from baselines.common.misc_util import set_global_seeds

from gym import Env
from gym.spaces import Box

from spinup import ddpg, ppo, sac, td3, trpo, vpg
from spinup.algos.ddpg.core import mlp_actor_critic as ddpg_ac
from spinup.algos.ppo.core import mlp_actor_critic as ppo_ac
from spinup.algos.sac.core import mlp_actor_critic as sac_ac
from spinup.algos.td3.core import mlp_actor_critic as td3_ac
from spinup.algos.trpo.core import mlp_actor_critic as trpo_ac
from spinup.algos.vpg.core import mlp_actor_critic as vpg_ac

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.envs.model_params import dump_params_file

class DummyEnv(Env):

    def __init__(self, action_space, observation_space):
        self.action_space = action_space
        self.observation_space = observation_space

    def seed(self, seed=None):
        return

    def reset(self):
        return self._observe()

    def step(self, action):
        return self._observe(), 0, True, None

    def _observe(self):
        return np.zeros(self.observation_space.shape)

def couple_actor_critic(actor_critic):
    def couple_single(x, a, **kwargs):
        # Spinning Up determines the variables to optimize over using calls like get_vars('main/pi') which uses:
        #
        #     def get_vars(scope):
        #         return [x for x in tf.global_variables() if scope in x.name]
        #
        # Hence when we are in scope 'main' if we give our variables names like 'main/single/main/pi/<name>', they are found by get_vars('main/pi').
        scope = tf.get_default_graph().get_name_scope()
        with tf.variable_scope('single/' + scope):
            single = actor_critic(x, a, **kwargs)
        with tf.variable_scope('couple/' + scope):
            couple = actor_critic(x, a, **kwargs)
        is_couple = tf.cast(x[:, 0], tf.bool)
        return tuple(tf.where(is_couple, c, s) for c, s in zip(single, couple))
    return couple_single

def train(training_model_params, *, train_algorithm, train_num_hidden_layers, train_hidden_layer_size, train_couple_net,
          train_timesteps_per_epoch, train_epochs_per_model_save,
          train_num_timesteps, train_single_num_timesteps, train_couple_num_timesteps, train_seed,
          nice, num_cpu, model_dir):

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

    set_global_seeds(train_seed)

    action_space_unbounded = train_algorithm in ('ppo', 'trpo', 'vpg')
    assert action_space_unbounded or (train_algorithm in ('ddpg', 'sac', 'td3'))
    training_model_params['action_space_unbounded'] = action_space_unbounded
    training_model_params['observation_space_ignores_range'] = True

    mkdir(model_dir)
    assets_dir = model_dir + '/assets.extra'
    mkdir(assets_dir)
    dump_params_file(assets_dir + '/params.txt', training_model_params)

    allow_early_resets = train_algorithm in ('ppo', 'trpo', 'vpg')
    env = make_fin_env(training=True, allow_early_resets=allow_early_resets, **training_model_params)

    global invocation
    invocation = 0
    def env_fn():
        global invocation
        assert invocation < 2
        training = invocation == 0
        if training:
            res_env = env
        else:
            res_env = DummyEnv(env.action_space, env.observation_space)
        invocation += 1
        return res_env

    couple = training_model_params['sex2'] != None
    couple_net = couple and train_couple_net
    std_actor_critic = {
        'ddpg': ddpg_ac,
        'ppo': ppo_ac,
        'sac': sac_ac,
        'td3': td3_ac,
        'trpo': trpo_ac,
        'vpg': vpg_ac,
    }[train_algorithm]
    actor_critic = couple_actor_critic(std_actor_critic) if couple_net else std_actor_critic

    ac_kwargs = {}
    if train_hidden_layer_size:
        ac_kwargs['hidden_sizes'] = [train_hidden_layer_size] * train_num_hidden_layers

    epochs = ceil(train_num_timesteps / train_timesteps_per_epoch)

    save_freq = epochs if train_epochs_per_model_save == None else train_epochs_per_model_save

    common_args = {
        'actor_critic': actor_critic,
        'ac_kwargs': ac_kwargs,
        'steps_per_epoch': train_timesteps_per_epoch,
        'epochs': epochs + 1, # Results from final epoch don't get saved.
        'seed': train_seed,
        'gamma': 1,
        'logger_kwargs': {'output_dir': model_dir},
        'save_freq': save_freq,
        'num_cpu': num_cpu,
    }

    if train_algorithm == 'ddpg':
        ddpg(env_fn, **common_args)
    elif train_algorithm == 'ppo':
        ppo(env_fn, **common_args)
    elif train_algorithm == 'sac':
        sac(env_fn, **common_args)
    elif train_algorithm == 'td3':
        td3(env_fn, **common_args)
    elif train_algorithm == 'trpo':
        trpo(env_fn, **common_args)
    elif train_algorithm == 'vpg':
        vpg(env_fn, **common_args)
    else:
        assert False

def main():
    parser = arg_parser()
    parser.add_argument('--train-algorithm', default='sac', choices=('ddpg', 'ppo', 'sac', 'td3', 'trpo', 'vpg'))
    parser.add_argument('--train-num-hidden-layers', type=int, default=2)
    parser.add_argument('--train-hidden-layer-size', type=int, default=None)
    boolean_flag(parser, 'train-couple-net', default=True)
    parser.add_argument('--train-timesteps-per-epoch', type=int, default=5000)
    parser.add_argument('--train-epochs-per-model-save', type=int, default=None)
    training_model_params, _, args = fin_arg_parse(parser, evaluate=False)
    train(training_model_params, **args)

if __name__ == '__main__':
    main()
