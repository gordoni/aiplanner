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

# Code based on baselines/ppo1/run_mujoco.py

from os import mkdir
from shutil import rmtree

import tensorflow as tf

from baselines import logger
from baselines.common import tf_util as U
from baselines.common.misc_util import set_global_seeds

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator
from gym_fin.envs.model_params import dump_params_file

def train(training_model_params, eval_model_params, *, train_num_hidden_layers, train_hidden_layer_size, train_minibatch_size,
          train_num_timesteps, train_single_num_timesteps, train_couple_num_timesteps, train_seed,
          eval_seed, evaluation, eval_num_timesteps, eval_frequency, eval_render, model_dir):
    while model_dir and model_dir[-1] == '/':
        model_dir = model_dir[:-1]
    assert model_dir.endswith('.tf')
    try:
        rmtree(model_dir)
    except FileNotFoundError:
        pass
    from baselines.ppo1 import mlp_policy, pposgd_simple
    set_global_seeds(train_seed)
    session = U.make_session(num_cpu=1).__enter__()
    env = make_fin_env(action_space_unbounded=True, training=True, **training_model_params)
    couple = training_model_params['sex2'] != None
    if evaluation:
        eval_seed += 1000000 # Use a different seed than might have been used during training.
        eval_env = make_fin_env(action_space_unbounded=True, training=False, **eval_model_params)
        evaluator = Evaluator([eval_env], eval_seed, eval_num_timesteps, render = eval_render, eval_batch_monitor = True)
        global next_eval_timestep
        next_eval_timestep = 0
        def eval_callback(l, g):
            global next_eval_timestep
            if l['timesteps_so_far'] < next_eval_timestep:
                return False
            next_eval_timestep = l['timesteps_so_far'] + eval_frequency
            def pi(obss):
                obs, = obss
                stochastic = False
                action, vpred = l['pi'].act(stochastic, obs)
                return [action]
            evaluator.evaluate(pi)
            return False
    else:
        eval_env = None
        eval_callback = None
        def eval_callback(l, g):
            if env.unwrapped.env_single_timesteps >= train_single_num_timesteps and (not couple or env.unwrapped.env_couple_timesteps >= train_couple_num_timesteps):
                l['timesteps_so_far'] = train_num_timesteps # Leads to termination of training.
            return False

    def policy_fn(name, ob_space, ac_space):
        return mlp_policy.MlpPolicy(name=name, ob_space=ob_space, ac_space=ac_space,
            hid_size=train_hidden_layer_size, num_hid_layers=train_num_hidden_layers,
            couple=couple)
    pposgd_simple.learn(env, policy_fn,
        max_timesteps=train_num_timesteps,
        timesteps_per_actorbatch=2048,
        clip_param=0.2, entcoeff=0.0,
        optim_epochs=10, optim_stepsize=3e-4, optim_batchsize=train_minibatch_size,
        gamma=1, lam=0.95, schedule='linear',
        callback=eval_callback
    )

    env.close()
    if eval_env:
        eval_env.close()
    g = tf.get_default_graph()
    action_tf = g.get_tensor_by_name('pi/action:0')
    v_tf = g.get_tensor_by_name('pi/v:0')
    observation_tf = g.get_tensor_by_name('pi/ob:0')
    tf.saved_model.simple_save(session, model_dir, {'observation': observation_tf}, {'action': action_tf, 'value': v_tf})
    assets_dir = model_dir + '/assets.extra'
    mkdir(assets_dir)
    dump_params_file(assets_dir + '/params.txt', training_model_params)

def main():
    parser = arg_parser()
    parser.add_argument('--train-num-hidden-layers', type=int, default=2)
    parser.add_argument('--train-hidden-layer-size', type=int, default=64)
    parser.add_argument('--train-minibatch-size', type=int, default=128)
    training_model_params, eval_model_params, args = fin_arg_parse(parser)
    logger.configure()
    train(training_model_params, eval_model_params, **args)

if __name__ == '__main__':
    main()
