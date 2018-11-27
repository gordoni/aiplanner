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

from os import getpriority, mkdir, PRIO_PROCESS, setpriority
from shutil import rmtree

import tensorflow as tf

from baselines import logger
from baselines.common import boolean_flag, tf_util as U
from baselines.common.misc_util import set_global_seeds

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator
from gym_fin.envs.model_params import dump_params_file

def train(training_model_params, eval_model_params, *, train_num_hidden_layers, train_hidden_layer_size, train_batch_size,
          train_single_minibatch_size, train_couple_minibatch_size, train_optimizer_epochs, train_optimizer_step_size, train_gae_lambda,
          train_couple_net, train_num_timesteps, train_single_num_timesteps, train_couple_num_timesteps, train_seed,
          eval_seed, evaluation, eval_num_timesteps, eval_frequency, eval_render, nice, num_cpu, model_dir):

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

    from baselines.ppo1 import mlp_policy, pposgd_dual
    set_global_seeds(train_seed)
    session = U.make_session(num_cpu=num_cpu).__enter__()
    training_model_params['action_space_unbounded'] = eval_model_params['action_space_unbounded'] = True
    training_model_params['observation_space_ignores_range'] = False
    env = make_fin_env(training=True, **training_model_params)
    couple = training_model_params['sex2'] != None
    couple_net = couple and train_couple_net
    if evaluation:
        eval_seed += 1000000 # Use a different seed than might have been used during training.
        eval_env = make_fin_env(training=False, **eval_model_params)
        evaluator = Evaluator([eval_env], eval_seed, eval_num_timesteps, render = eval_render, eval_batch_monitor = True)
        global next_eval_timestep
        next_eval_timestep = 0
        def callback(l, g):
            global next_eval_timestep
            if env.unwrapped.env_single_timesteps >= train_single_num_timesteps and \
                (not couple or env.unwrapped.env_couple_timesteps >= train_couple_num_timesteps):
                return True
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
        def callback(l, g):
            return env.unwrapped.env_single_timesteps >= train_single_num_timesteps and \
                (not couple or env.unwrapped.env_couple_timesteps >= train_couple_num_timesteps)

    def policy_fn(name, ob_space, ac_space):
        return mlp_policy.MlpPolicy(name=name, ob_space=ob_space, ac_space=ac_space,
            hid_size=train_hidden_layer_size, num_hid_layers=train_num_hidden_layers)
    pposgd_dual.learn(env, policy_fn, couple_net,
        max_timesteps=train_num_timesteps,
        timesteps_per_actorbatch=train_batch_size,
        clip_param=0.2, entcoeff=0.0,
        optim_epochs=train_optimizer_epochs, optim_stepsize=train_optimizer_step_size,
        optim_single_batchsize=train_single_minibatch_size, optim_couple_batchsize=train_couple_minibatch_size,
        gamma=1, lam=train_gae_lambda, schedule='linear',
        callback=callback
    )

    env.close()
    if eval_env:
        eval_env.close()
    g = tf.get_default_graph()
    observation_tf = g.get_tensor_by_name('single/ob:0')
    action_tf = g.get_tensor_by_name('single/action:0')
    #v_tf = g.get_tensor_by_name('single/pi/v:0')
    tf.saved_model.simple_save(session, model_dir, {'observation': observation_tf}, {'action': action_tf})
    assets_dir = model_dir + '/assets.extra'
    mkdir(assets_dir)
    dump_params_file(assets_dir + '/params.txt', training_model_params)

def main():
    parser = arg_parser()
    parser.add_argument('--train-num-hidden-layers', type=int, default=2)
    parser.add_argument('--train-hidden-layer-size', type=int, default=64)
    parser.add_argument('--train-batch-size', type=int, default=2048)
    parser.add_argument('--train-single-minibatch-size', type=int, default=128) # Canonical PPO1 defaults to 64. Use larger value because problem is stochastic.
    parser.add_argument('--train-couple-minibatch-size', type=int, default=512) # Couple uses an even larger value because first death is non-probabilistic.
    parser.add_argument('--train-optimizer-epochs', type=int, default=10)
    parser.add_argument('--train-optimizer-step-size', type=float, default=3e-4)
    parser.add_argument('--train-gae-lambda', type=float, default=0.95)
    boolean_flag(parser, 'train-couple-net', default = True)
    training_model_params, eval_model_params, args = fin_arg_parse(parser)
    logger.configure()
    train(training_model_params, eval_model_params, **args)

if __name__ == '__main__':
    main()
