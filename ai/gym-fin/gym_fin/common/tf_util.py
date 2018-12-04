# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

import tensorflow as tf

from baselines.common import tf_util as U

class TFRunner:

    def __init__(self, *, tf_dir = 'aiplanner.tf/tensorflow', couple_net = True, num_cpu = None):

        self.couple_net = couple_net

        self.session = U.make_session(num_cpu = num_cpu).__enter__()

        try:

            from spinup.utils.logx import restore_tf_graph
            model_graph = restore_tf_graph(self.session, tf_dir + '/simple_save')
            self.observation_sigle_tf = observation_couple_tf = model_graph['x']
            try:
                self.action_single_tf = action_couple_tf = model_graph['mu']
            except KeyError:
                self.action_single_tf = action_couple_tf = model_graph['pi']

        except (ModuleNotFoundError, IOError):

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

        self.session.__exit__(exception_type, exception_value, traceback)
        tf.reset_default_graph()

    def is_couple(self, ob):
        return ob[0] == 1

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
            single_action = self.session.run(self.action_single_tf, feed_dict = {self.observation_single_tf: single_obss})
            for i, act in zip(single_idx, single_action):
                action[i] = act
        if couple_obss:
            couple_action = self.session.run(self.action_couple_tf, feed_dict = {self.observation_couple_tf: couple_obss})
            for i, act in zip(couple_idx, couple_action):
                action[i] = act

        return action
