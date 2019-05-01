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

import tensorflow as tf

from baselines.common import tf_util as U

class TFRunner:

    def __init__(self, *, tf_dir = 'aiplanner.tf/tensorflow', eval_model_params, couple_net = True, num_workers = 1, num_environments = 1, num_cpu = None):

        self.couple_net = couple_net
        self.session = None
        self.local_policy_graph = None
        self.remote_evaluators = None

        rllib_checkpoints = glob(tf_dir + '/checkpoint-*[0-9]')
        if rllib_checkpoints:

            num_checkpoint = {int(checkpoint.split('-')[-1]): checkpoint for checkpoint in rllib_checkpoints}
            checkpoint = num_checkpoint[max(num_checkpoint)]

            # RLlib.
            import ray
            from ray.rllib.agents.registry import get_agent_class

            from train_rllib import RayFinEnv

            config_path = join(tf_dir, '../params.pkl')
            with open(config_path, 'rb') as f:
                config = load(f)

            cls = get_agent_class(config['env_config']['algorithm'])
            config['env_config'] = eval_model_params
            config['num_envs_per_worker'] = num_environments
            config['sample_mode'] = True
            agent = cls(env = RayFinEnv, config = config)
            agent.restore(checkpoint)

            self.local_policy_graph = agent.local_evaluator.get_policy()

            self.remote_evaluators = agent.make_remote_evaluators(agent.env_creator, agent._policy_graph, num_workers)
            weights = ray.put(agent.local_evaluator.get_weights())
            for e in self.remote_evaluators:
                e.set_weights.remote(weights)

        else:

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

    def _run_unit(self, couple, obss, policy_graph):

        if self.session:

            action_tf = self.action_couple_tf if couple else self.action_single_tf
            observation_tf = self.observation_couple_tf if couple else self.observation_single_tf
            return self.session.run(action_tf, feed_dict = {observation_tf: obss})

        else:

            return policy_graph.compute_actions(obss)[0]

    def run(self, obss, policy_graph = None):

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
            single_action = self._run_unit(False, single_obss, policy_graph)
            for i, act in zip(single_idx, single_action):
                action[i] = act
        if couple_obss:
            couple_action = self._run_unit(True, couple_obss, policy_graph)
            for i, act in zip(couple_idx, couple_action):
                action[i] = act

        return action
