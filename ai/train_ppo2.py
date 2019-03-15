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

def train(training_model_params, eval_model_params, *, train_num_hidden_layers, train_hidden_layer_size, train_num_timesteps, train_seed,
          eval_seed, evaluation, eval_num_timesteps, eval_frequency, eval_render, nice, num_cpu, model_dir):
    assert train_num_hidden_layers == 2
    assert model_dir.endswith('.tf')
    try:
        rmtree(model_dir)
    except FileNotFoundError:
        pass
    from baselines.ppo1 import mlp_policy, pposgd_simple
    set_global_seeds(train_seed)
    config = tf.ConfigProto(allow_soft_placement=True,
                            intra_op_parallelism_threads=num_cpu,
                            inter_op_parallelism_threads=num_cpu)
    session = tf.Session(config=config).__enter__()
    training_model_params['action_space_unbounded'] = eval_model_params['action_space_unbounded'] = True
    training_model_params['observation_space_ignores_range'] = True
    def policy_fn(sess, ob_space, ac_space, nbatch, nsteps, reuse=False):
        return MlpPolicy(sess=sess, ob_space=ob_space, ac_space=ac_space,
            nbatch=nbatch, nsteps=nsteps, reuse=reuse, hid_size=train_hidden_layer_size)
    def make_env():
        env = make_fin_env(training=True, **training_model_params)
        return env
    env = DummyVecEnv([make_env])
    env = VecNormalize(env)
    ppo2.learn(policy=policy_fn, env=env, nsteps=2048, nminibatches=32,
        lam=0.95, gamma=1, noptepochs=10, log_interval=1,
        ent_coef=0.0,
        lr=3e-4,
        cliprange=0.2,
        total_timesteps=train_num_timesteps)
    env.close()
    #g = tf.get_default_graph()
    #train_tf = g.get_tensor_by_name('pi/train:0')
    #action_tf = g.get_tensor_by_name('pi/action:0')
    #v_tf = g.get_tensor_by_name('pi/v:0')
    #observation_tf = g.get_tensor_by_name('pi/ob:0')
    #tf.saved_model.simple_save(session, model_dir, {'train': train_tf, 'observation': observation_tf}, {'action': action_tf, 'v': v_tf})

def main():
    parser = arg_parser()
    parser.add_argument('--train-num-hidden-layers', type=int, default=2)
    parser.add_argument('--train-hidden-layer-size', type=int, default=64)
    training_model_params, eval_model_params, args = fin_arg_parse(parser)
    logger.configure()
    train(training_model_params, eval_model_params, **args)

if __name__ == '__main__':
    main()
