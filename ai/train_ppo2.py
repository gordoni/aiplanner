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

# Code based on baselines/ppo2/run_mujoco.py

from shutil import rmtree

import tensorflow as tf

from baselines import logger
from baselines.common import tf_util as U
from baselines.common.misc_util import set_global_seeds
from baselines.common.vec_env.vec_normalize import VecNormalize
from baselines.ppo2 import ppo2
from baselines.ppo2.policies import MlpPolicy
from baselines.common.vec_env.dummy_vec_env import DummyVecEnv

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator

def train(training_model_params, eval_model_params, *, nb_hidden_layers, hidden_layer_size, num_timesteps, seed,
          eval_seed, evaluation, eval_num_timesteps, eval_frequency, eval_render, model_dir):
    assert model_dir.endswith('.tf')
    try:
        rmtree(model_dir)
    except FileNotFoundError:
        pass
    from baselines.ppo1 import mlp_policy, pposgd_simple
    set_global_seeds(seed)
    ncpu = 1
    config = tf.ConfigProto(allow_soft_placement=True,
                            intra_op_parallelism_threads=ncpu,
                            inter_op_parallelism_threads=ncpu)
    session = tf.Session(config=config).__enter__()
    def policy_fn(name, ob_space, ac_space):
        return mlp_policy.MlpPolicy(name=name, ob_space=ob_space, ac_space=ac_space,
            hid_size=hidden_layer_size, num_hid_layers=nb_hidden_layers)
    def make_env():
        env = make_fin_env(action_space_unbounded=True, training=True, **training_model_params)
        return env
    env = DummyVecEnv([make_env])
    env = VecNormalize(env)
    if evaluation:
        eval_env = make_fin_env(action_space_unbounded=True, training=False, **eval_model_params)
        evaluator = Evaluator(eval_env, eval_seed, eval_num_timesteps, eval_render)
        global next_eval_timestep
        next_eval_timestep = 0
        def eval_callback(l, g):
            global next_eval_timestep
            if l['timesteps_so_far'] < next_eval_timestep:
                return False
            next_eval_timestep = l['timesteps_so_far'] + eval_frequency
            def pi(obs):
                stochastic = False
                action, vpred = l['pi'].act(stochastic, obs)
                return action
            return evaluator.evaluate(pi)
    else:
        eval_env = None
        eval_callback = None
    policy = MlpPolicy
    ppo2.learn(policy=policy, env=env, nsteps=2048, nminibatches=32,
        lam=0.95, gamma=1, noptepochs=10, log_interval=1,
        ent_coef=0.0,
        lr=3e-4,
        cliprange=0.2,
        total_timesteps=num_timesteps)
    env.close()
    if eval_env:
        eval_env.close()
    #g = tf.get_default_graph()
    #train_tf = g.get_tensor_by_name('pi/train:0')
    #action_tf = g.get_tensor_by_name('pi/action:0')
    #v_tf = g.get_tensor_by_name('pi/v:0')
    #observation_tf = g.get_tensor_by_name('pi/ob:0')
    #tf.saved_model.simple_save(session, model_dir, {'train': train_tf, 'observation': observation_tf}, {'action': action_tf, 'v': v_tf})

def main():
    parser = arg_parser()
    parser.add_argument('--nb-hidden-layers', type=int, default=2)
    parser.add_argument('--hidden-layer-size', type=int, default=64)
    training_model_params, eval_model_params, args = fin_arg_parse(parser)
    logger.configure()
    train(training_model_params, eval_model_params, **args)

if __name__ == '__main__':
    main()
