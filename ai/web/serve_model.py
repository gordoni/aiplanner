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
from http.server import HTTPServer, BaseHTTPRequestHandler
from json import dumps, loads
from os import chmod, mkdir
from socketserver import ThreadingMixIn
from subprocess import Popen
from tempfile import mkdtemp

from gym_fin.envs.model_params import dump_params_file

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

            result = self.run_models(request)

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

    def run_models(self, request):

        try:
            mkdir(data_root)
        except FileExistsError:
            pass
        dir = mkdtemp(prefix='', dir=data_root)
        chmod(dir, 0o775)

        dump_params_file(dir + '/aiplanner-request.txt', request, prefix = '')

        request_params = dict(request)
        request_params['defined_benefits'] = dumps(request_params['defined_benefits'])
        try:
            request_params['p_taxable_stocks_basis_fraction'] = request_params['p_taxable_stocks_basis'] / request_params['p_taxable_stocks']
        except ZeroDivisionError:
            request_params['p_taxable_stocks_basis_fraction'] = 0
        del request_params['p_taxable_stocks_basis']
        request_params['income_preretirement_age_end'] = request_params['age_retirement']
        for param in ('p_taxable_real_bonds', 'p_taxable_iid_bonds', 'p_taxable_bills'):
            request_params[param] = 0
        request_params['p_taxable_nominal_bonds'] = request_params['p_taxable_bonds']
        del request_params['p_taxable_bonds']
        request_params['display_returns'] = False

        dump_params_file(dir + '/aiplanner-scenario-request.txt', request_params)

        processes = []
        dir_seeds = []
        for model_seed in range(args.num_models):
            dir_seed = dir + '/' + str(model_seed)
            processes.append(self.run_model(request, model_seed, dir, dir_seed))
            dir_seeds.append(dir_seed)

        for process in processes:
              process.wait()

        best_ce = float('-inf')
        for dir_seed in dir_seeds:

            final = loads(open(dir_seed + '/aiplanner-final.json').read())

            if final['error']:
                return final

            initial = loads(open(dir_seed + '/aiplanner-initial.json').read())

            results = dict(initial, **final)
            results['data_dir'] = '/api/data/' + dir_seed[len(data_root) + 1:]

            if results['ce'] > best_ce:
                best_ce = results['ce']
                best_results = results

        return best_results

    def run_model(self, request, model_seed, dir, dir_seed):

        mkdir(dir_seed)
        chmod(dir_seed, 0o775)

        unit = 'single' if request['sex2'] == None else 'couple'
        suffix = '' if args.modelset_suffix == None else '-' + args.modelset_suffix
        model_dir = args.modelset_dir + 'aiplanner.' + unit + suffix + '-seed_' + str(model_seed) + '.tf'
        model_params = loads(open(model_dir + '/assets.extra/params.json').read())

        dump_params_file(dir_seed + '/aiplanner-scenario-model.txt', model_params)

        return Popen(('./eval_model',
            '--model-dir', model_dir,
            '-c', dir_seed + '/aiplanner-scenario-model.txt',
            '-c', dir + '/aiplanner-scenario-request.txt',
            '--result-dir', dir_seed,
            '--eval-seed', str(args.eval_seed),
            '--eval-num-timesteps', str(args.eval_num_timesteps),
            '--num-trace-episodes', str(args.num_trace_episodes),
            '--num-environments', str(args.num_environments),
            '--pdf-buckets', str(args.pdf_buckets),
        ))

def main():
    global args

    parser = ArgumentParser()
    parser.add_argument('--eval-seed', type = int, default = 0)
    parser.add_argument('--eval-num-timesteps', type = int, default = 50000)
    parser.add_argument('--modelset-dir', default = './')
    parser.add_argument('--modelset-suffix')
    parser.add_argument('--num-models', type = int, default = 10)
    parser.add_argument('--num-trace-episodes', type = int, default = 5)
    parser.add_argument('--num-environments', type = int, default = 10) # Number of parallel environments to use for a single model. Speeds up tensor flow.
    parser.add_argument('--pdf-buckets', type = int, default = 20) # Number of non de minus buckets to use in computing consume probability density distribution.
    args = parser.parse_args()
    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.serve_forever()

if __name__ == '__main__':
    main()
