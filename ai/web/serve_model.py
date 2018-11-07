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
from os import chmod, listdir, makedirs, remove, scandir
from os.path import isdir
from re import match
from socketserver import ThreadingMixIn
from subprocess import PIPE, Popen
from tempfile import mkdtemp
from threading import BoundedSemaphore
from time import sleep
from traceback import print_tb

from gym_fin.envs.model_params import dump_params_file, load_params_file

host = 'localhost'
port = 3000

data_root = '/tmp/aiplanner-data'

results_dir = data_root + '/results'
run_queue = data_root + '/runq'

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):

    pass

class RequestHandler(BaseHTTPRequestHandler):

    def do_POST(self):

        if self.path in ('/api/scenario', '/api/result', '/api/full'):

            content_type = self.headers.get('Content-Type')
            content_length = int(self.headers['Content-Length'])
            data = self.rfile.read(content_length)
            json_data = data.decode('utf-8')
            request = loads(json_data)

            if self.path == '/api/scenario':
                result = self.run_models_with_lock(request)
            elif self.path == '/api/result':
                result = self.get_results(request)
            elif self.path == '/api/full':
                result = self.run_full(request)
            else:
                assert False

            if result:

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
                    path = results_dir + '/' + asset
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

    run_lock = BoundedSemaphore(1) # For load management; there are no known concurrency problems.

    def run_models_with_lock(self, request):

        if self.run_lock.acquire(timeout = 60):
            # Development client resubmits request after 120 seconds, so keep timeout plus evaluation time below that.
            try:
                dir = self.save_params(request)
                model_prefix = self.get_model_prefix(dir)
                eval_models('prelim', model_prefix, dir)
                return {'id': dir[len(results_dir) + 1:]}
            finally:
                self.run_lock.release()
        else:
            self.send_error(503, 'Overloaded: try again later')

    def save_params(self, request):

        dir = mkdtemp(prefix = '', dir = results_dir)
        chmod(dir, 0o755)

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
        request_params['nominal_spias'] = request_params['spias']
        del request_params['spias']
        request_params['consume_clip'] = 0
        request_params['consume_income_ratio_max'] = float('inf')
        request_params['display_returns'] = False

        dump_params_file(dir + '/aiplanner-scenario.txt', request_params)

        return dir

    def get_model_prefix(self, dir):

        request = load_params_file(dir + '/aiplanner-request.txt', prefix = '')

        unit = 'single' if request['sex2'] == None else 'couple'
        spias = 'spias' if request['spias'] else 'no_spias'
        suffix = '' if args.modelset_suffix == None else '-' + args.modelset_suffix
        model_prefix = args.modelset_dir + 'aiplanner.' + unit + '-' + spias + suffix

        return model_prefix

    def get_results(self, request):

        id = request['id']
        assert match('[A-Za-z0-9_]+$', id)
        mode = request['mode']
        assert mode in ('prelim', 'full')

        dir = results_dir + '/' + id + '/' + mode

        best_ce = float('-inf')
        model_seed = 0
        while True:

            dir_seed = dir + '/' + str(model_seed)

            if not isdir(dir_seed):
                break

            try:
                final = loads(open(dir_seed + '/aiplanner-final.json').read())
            except IOError:
                return {'error': 'Results not found.'}

            if final['error'] != None:
                return final

            initial = loads(open(dir_seed + '/aiplanner-initial.json').read())

            results = dict(initial, **final)
            results['data_dir'] = '/api/data/' + dir_seed[len(results_dir) + 1:]

            if results['ce'] > best_ce:
                best_ce = results['ce']
                best_results = results

            model_seed += 1

        if model_seed == 0:
            return {'error': 'Results not found.'}
        else:
            return best_results

    def run_full(self, request):

        email = request['email']
        assert match('[^\s]+@[^\s]+$', email)
        name = request['name']
        assert match('.*$', name)
        id = request['id']
        assert match('[A-Za-z0-9_]+$', id)

        dir = results_dir + '/' + id
        dump_params_file(dir + '/aiplanner-request-full.txt', request, prefix = '')

        open(run_queue + '/' + id, 'w')
        #symlink('../' + id, run_queue + '/' + id)

        run_queue_length = len(listdir(run_queue))

        return {'run_queue_length': run_queue_length}

def eval_models(mode, model_prefix, dir):

    processes = []
    for model_seed in range(args.num_models):
        processes.append(eval_model(mode, model_prefix, dir, model_seed))

    fail = False
    for process in processes:
        if process.wait() != 0:
            fail = True

    if fail:
        raise Exception('Model evaluation failed mode ' + mode + ': ' + dir)

def train_eval_models(dir):

    dir_model = dir + '/models'
    model_prefix = dir_model + '/aiplanner'

    makedirs(dir_model, exist_ok = True)

    unit = get_family_unit(dir)
    num_timesteps = str(args.train_single_num_timesteps) if unit == 'single' else str(args.train_couple_num_timesteps)

    processes = []
    for model_seed in range(args.num_models):
        processes.append(train_model(model_prefix, dir, model_seed, num_timesteps))

    fail = False
    for process in processes:
        if process.wait() != 0:
            fail = True

    if fail:
        raise Exception('Model training failed: ' + dir)

    mode = 'full'
    eval_models(mode, model_prefix, dir)

def get_family_unit(dir):

    request = load_params_file(dir + '/aiplanner-request.txt', prefix = '')

    unit = 'single' if request['sex2'] == None else 'couple'

    return unit

def eval_model(mode, model_prefix, dir, model_seed):

    model_dir = model_prefix + '-seed_' + str(model_seed) + '.tf'
    dir_seed = dir + '/' + mode + '/' + str(model_seed)

    makedirs(dir_seed, exist_ok = True)

    num_timesteps = str(args.eval_prelim_num_timesteps) if mode == 'prelim' else str(args.eval_full_num_timesteps)

    return Popen(('./eval_model',
        '--result-dir', dir_seed,
        '--model-dir', model_dir,
        '-c', model_dir + '/assets.extra/params.txt',
        '-c', '../market_data.txt',
        '-c', dir + '/aiplanner-scenario.txt',
        '--eval-num-timesteps', num_timesteps,
        '--num-trace-episodes', str(args.num_trace_episodes),
        '--num-environments', str(args.num_environments),
        '--pdf-buckets', str(args.pdf_buckets),
    ))

def train_model(model_prefix, dir, model_seed, num_timesteps):

    model_dir = model_prefix + '-seed_' + str(model_seed) + '.tf'

    return Popen(('./train_model',
        '--model-dir', model_dir,
        '-c', '../aiplanner-scenario.txt',
        '-c', '../market_data.txt',
        '-c', dir + '/aiplanner-scenario.txt',
        '--train-seed', str(model_seed),
        '--train-num-timesteps', num_timesteps,
    ))

class RunQueueServer(object):

    def serve_forever(self):

        while True:
            try:
                oldest_id = None
                oldest_age = float('inf')
                with scandir(run_queue) as iter:
                    for entry in iter:
                        age = entry.stat(follow_symlinks = False).st_mtime
                        if age < oldest_age:
                            oldest_id = entry.name
                            oldest_age = age
                if oldest_id:
                    try:
                        self.serve_one(oldest_id)
                    finally:
                        remove(run_queue + '/' + oldest_id)
                else:
                    sleep(10)
            except Exception as e:
                print('----------------------------------------')
                print_tb(e.__traceback__)
                print(e.__class__.__name__ + ': ' + str(e))
                print('----------------------------------------')
                sleep(10)

    def serve_one(self, id):

        dir = results_dir + '/' + id
        request = load_params_file(dir + '/aiplanner-request-full.txt', prefix = '')
        email = request['email']
        name = request['name']

        try:
            dir = results_dir + '/' + id
            train_eval_models(dir)
            self.notify(email, name, id, True)
        except Exception as e:
            self.notify(email, name, id, False)
            raise e

    def notify(self, email, name, id, success):

        cmd = ['/usr/sbin/sendmail',
            '-f', 'root',
            email,
        ]
        if not success:
            cmd.append(args.admin_email)
        mta = Popen(cmd, stdin = PIPE, encoding = 'utf-8')

        header = 'From: "' + args.notify_name + '" <' + args.notify_email + '''>
To: ''' + email + '''
Subject: ''' + args.project_name + ': ' + name + '''

'''

        if success:
            body = 'Your requested ' + args.project_name + ' results are now available at ' + args.base_url + 'result/' + id + '''

Thank you for using ''' + args.project_name + '''.
'''
        else:
            body = 'Something went wrong computing your ' + args.project_name + ''' results. We are looking into the problem.

JobRef: ''' + id + '''
'''

        mta.stdin.write(header + body)
        mta.stdin.close()

        assert mta.wait() == 0

def main():
    global args

    parser = ArgumentParser()
    parser.add_argument('--serve', default='http', choices=('http', 'runq'))
    parser.add_argument('--modelset-dir', default = './')
    parser.add_argument('--modelset-suffix')
    parser.add_argument('--notify-email', default = 'notify@aiplanner.com')
    parser.add_argument('--notify-name', default = 'AIPlanner')
    parser.add_argument('--admin-email', default = 'admin@aiplanner.com')
    parser.add_argument('--project-name', default = 'AIPlanner')
    parser.add_argument('--base-url', default = 'https://www.aiplanner.com/')
    parser.add_argument('--eval-prelim-num-timesteps', type = int, default = 20000)
    parser.add_argument('--eval-full-num-timesteps', type = int, default = 2000000)
    parser.add_argument('--train-single-num-timesteps', type = int, default = 1000000)
    parser.add_argument('--train-couple-num-timesteps', type = int, default = 2000000)
    parser.add_argument('--num-models', type = int, default = 10)
    parser.add_argument('--num-trace-episodes', type = int, default = 5)
    parser.add_argument('--num-environments', type = int, default = 10) # Number of parallel environments to use for a single model evaluation. Speeds up tensor flow.
    parser.add_argument('--pdf-buckets', type = int, default = 20) # Number of non de minus buckets to use in computing consume probability density distribution.
    args = parser.parse_args()

    makedirs(results_dir, exist_ok = True)
    makedirs(run_queue, exist_ok = True)

    if args.serve == 'http':
        server = ThreadingHTTPServer((host, port), RequestHandler)
    else:
        server = RunQueueServer()
    server.serve_forever()

if __name__ == '__main__':
    main()
