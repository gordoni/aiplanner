#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019-2020 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from glob import glob
from os import getpriority, mkdir, PRIO_PROCESS, setpriority
from os.path import abspath
from shutil import rmtree


import ray
from ray.tune import function, grid_search, run
from ray.tune.config_parser import make_parser

from ai.common.cmd_util import arg_parser, fin_arg_parse
from ai.common.utils import boolean_flag
from ai.gym_fin.model_params import dump_params_file
from ai.gym_fin.fin_env import FinEnv

class RayFinEnv(FinEnv):

    def __init__(self, config):
        super().__init__(**config)

def train(training_model_params, *, redis_address, train_num_workers, train_anneal_num_timesteps, train_seeds,
    train_batch_size, train_minibatch_size, train_optimizer_epochs, train_optimizer_step_size, train_entropy_coefficient,
    train_save_frequency, train_max_failures, train_resume,
    train_num_timesteps, train_single_num_timesteps, train_couple_num_timesteps,
    train_seed, nice, num_cpu, model_dir, **ray_kwargs):

    priority = getpriority(PRIO_PROCESS, 0)
    priority += nice
    setpriority(PRIO_PROCESS, 0, priority)

    while model_dir and model_dir[-1] == '/':
        model_dir = model_dir[:-1]
    assert model_dir.endswith('.tf')
    try:
        if not train_resume:
            rmtree(model_dir)
    except FileNotFoundError:
        pass

    training_model_params['action_space_unbounded'] = True
    training_model_params['observation_space_ignores_range'] = True
    training_model_params['observation_space_clip'] = True

    try:
        mkdir(model_dir)
    except FileExistsError:
        pass
    dump_params_file(model_dir + '/params.txt', training_model_params)

    ray.init(redis_address=redis_address)
    #ray.init(object_store_memory=int(2e9))

    algorithm = training_model_params['algorithm']

    lr_schedule = [
        (0, train_optimizer_step_size),
        (max(0, train_num_timesteps - train_anneal_num_timesteps), train_optimizer_step_size),
    ]
    # Exponentially decaying anneal phase. Not usually needed; at least not when entropy_coeff provide regularization.
    #     Consider estimating the non-representativeness of the batch brought about by it being a sample from a larger universe.
    #     4 samples would have a stderr of 1/2 the non-representativeness.
    #     Thus every 4 batches would cut down the non-representativeness remaining to be cut down by a factor of 2.
    while lr_schedule[-1][0] < train_num_timesteps:
        lr_schedule.append((lr_schedule[-1][0] + train_batch_size, lr_schedule[-1][1] / 2 ** (1/4)))
    agent_config = {

        'A2C': {
        },

        'A3C': {
        },

        'PG': {
        },

        'DDPG': {
        },

        'PPO': {
            'model': {
                # Changing the fully connected net size from 256x256 (the default) to 128x128 reduces CE values.
                # At least for retired model with nominal_spias.
                # Results for preretirement, nominal_spias, train_batch_size 500k, minibach_size 500, lr 2e-5, num_sgd_iter 30, entropy 1e-4:
                # fcnet_hiddens 128x128: CE dist 81900 stderr 350
                # fcnet_hiddens 256x256: CE dist 81700 stderr 350
                # Results for retired, nominal_spias, train_batch_size 500k, minibach_size 500, lr 2e-5, num_sgd_iter 30, entropy 1e-4:
                # fcnet_hiddens 128x128: CE dist 85700 stderr 200
                # fcnet_hiddens 256x256: CE dist 86200 stderr 200
                # Reducing size is unlikely to improve the run time performance as it is dominated by fixed overhead costs:
                #     runner.run(obss, policy_graph = runner.local_policy_graph):
                #         256x256 (r5.large): 1.1ms + 0.013ms x num_observations_in_batch
                #         128x128 (r5.large): 1.1ms + 0.009ms x num_observations_in_batch
                'fcnet_hiddens': (256, 256),
            },
            'train_batch_size': train_batch_size,
                # Increasing the batch size might reduce aa variability due to training for the last batch seen.
                # Results for lr 2e-5, minibatch_size 500, fcnet_hiddens 256x256.
                # train_batch_size 200k, num_sgd_iter 10: CE dist 81200 stderr 250
                # train_batch_size 500k, num_sgd_iter 10: CE dist 82000 stderr 250
                # train_batch_size 1m, num_sgd_iter 5: CE dist 81100 stderr 450
                # i.e. 500k seems like a good choice (previously used 200k).
            'sgd_minibatch_size': train_minibatch_size,
                # Results for train_batch_size 200k, num_sgd_iter 30, fcnet_hiddens 256x256.
                # minibatch_size 128, lr 2e-6: CE dist 80900 stderr 550; grad time ~180 sec
                # minibatch_size 250, lr 5e-6: CE dist 81550 stderr 600; grad_time ~115 sec
                # minibatch_size 500, lr 1e-5: CE dist 81500 stderr 450; grad time ~85 sec
                # minibatch_size 1000, lr 2e-5: CE dist 81500 stderr 250; grad time ~80 sec
                # minibatch_size 5000, lr 1e-4: CE dist 80100 stderr 500; grad time ~80 sec
                # i.e. 500 seems like a good choice (previously used 128).
            'num_sgd_iter': train_optimizer_epochs,
                # A smaller num_sgd_iter increases the CE, but also increases the amount of rollout cpu time.
                # Results for train_batch_size 200k, minibatch_size 500, lr 2e-5, fcnet_hiddens 256x256.
                # num_sgd_iter 30: CE dist 81000 stderr 500
                # num_sgd_iter 10: CE dist 81200 stderr 250
                # Results for train_batch_size 500k, minibatch_size 500, lr 2e-5, fcnet_hiddens 256x256.
                # num_sgd_iter 30: CE dist 81450 stderr 100
                # num_sgd_iter 10: CE dist 82000 stderr 250
                # i.e. 10 seems like a good choice even though increases rollout cpu time significantly (previously used 30).
            'entropy_coeff': train_entropy_coefficient,
                # After fixing entropy for diagonal gaussian (Ray issue #6393).
                # Entropy may not make any difference. Results for lr 2e-6, sgd_minibatch_size 128, train_batch_size 200k, num_sgd_iter 30, fcnet_hiddens 256x256.
                # Entropy 0: CE dist 80550 stderr 500
                # Entropy 1e-4: CE dist 80900 stderr 500
                # Entropy 1e-3: CE dist 80800 stderr 500
                # Entropy 5e-3: seed zero diverges
                # Use entropy 1e-4 by default; might not help but unlikely to harm.
            'vf_clip_param': 10.0, # Currently equal to PPO default value.
                # Clip value function advantage estimates. We expect most rewards to be roughly in [-1, 1],
                # so if we get something far from this we don't want to train too hard on it.
            'kl_coeff': 0.0, # Disable PPO KL-Penalty, use PPO Clip only; gives better CE.
            'lr': train_optimizer_step_size,
                # lr_schedule is ignored by Ray 0.7.1 through 0.7.6+ (Ray issue #6096), so need to ensure fallback learning rate is reasonable.
                # A smaller lr requires more timesteps but produces a higher CE.
                # Results for train_batch_size 500k, minibatch_size 500, num_sgd_iter 30, fcnet_hiddens 256x256.
                # lr 1e-5: CE dist 81500 stderr 450
                # lr 2e-5: CE dist 81000 stderr 500
                # Results.
                # train_batch_size 200k, minibatch_size 128, num_sgd_iter 30, lr 5e-6, entropy_coeff 0.0: CE dist 81700 stderr 400
                # train_batch_size 500k, minibatch_size 500, num_sgd_iter 10, lr 2e-5, entropy_coeff 1e-4: CE dist 82000 stderr 250
                # i.e. 2e-5 seems like a good choice; less (weakly parallelizable) grad time in exchange for more (strongly) parallelizable rollout time
                # allows quicker computation of results (previously used 5e-6). Drops training time from 28.5 hours to 11 hours.
                #
                # If need better CE reduce lr.
            'lr_schedule': lr_schedule,
            'clip_param': 0.3,
                # Reducing clip_param may very slightly improve results but incurs increased training time.
                # Results for train_batch_size 500k, minibatch_size 500, num_sgd_iter 10, lr 2e-5, entropy_coeff 1e-4, fcnet_hiddens 256x256.
                # clip_param 0.2: CE dist 82000 stderr 300 (asymptote at ckpt 260)
                # clip_param 0.3: CE dist 82000 stderr 250 (asymptote at ckpt 220)
            # i.e. the PPO default 0.3 seems reasonable.
            'batch_mode': 'complete_episodes', # Unknown whether helps, but won't harm.
            #'shuffle_sequences': False,
        },

        'PPO.baselines': { # Compatible with AIPlanner's OpenAI baselines ppo1 implementation.
            'model': {
                'fcnet_hiddens': (64, 64),
            },
            'lambda': 0.95,
            'sample_batch_size': 256,
            'train_batch_size': 4096,
            #'sgd_minibatch_size': 128,
            'num_sgd_iter': 10,
            'lr_schedule': (
                (0, 3e-4),
                (train_num_timesteps, 0)
            ),
            'clip_param': 0.2,
            'vf_clip_param': float('inf'),
            'kl_target': 1,
            'batch_mode': 'complete_episodes',
            #'observation_filter': 'NoFilter',
        },

        'APPO': {
            # 1500m timesteps: inferior to 50m x 30 num_sgd_iter PPO.
            'num_workers': 31, # Default value is 2.
            'num_gpus': 0, # No speedup from GPUs for continuous control - https://www.reddit.com/r/MLQuestions/comments/akl6cs/hardware_for_reinforcement_learning/
            'sample_batch_size': 50, # Default value is 50.
            'train_batch_size': train_minibatch_size, # Default value is 500.
            'minibatch_buffer_size': 1, #train_batch_size // train_minibatch_size, # Default value is 1. No effect if num_sgd_iter == 1.
            'num_sgd_iter': 1, # Default value is 1.
            'vtrace': False, # Default is False.
            'replay_proportion': 0.0, #train_optimizer_epochs - 1,
            'replay_buffer_num_slots': 0, #train_batch_size // 50,
            'min_iter_time_s': 10, # Default value.
            'opt_type': 'adam', # Default value. Have not tried 'rmsprop'.
            'clip_param': 0.3, # Default is 0.4. PPO default is 0.3.
            'lr': train_optimizer_step_size, # Default is 5e-4.
            'lr_schedule': lr_schedule,
            'vf_loss_coeff': 0.5, # Default is 0.5.
            'entropy_coeff': 0.0, # Default is 0.01.
        },

        'IMPALA': {
            # 1500m timesteps: better than APPO, but possibly inferior (within training noise) to 50m x 30 num_sgd_iter PPO.
            'num_workers': 31, # Default value is 2.
            'num_gpus': 0,
            'sample_batch_size': 50, # Default value is 50.
            'train_batch_size': 500, # Default value is 500. 128 performs much worse. 5000 performs no better.
            'minibatch_buffer_size': 1, # 1, # Default value is 1. No effect if num_sgd_iter == 1.
                # Bad results for minibatch_buffer_size 400, num_sgd_iter 30, lr 5e-6. Probably need smaller stepsize, but then will take longer to train.
            'num_sgd_iter': 1, # Default value is 1.
            'replay_proportion': 0.0, # Default value is 0.0.
                # Bad results for replay_proportion 29.0, replay_buffer_num_slots 4000, lr 5e-6. Probably need smaller stepsize, but then will take longer to train.
            'replay_buffer_num_slots': 0, # Default value is 0.
            'min_iter_time_s': 10, # Default value.
            'learner_queue_timeout': 300, # Default value.
            'opt_type': 'adam', # Default value.
            'lr': train_optimizer_step_size, # Default is 5e-4. 5e-5 performs a lot worse than 5e-6. 5e-7 performs much slower than 5e-6.
            'lr_schedule': lr_schedule,
            'vf_loss_coeff': 0.5, # Default is 0.5.
            'entropy_coeff': 0.0, # Default is 0.01.
        }

    }[algorithm]
    agent_config = dict(agent_config, **ray_kwargs['config'])

    trainable = algorithm[:-len('.baselines')] if algorithm.endswith('.baselines') else algorithm
    trial_name = lambda trial: 'seed_' + str(trial.config['seed'] // 1000)
    if train_num_workers == None:
        num_workers = agent_config.get('num_workers', 1 if algorithm in ('A3C', 'APPO', 'IMPALA') else 0)
    else:
        num_workers = train_num_workers
    if train_save_frequency == None:
        checkpoint_freq = 0
    elif trainable in ('PPO', ):
        checkpoint_freq = max(1, train_save_frequency // agent_config['train_batch_size'])
    elif trainable in ('APPO', 'IMPALA'):
        rough_timestep_rate = 2000
        checkpoint_freq = max(1, train_save_frequency // (rough_timestep_rate * agent_config['min_iter_time_s']))
    else:
        assert False

    # from pympler import tracker
    # def on_train_result(info):
    #     global tr
    #     try:
    #         tr
    #     except NameError:
    #         tr = tracker.SummaryTracker()
    #     tr.print_diff()

    run(
        trainable,
        name = './',
        trial_name_creator = function(trial_name),

        config = dict({
            'env': RayFinEnv,
            'env_config': training_model_params,
            'clip_actions': False,
            'gamma': 1,
            'seed': grid_search(list(range(train_seed * 1000, (train_seed + train_seeds) * 1000, 1000))), # Workers are assigned consecutive seeds.

            #'num_gpus': 0,
            #'num_cpus_for_driver': 1,
            'num_workers': num_workers,
            #'num_envs_per_worker': 1,
            #'num_cpus_per_worker': 1,
            #'num_gpus_per_worker': 0,

            'tf_session_args': {
                'intra_op_parallelism_threads': 1,
                'inter_op_parallelism_threads': 1,
            },
            'local_tf_session_args': {
                'intra_op_parallelism_threads': num_cpu,
                'inter_op_parallelism_threads': num_cpu,
            },

            'callbacks': {
                # 'on_train_result': function(on_train_result),
            },
        }, **agent_config),

        stop = {
            'timesteps_total': train_num_timesteps,
        },

        local_dir = abspath(model_dir),
        checkpoint_freq = checkpoint_freq,
        checkpoint_at_end = True,
        max_failures = train_max_failures,
        resume = train_resume,
        queue_trials = redis_address != None
    )

def main():
    parser = make_parser(lambda: arg_parser(evaluate=False))
    parser.add_argument('--redis-address')
    parser.add_argument('--train-num-workers', type=int, default=8) # Number of rollout worker processes.
        # Default appropriate for a short elapsed time with train_optimizer_epochs 10.
        # Set to 0, or possibly 1, for deterministic training.
    parser.add_argument('--train-anneal-num-timesteps', type=int, default=0)
    parser.add_argument('--train-seeds', type=int, default=1) # Number of parallel seeds to train.
    parser.add_argument('--train-batch-size', type=int, default=500000)
    parser.add_argument('--train-minibatch-size', type=int, default=500)
    parser.add_argument('--train-optimizer-epochs', type=int, default=10)
    parser.add_argument('--train-optimizer-step-size', type=float, default=2e-5)
    parser.add_argument('--train-entropy-coefficient', type=float, default=1e-4)
    parser.add_argument('--train-save-frequency', type=int, default=None) # Save frequency in timesteps.
    parser.add_argument('--train-max-failures', type=int, default=3)
    boolean_flag(parser, 'train-resume', default = False) # Resume training rather than starting new trials.
        # To resume running trials for which Ray appears to have hung with no running worker processes or worker nodes (check has redis died?),
        # it is recommended first make a copy the model(s) directory, and then stop Ray and reinvoke training with --train-resume.
        # First time attempted this got redis connection error on 2 of 20 processes, which couldn't be corrected,
        # but having a copy of the model(s) directory allowed me to rollback and retry successfully.
        #
        # To attempt to resume trials that have errored edit the latest <model_dir>/seed_0/experiment_state-<date>.json (Note: Use seed_0 for all experiments).
        # changing all of their statuses from "ERROR" to "RUNNING", and then invoke this script with --train-resume.
        # Didn't work, state changed to "RUNNING", but not actually running.
        #
        # To attempt to extend already completed trials edit the latest <model_dir>/seed_0/experiment_state-<date>.json
        # changing all of their statuses from "TERMINATED" to "RUNNING", and timeteps_total to <new_timestep_limit>,
        # then invoke this script with --train-resume --train-num-timesteps=<new_timestep_limit>.
        # Didn't work, not sure what the problem is, but Rllib resume is currently experimental.
    training_model_params, _, args = fin_arg_parse(parser, evaluate=False)
    if not training_model_params['algorithm']:
         training_model_params['algorithm'] = 'PPO'
    train(training_model_params, **args)

if __name__ == '__main__':
    main()
