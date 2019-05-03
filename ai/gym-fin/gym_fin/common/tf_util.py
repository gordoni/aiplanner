# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from glob import glob
from os.path import join
from pickle import load

import numpy as np

import tensorflow as tf

from baselines.common import tf_util as U

class TFRunner:

    def __init__(self, *, train_dirs = ['aiplanner.tf'], checkpoint_name = None, eval_model_params, couple_net = True,
        redis_address = None, num_workers = 1, num_environments = 1, num_cpu = None):

        self.couple_net = couple_net
        self.session = None
        self.local_policy_graph = None
        self.remote_evaluators = None

        rllib_checkpoints = glob(train_dirs[0] + '/*/checkpoint_*')
        if rllib_checkpoints:

            # RLlib.
            import ray
            from ray.rllib.agents.registry import get_agent_class
            from ray.rllib.evaluation import PolicyGraph

            from train_rllib import RayFinEnv

            if not ray.is_initialized():
                ray.init(redis_address = redis_address)

            weights = []
            first = True
            for train_dir in train_dirs:

                checkpoints = glob(train_dir + '/*/checkpoint_*')
                if not checkpoint_name:
                    checkpoint_name = 'checkpoint_' + str(max(int(checkpoint.split('_')[-1]) for checkpoint in checkpoints))
                checkpoint_dir, = glob(train_dir + '/*/' + checkpoint_name)
                checkpoint, = glob(checkpoint_dir + '/checkpoint-*[0-9]')

                if first:
                    config_path = join(checkpoint_dir, '../params.pkl')
                    with open(config_path, 'rb') as f:
                        config = load(f)

                    cls = get_agent_class(config['env_config']['algorithm'])
                    config['env_config'] = eval_model_params
                    config['num_envs_per_worker'] = num_environments
                    config['sample_mode'] = True # Rllib hack to return modal sample not a randomly perturbed one.

                agent = cls(env = RayFinEnv, config = config)
                agent.restore(checkpoint)
                weight = agent.local_evaluator.get_weights()['default']
                weights.append(weight)

                first = False

            class EnsemblePolicyGraph(agent._policy_graph):

                def __init__(self, observation_space, action_space, config, *args, **kwargs):

                    super().__init__(observation_space, action_space, config, *args, **kwargs)
                    self.policy_graphs = []
                    for w in weights:
                        graph = tf.Graph()
                        with graph.as_default() as g:
                            tf_config = tf.ConfigProto(
                                inter_op_parallelism_threads = num_cpu,
                                intra_op_parallelism_threads = num_cpu
                            )
                            with tf.Session(graph = graph, config = tf_config).as_default() as sess:
                                policy_graph = agent._policy_graph(observation_space, action_space, config)
                                self.policy_graphs.append(policy_graph)

                def set_weights(self, weights):

                    for policy_graph, w in zip(self.policy_graphs, weights):
                        policy_graph.set_weights(w)

                def compute_actions(self, *args, **kwargs):

                    actions = [policy_graph.compute_actions(*args, **kwargs) for policy_graph in self.policy_graphs]
                    mean_action = np.mean(np.array([action[0] for action in actions]), axis=0)
                    return [mean_action] + list(actions[0][1:])

                def copy(self, existing_inputs):
                    return EnsemblePolicyGraph(self.observation_space, self.action_space, self.config, existing_inputs = existing_inputs)

            agent_weights = {'default': weights}

            local_evaluator = agent.make_local_evaluator(agent.env_creator, EnsemblePolicyGraph)
            local_evaluator.set_weights(agent_weights)
            self.policy_graph = local_evaluator.get_policy()

            # Delete local evaluator and optimizer, they cause deserialization to fail.
            # Not precisely sure why, but this fixes the problem. They aren't needed for remote evaluation.
            del agent.local_evaluator
            del agent.optimizer
            self.remote_evaluators = agent.make_remote_evaluators(agent.env_creator, EnsemblePolicyGraph, num_workers)
            weights = ray.put(agent_weights)
            for e in self.remote_evaluators:
                e.set_weights.remote(weights)

        else:

            if not checkpoint_name:
                checkpoint_name = 'tensorflow'
            tf_dir = train_dirs[0] + '/' + checkpoint_name

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

        if self.session:

            action_tf = self.action_couple_tf if couple else self.action_single_tf
            observation_tf = self.observation_couple_tf if couple else self.observation_single_tf
            return self.session.run(action_tf, feed_dict = {observation_tf: obss})

        else:

            return self.policy_graph.compute_actions(obss)[0]

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
