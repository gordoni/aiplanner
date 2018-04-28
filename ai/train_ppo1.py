#!/usr/bin/python3

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

from baselines import logger
from baselines.common import tf_util as U
from baselines.common.misc_util import set_global_seeds

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator

def train(training_model_params, eval_model_params, *, nb_hidden_layers, hidden_layer_size, num_timesteps, seed,
        eval_seed, evaluation, nb_eval_steps, eval_frequency, render_eval):
    from baselines.ppo1 import mlp_policy, pposgd_simple
    set_global_seeds(seed)
    U.make_session(num_cpu=1).__enter__()
    def policy_fn(name, ob_space, ac_space):
        return mlp_policy.MlpPolicy(name=name, ob_space=ob_space, ac_space=ac_space,
            hid_size=hidden_layer_size, num_hid_layers=nb_hidden_layers)
    env = make_fin_env(action_space_unbounded=True, training=True, **training_model_params)
    if evaluation:
        eval_env = make_fin_env(action_space_unbounded=True, training=False, **eval_model_params)
        evaluator = Evaluator(eval_env, eval_seed, nb_eval_steps, render_eval)
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
    pposgd_simple.learn(env, policy_fn,
            max_timesteps=num_timesteps,
            timesteps_per_actorbatch=2048,
            clip_param=0.2, entcoeff=0.0,
            optim_epochs=10, optim_stepsize=3e-4, optim_batchsize=64,
            gamma=1, lam=0.95, schedule='linear',
            callback=eval_callback
        )
    env.close()

def main():
    parser = arg_parser()
    parser.add_argument('--nb-hidden-layers', type=int, default=2)
    parser.add_argument('--hidden-layer-size', type=int, default=64)
    training_model_params, eval_model_params, args = fin_arg_parse(parser)
    logger.configure()
    train(training_model_params, eval_model_params, **args)

if __name__ == '__main__':
    main()
