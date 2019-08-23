# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from glob import glob
from os.path import isdir, join
from pickle import load
from shutil import rmtree

import numpy as np

import tensorflow as tf

from baselines.common import tf_util as U

from ray.rllib.evaluation.worker_set import WorkerSet

class TFRunner:

    def __init__(self, *, train_dirs = ['aiplanner.tf'], checkpoint_name = None, eval_model_params, couple_net = True,
        redis_address = None, num_workers = 1, worker_seed = 0, num_environments = 1, num_cpu = None,
        evaluator = True, export_model = False):

        self.couple_net = couple_net
        self.session = None
        self.local_policy_graph = None
        self.remote_evaluators = None
        self.sessions = []
        self.observation_tfs = []
        self.action_tfs = []

        tf_name = checkpoint_name or 'tensorflow'
        tf_dir = train_dirs[0] + '/' + tf_name
        tensorflow = isdir(tf_dir)
        #rllib_checkpoints = glob(train_dirs[0] + '/*/checkpoint_*')
        if not tensorflow:

            # Rllib.
            import ray
            from ray.rllib.agents.registry import get_agent_class
            from ray.rllib.evaluation import PolicyGraph

            from train_rllib import RayFinEnv

            if not ray.is_initialized():
                ray.init(redis_address = redis_address)

            weights = []
            first = True
            for train_dir in train_dirs:

                checkpoints = glob(train_dir + '**/checkpoint_*', recursive = True)
                if not checkpoint_name:
                    assert checkpoints, 'No Rllib checkpoints found: ' + train_dir
                    checkpoint_name = 'checkpoint_' + str(max(int(checkpoint.split('_')[-1]) for checkpoint in checkpoints))
                checkpoint_dir, = glob(train_dir + '**/' + checkpoint_name)
                checkpoint, = glob(checkpoint_dir + '/checkpoint-*[0-9]', recursive = True)

                if first:
                    config_path = join(checkpoint_dir, '../params.pkl')
                    with open(config_path, 'rb') as f:
                        config = load(f)

                    cls = get_agent_class(config['env_config']['algorithm'])
                    config['env_config'] = eval_model_params
                    config['num_envs_per_worker'] = num_environments
                    config['seed'] = worker_seed
                    config['sample_mode'] = True # Rllib hack to return modal sample not a randomly perturbed one.

                agent = cls(env = RayFinEnv, config = config)
                agent.restore(checkpoint)

                if export_model:
                    export_dir = train_dir + '/tensorflow'
                    assert '.tf/' in export_dir
                    try:
                        rmtree(export_dir)
                    except FileNotFoundError:
                        pass
                    agent.export_policy_model(export_dir)

                if not evaluator:
                    return

                weight = agent.get_weights()['default_policy']
                weights.append(weight)

                first = False

            class EnsemblePolicy(agent._policy):

                def __init__(self, observation_space, action_space, config, *args, **kwargs):

                    super().__init__(observation_space, action_space, config, *args, **kwargs)
                    self.policies = []
                    for w in weights:
                        graph = tf.Graph()
                        with graph.as_default() as g:
                            tf_config = tf.ConfigProto(
                                inter_op_parallelism_threads = num_cpu,
                                intra_op_parallelism_threads = num_cpu
                            )
                            with tf.Session(graph = graph, config = tf_config).as_default() as sess:
                                policy = agent._policy(observation_space, action_space, config, *args, **kwargs)
                                self.policies.append(policy)

                def set_weights(self, weights):

                    for policy, w in zip(self.policies, weights):
                        policy.set_weights(w)

                def compute_actions(self, *args, **kwargs):

                    actions_ca = [policy.compute_actions(*args, **kwargs) for policy in self.policies]
                    actions = np.array([action[0] for action in actions_ca])
                    # Get slightly better CEs (retired, SPIAs, gamma=1.5) taking mean, than first dropping high/low.
                    #mean_action = (np.sum(actions, axis = 0) - np.amin(actions, axis = 0) - np.amax(actions, axis = 0)) / (actions.shape[0] - 2)
                    mean_action = np.mean(actions, axis = 0)
                    return [mean_action] + list(actions_ca[0][1:])

                #def copy(self, existing_inputs):
                #    return EnsemblePolicy(self.observation_space, self.action_space, self.config, existing_inputs = existing_inputs)

            policy = agent.workers.local_worker().get_policy()

            agent_weights = {'default_policy': weights}

            env_creator = lambda x: RayFinEnv(config['env_config'])
            # Delete workers and optimizer, they cause deserialization to fail.
            # Not precisely sure why, but this fixes the problem. They aren't needed for remote evaluation.
            del agent.workers
            del agent.optimizer
            workers = WorkerSet(env_creator, EnsemblePolicy, agent.config, num_workers = num_workers)
            workers.foreach_worker(lambda w: w.set_weights(agent_weights))
            self.remote_evaluators = workers.remote_workers()

            self.policy = workers.local_worker().get_policy()

        else:

            try:

                # Rllib tensorflow.
                for train_dir in train_dirs:
                    tf_dir = train_dir + '/' + tf_name
                    graph = tf.Graph()
                    with graph.as_default() as g:
                        tf_config = tf.ConfigProto(
                            inter_op_parallelism_threads = num_cpu,
                            intra_op_parallelism_threads = num_cpu
                        )
                        with tf.Session(graph = graph, config = tf_config).as_default() as session:
                            metagraph = tf.saved_model.loader.load(session, [tf.saved_model.tag_constants.SERVING], tf_dir)
                            inputs = metagraph.signature_def['serving_default'].inputs
                            outputs = metagraph.signature_def['serving_default'].outputs
                            observation_tf = graph.get_tensor_by_name(inputs['observations'].name)
                            action_tf = graph.get_tensor_by_name(outputs['actions'].name)
                            self.sessions.append(session)
                            self.observation_tfs.append(observation_tf)
                            self.action_tfs.append(action_tf)

            except KeyError:

                self.session = U.make_session(num_cpu = num_cpu).__enter__()

                try:

                    # OpenAI Spinning Up.
                    from spinup.utils.logx import restore_tf_graph
                    model_graph = restore_tf_graph(self.session, tf_dir + '/simple_save')
                    self.observation_sigle_tf = observation_couple_tf = model_graph['x']
                    try:
                        self.action_single_tf = action_couple_tf = model_graph['mu']
                    except KeyError:
                        self.action_single_tf = action_couple_tf = model_graph['pi']

                except (ModuleNotFoundError, IOError):

                    # OpenAI Baselines.
                    tf.saved_model.loader.load(self.session, [tf.saved_model.tag_constants.SERVING], tf_dir)
                    g = tf.get_default_graph()
                    self.observation_single_tf = g.get_tensor_by_name('single/ob:0')
                    self.action_single_tf = g.get_tensor_by_name('single/action:0')
                    try:
                        self.observation_couple_tf = g.get_tensor_by_name('couple/ob:0')
                        self.action_couple_tf = g.get_tensor_by_name('couple/action:0')
                    except KeyError:
                        self.observation_couple_tf = self.action_couple_tf = None

    def __enter__(self):

        return self

    def __exit__(self, exception_type, exception_value, traceback):

        if self.session:
            self.session.__exit__(exception_type, exception_value, traceback)
            tf.reset_default_graph()

    def is_couple(self, ob):
        return ob[0] == 1

    def _run_unit(self, couple, obss):

        if self.sessions:

                actions = [session.run(action_tf, feed_dict = {observation_tf: obss}) \
                    for session, observation_tf, action_tf in zip(self.sessions, self.observation_tfs, self.action_tfs)]
                mean_action = np.mean(actions, axis = 0)
                return mean_action

        if self.session:

            action_tf = self.action_couple_tf if couple else self.action_single_tf
            observation_tf = self.observation_couple_tf if couple else self.observation_single_tf
            return self.session.run(action_tf, feed_dict = {observation_tf: obss})

        else:

            return self.policy.compute_actions(obss)[0]

    def run(self, obss):

        single_obss = []
        couple_obss = []
        single_idx = []
        couple_idx = []
        for i, obs in enumerate(obss):
            if self.is_couple(obs) and self.couple_net:
                couple_obss.append(obs)
                couple_idx.append(i)
            else:
                single_obss.append(obs)
                single_idx.append(i)
        action = [None] * len(obss)
        if single_obss:
            single_action = self._run_unit(False, single_obss)
            for i, act in zip(single_idx, single_action):
                action[i] = act
        if couple_obss:
            couple_action = self._run_unit(True, couple_obss)
            for i, act in zip(couple_idx, couple_action):
                action[i] = act

        return action
