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

from argparse import ArgumentParser
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
from json import dumps, loads

import tensorflow as tf

from baselines import logger
from baselines.common import (
    tf_util as U,
)
from baselines.common.misc_util import set_global_seeds

from gym_fin.common.evaluator import Evaluator
from gym_fin.envs.bonds import BondsSet
from gym_fin.envs.fin_env import FinEnv
from gym_fin.envs.policies import policy

host = 'localhost'
port = 3000

data_root = '/tmp/aiplanner-data'

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):

    pass

class RequestHandler(BaseHTTPRequestHandler):

    def do_POST(self):

        if self.path == '/api/scenario':

            content_type = self.headers.get('Content-Type')
            content_length = int(self.headers['Content-Length'])
            data = self.rfile.read(content_length)
            json_data = data.decode('utf-8')
            request = loads(json_data)

            result = self.run_model(request)

            result_bytes = dumps(result).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(result_bytes))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(result_bytes)
            return

        self.send_error(404)

    def do_GET(self):

        if self.path.startswith('/api/data/'):

            asset = self.path[len('/api/data/'):];
            if '..' not in asset:
                if asset.endswith('.png'):
                    filetype = 'image/png'
                elif asset.endswith('.svg'):
                    filetype = 'image/svg+xml'
                else:
                    filetype = None
                if filetype:
                    path = data_root + '/' + asset
                    try:
                        data = open(path, 'rb').read()
                    except IOError:
                        pass
                    else:
                        self.send_response(200)
                        self.send_header('Content-Type', filetype)
                        self.send_header('Content-Length', len(data))
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        self.wfile.write(data)
                        return

        self.send_error(404)

    bonds_cache = [BondsSet()]
        # Cache of pre-computed BondsSets. Handled in thread-safe manner.

    def run_model(self, request):

        model_dir = args.master_model_dir
        model_params = loads(open(model_dir + '/assets.extra/params.json').read())

        assert 'asset_allocation_policy' not in request, 'Be doubly sure to prevent untrusted code execution'

        def set_delete(param):
            model_params[param] = request[param]
            del request[param]

        def set_low_high(param, value):
            model_params[param + '_low'] = model_params[param + '_high'] = value
            del model_params[param] # Should not be used. Make sure.

        set_delete('sex')
        set_delete('life_expectancy_additional')
        set_delete('gamma')

        try:
            basis_fraction = request['p_taxable_stocks_basis'] / request['p_taxable_stocks']
        except ZeroDivisionError:
            basis_fraction = 0
        set_low_high('p_taxable_stocks_basis_fraction', basis_fraction)
        del request['p_taxable_stocks_basis']

        for param in ('age_start', 'p_tax_free', 'p_tax_deferred', 'p_taxable_stocks'):
            set_low_high(param, request[param])
            del request[param]

        for param in (
            'age_start2',
            'gi_real', 'gi_real2', 'gi_real_couple', 'gi_nominal', 'gi_nominal2', 'gi_nominal_couple',
            'p_taxable_real_bonds', 'p_taxable_iid_bonds', 'p_taxable_bills'):
            set_low_high(param, 0)

        set_low_high('p_taxable_nominal_bonds', request['p_taxable_bonds'])
        del request['p_taxable_bonds']

        for param, value in request.items():
            assert param in ('defined_benefits', 'retirement_age', ), 'Unexpected parameter: ' + param

        model_params['display_returns'] = False;

        try:
            bonds = self.bonds_cache.pop()
        except:
            bonds = BondsSet()

        try:

            seed = args.seed + 1000000 # Use a different seed than might have been used during training.
            set_global_seeds(seed)
            env = FinEnv(bonds_cached = bonds, action_space_unbounded = True, direct_action = False,  **model_params)
            obs = env.reset()

            with U.make_session(num_cpu=1) as session:
                tf.saved_model.loader.load(session, [tf.saved_model.tag_constants.SERVING], model_dir)
                g = tf.get_default_graph()
                observation_tf = g.get_tensor_by_name('pi/ob:0')
                action_tf = g.get_tensor_by_name('pi/action:0')
                v_tf = g.get_tensor_by_name('pi/v:0')
                action, = session.run(action_tf, feed_dict = {observation_tf: [obs]})
                decoded_action = env.decode_action(action)
                policified_action = policy(env, decoded_action)
                consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = policified_action
                p_tax_free, p_tax_deferred, p_taxable, consume, taxes_paid, real_spias_purchase, nominal_spias_purchase = \
                    env.spend(consume_fraction, real_spias_fraction, nominal_spias_fraction)

                print('Consume: ', consume / env.params.time_period)
                print('Asset allocation: ', asset_allocation)
                print('Real immediate annuities purchase: ', real_spias_purchase if env.params.real_spias else None)
                print('Nominal immediate annuities purchase: ', nominal_spias_purchase if env.params.nominal_spias else None)
                print('Real bonds duration: ', real_bonds_duration)
                print('Nominal bonds duration: ', nominal_bonds_duration)

                render = False
                evaluator = Evaluator(env, seed, args.num_timesteps, render)

                def pi(obs):
                    action, = session.run(action_tf, feed_dict = {observation_tf: [obs]})
                    return action

                evaluator.evaluate(pi)

        finally:
            self.bonds_cache.append(bonds)

        return {
            'consume': consume / env.params.time_period,
            'asset_allocation': str(asset_allocation),
            'data_dir': '/api/data/dir1',
        }
        
def main():
    global args

    parser = ArgumentParser()
    parser.add_argument('--seed', type = int, default = 0)
    parser.add_argument('--num-timesteps', type = int, default = 10000)
    parser.add_argument('--master-model-dir', default = './')
    args = parser.parse_args()
    logger.configure()
    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.serve_forever()

if __name__ == '__main__':
    main()
