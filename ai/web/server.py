#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from argparse import ArgumentParser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from json import dumps, loads
from os import chmod, environ, listdir, makedirs, remove, scandir, stat, statvfs
from os.path import expanduser, isdir
from re import match
from shutil import copyfile, move, rmtree
from socketserver import ThreadingMixIn
from statistics import stdev
from subprocess import PIPE, Popen
from tempfile import mkdtemp, mkstemp
from threading import BoundedSemaphore, Lock, Thread
from time import sleep, time
from traceback import print_tb

from gym_fin.envs.model_params import dump_params_file, load_params_file

from spia import YieldCurve

class AttributeObject(object):

    def __init__(self, dict):
        self.__dict__.update(dict)

class ApiHTTPServer(ThreadingMixIn, HTTPServer):

    def __init__(self, args):

        super().__init__((args.host, args.port), RequestHandler)
        self.args = args
        self.run_lock = BoundedSemaphore(self.args.num_concurrent_jobs)

class RequestHandler(BaseHTTPRequestHandler):

    def send_result(self, result_bytes, mime_type):

        self.send_response(200)
        self.send_header('Content-Type', mime_type)
        self.send_header('Content-Length', len(result_bytes))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(result_bytes)

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
                self.send_result(result_bytes, 'application/json')

            return

        self.send_error(404)

    def do_GET(self):

        if self.path == '/healthcheck':

            if self.healthcheck():
                data = 'OK\n'
            else:
                data = 'FAIL\n'

            data = data.encode('utf-8')
            self.send_result(data, 'text/plain')
            return

        elif self.path.startswith('/api/data/'):

            asset = self.path[len('/api/data/'):];
            if '..' not in asset:
                if asset.endswith('.png'):
                    filetype = 'image/png'
                elif asset.endswith('.svg'):
                    filetype = 'image/svg+xml'
                else:
                    filetype = None
                if filetype:
                    path = self.server.args.results_dir + '/' + asset
                    try:
                        data = open(path, 'rb').read()
                    except IOError:
                        pass
                    else:
                        self.send_result(data, filetype)
                        return

        elif self.path == '/api/market':

            result_bytes = dumps(self.market()).encode('utf-8')
            self.send_result(result_bytes, 'application/json')
            return

        self.send_error(404)

    def healthcheck(self):

        myargs = dict(
            vars(self.server.args),
            num_models = 1,
            eval_prelim_num_timesteps = 2000,
            train_num_timesteps = 2000,
            eval_full_num_timesteps = 2000,
        )
        args = AttributeObject(myargs)

        request = {
            'sex2': None,
            'spias': True,
        }
        result = self.run_models(request, args, prefix = 'healthcheck-')
        id = result['id']
        request = {
            'id': id,
            'mode': 'prelim',
        }
        results = self.get_results(request)

        assert 40000 < results['ce'] < 50000
            # Generically trained model continues past age 100 and doesn't allow for SPIAs past 85. Hence it delivers a worse CE than self trained model below.

        dir = self.server.args.results_dir + '/' + id
        model_runner = ModelRunner(dir, args)
        model_runner.train_eval_models('Healthcheck Results')
        request = {
            'id': id,
            'mode': 'full',
        }
        results = self.get_results(request)

        assert 45000 < results['ce'] < 50000

        return True

    def market(self):

        now = datetime.utcnow().date().isoformat()
        real_short_rate = YieldCurve('real', now, permit_stale_days = 7).spot(0)
        nominal_short_rate = YieldCurve('nominal', now, permit_stale_days = 7).spot(0)

        return {
            'stocks_price': self.server.args.stocks_price,
            'real_short_rate': real_short_rate,
            'nominal_short_rate': nominal_short_rate,
        }

    def run_models_with_lock(self, request):

        if self.server.run_lock.acquire(timeout = 60):
            # Development client resubmits request after 120 seconds, so keep timeout plus evaluation time below that.
            try:
                return self.run_models(request, self.server.args)
            finally:
                self.server.run_lock.release()
        else:
            self.send_error(503, 'Overloaded: try again later')

    def run_models(self, request, args, prefix = ''):

        dir = self.save_request(request, prefix = prefix)
        if prefix == 'healthcheck-':
            copyfile('healthcheck-scenario.txt', dir + '/aiplanner-scenario.txt')
        else:
            self.save_scenario(dir, request)
        model_prefix = self.get_model_prefix(dir)
        model_runner = ModelRunner(dir, args)
        model_runner.eval_models('prelim', model_prefix)

        return {'id': dir[len(args.results_dir) + 1:]}

    def save_request(self, request, prefix = ''):

        dir = mkdtemp(prefix = prefix, dir = self.server.args.results_dir)
        chmod(dir, 0o755)

        dump_params_file(dir + '/aiplanner-request.txt', request, prefix = '')

        return dir

    def save_scenario(self, dir, request):

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
        request_params['consume_income_ratio_max'] = float('inf')
        request_params['display_returns'] = False

        dump_params_file(dir + '/aiplanner-scenario.txt', request_params)

    def get_model_prefix(self, dir):

        request = load_params_file(dir + '/aiplanner-request.txt', prefix = '')

        unit = 'single' if request['sex2'] == None else 'couple'
        spias = 'spias' if request['spias'] else 'no_spias'
        gamma = 'gamma' + str(request['gamma'])
        suffix = '' if self.server.args.modelset_suffix == None else '-' + self.server.args.modelset_suffix
        model_prefix = expanduser(self.server.args.modelset_dir) + '/aiplanner.' + unit + '-' + spias + '-' + gamma + suffix

        return model_prefix

    def get_results(self, request):

        id = request['id']
        assert match('[A-Za-z0-9_-]+$', id)
        mode = request['mode']
        assert mode in ('prelim', 'full')

        dir = self.server.args.results_dir + '/' + id + '/' + mode

        ces = []
        best_ce = float('-inf')
        for model_seed in range(self.server.args.num_models):

            dir_seed = dir + '/' + str(model_seed)

            try:
                final = loads(open(dir_seed + '/aiplanner-final.json').read())
            except IOError:
                continue

            if final['error'] != None:
                continue

            try:
                initial = loads(open(dir_seed + '/aiplanner-initial.json').read())
            except IOError:
                continue

            results = dict(initial, **final)
            results['data_dir'] = '/api/data/' + dir_seed[len(self.server.args.results_dir) + 1:]

            ce = results['ce']
            ces.append(ce)
            if ce > best_ce:
                best_ce = ce
                best_results = results

        if not ces:
            results = {'error': 'Results not found.'}
        else:
            results = dict(
                best_results,
                model_count = len(ces),
                models_stdev = 0 if len(ces) == 1 else stdev(ces),
            )

        return results

    def run_full(self, request):

        email = request['email']
        assert match('[^\s]+@[^\s]+$', email)
        name = request['name']
        assert match('.*$', name)
        id = request['id']
        assert match('[A-Za-z0-9_-]+$', id)

        dir = self.server.args.results_dir + '/' + id
        dump_params_file(dir + '/aiplanner-request-full.txt', request, prefix = '')

        open(self.server.args.run_queue + '/' + id, 'w')
        #symlink('../' + id, self.server.args.run_queue + '/' + id)

        run_queue_length = len(listdir(self.server.args.run_queue))

        return {'run_queue_length': run_queue_length}

class ModelRunner(object):

    def __init__(self, dir, args, priority = 0):

        self.dir = dir
        self.args = args
        self.priority = priority

    def eval_models(self, mode, model_prefix):

        processes = []
        for model_seed in range(self.args.num_models):
            processes.append(self.eval_model(mode, model_prefix, model_seed))

        fail = False
        for process in processes:
            if process.wait() != 0:
                fail = True

        if fail:
            raise Exception('Model evaluation failed mode ' + mode + ': ' + self.dir)

    def train_eval_models(self, name):

        dir_model = self.dir + '/models'
        model_prefix = dir_model + '/aiplanner'

        makedirs(dir_model, exist_ok = True)

        processes = []
        for model_seed in range(self.args.num_models):
            model_dir = model_prefix + '-seed_' + str(model_seed) + '.tf'
            processes.append(self.train_model(name, model_dir, model_seed))

        fail = False
        for process, temp_name in processes:
            if process.wait() != 0:
                fail = True
            makedirs(model_dir, exist_ok = True)
            move(temp_name, model_dir + '/train.log')

        if fail:
            raise Exception('Model training failed: ' + self.dir)

        mode = 'full'
        self.eval_models(mode, model_prefix)

    def eval_model(self, mode, model_prefix, model_seed):

        model_dir = model_prefix + '-seed_' + str(model_seed) + '.tf'
        dir_seed = self.dir + '/' + mode + '/' + str(model_seed)

        makedirs(dir_seed, exist_ok = True)

        num_timesteps = str(self.args.eval_prelim_num_timesteps) if mode == 'prelim' else str(self.args.eval_full_num_timesteps)

        eval_log = open(dir_seed + '/eval.log', 'w')
        return Popen((environ['AIPLANNER_HOME'] + '/ai/eval_model.py',
            '--result-dir', dir_seed,
            '--model-dir', model_dir,
            '--nice', str(self.priority),
            '-c', model_dir + '/params.txt',
            '-c', self.dir + '/aiplanner-scenario.txt',
            '--master-consume-clip', '0',
            '--eval-num-timesteps', num_timesteps,
            '--num-trace-episodes', str(self.args.num_trace_episodes),
            '--num-environments', str(self.args.num_environments),
            '--pdf-buckets', str(self.args.pdf_buckets),
        ), stdout = eval_log, stderr = eval_log)

    def train_model(self, name, model_dir, model_seed):

        temp, temp_name = mkstemp(prefix = 'train')
        process = Popen((environ['AIPLANNER_HOME'] + '/ai/train_ppo1.py',
            '--model-dir', model_dir,
            '--nice', str(self.priority),
            '-c', '../aiplanner-scenario.txt',
            '-c', self.dir + '/aiplanner-scenario.txt',
            '--master-name', name,
            '--train-seed', str(model_seed),
            '--train-num-timesteps', str(self.args.train_num_timesteps),
        ), stdout = temp, stderr = temp)

        return process, temp_name

class RunQueueServer(object):

    def __init__(self, args):

        self.args = args

        self.run_queue_lock = Lock()
        self.output_lock = Lock()

        self.running = {}

    def report_exception(self, e):

        self.output_lock.acquire()
        print('----------------------------------------')
        print_tb(e.__traceback__)
        print(e.__class__.__name__ + ': ' + str(e))
        print('----------------------------------------')
        self.output_lock.release()

    def serve_forever(self):

        prev_pending = None
        while True:
            try:
                run_queue_length = 0
                oldest_id = None
                oldest_age = float('inf')
                self.run_queue_lock.acquire()
                with scandir(self.args.run_queue) as iter:
                    for entry in iter:
                        run_queue_length += 1
                        if len(self.running) < self.args.num_concurrent_jobs:
                            age = entry.stat(follow_symlinks = False).st_mtime
                            if age < oldest_age and entry.name not in self.running:
                                oldest_id = entry.name
                                oldest_age = age
                self.run_queue_lock.release()
                if oldest_id:
                    id = oldest_id
                    thread = Thread(target = self.serve_thread, args = (id, ))
                    self.log('Starting', id)
                    self.running[id] = thread
                    thread.start()
                else:
                    pending = max(0, run_queue_length - len(self.running))
                    if pending != prev_pending:
                        prev_pending = pending
                        if pending > 0:
                            self.log('Jobs pending', pending)
                    sleep(10)
            except Exception as e:
                self.report_exception(e)
                sleep(10)

    def log(self, *args):

        self.output_lock.acquire()
        print(datetime.now().replace(microsecond = 0).isoformat(), *args)
        self.output_lock.release()

    def serve_thread(self, id):

        try:
            self.serve_one(id)
            self.log('Completed', id)
        except Exception as e:
            self.report_exception(e)
            self.log('Failed', id)
        finally:
            try:
                self.run_queue_lock.acquire()
                remove(self.args.run_queue + '/' + id)
                del self.running[id]
            except Exception as e:
                self.report_exception(e)
                pass
            finally:
                self.run_queue_lock.release()

    def serve_one(self, id):

        dir = self.args.results_dir + '/' + id
        request = load_params_file(dir + '/aiplanner-request-full.txt', prefix = '')
        email = request['email']
        name = request['name']

        try:
            dir = self.args.results_dir + '/' + id
            model_runner = ModelRunner(dir, self.args, priority = 10)
            model_runner.train_eval_models(name)
            self.notify(email, name, id, True)
        except Exception as e:
            self.notify(email, name, id, False)
            raise e

    def notify(self, email, name, id, success):

        if not email:
            return

        cmd = ['/usr/sbin/sendmail',
            '-f', 'root',
            email,
        ]
        if not success:
            cmd.append(self.args.admin_email)
        mta = Popen(cmd, stdin = PIPE, encoding = 'utf-8')

        header = 'From: "' + self.args.notify_name + '" <' + self.args.notify_email + '''>
To: ''' + email + '''
Subject: ''' + self.args.project_name + ': ' + name + '''

'''

        if success:
            body = 'Your requested ' + self.args.project_name + ' results are now available at ' + self.args.base_url + 'result/' + id + '''

Thank you for using ''' + self.args.project_name + '''.
'''
        else:
            body = 'Something went wrong computing your ' + self.args.project_name + ''' results. We are looking into the problem.

JobRef: ''' + id + '''
'''

        mta.stdin.write(header + body)
        mta.stdin.close()

        assert mta.wait() == 0

class PurgeQueueServer(object):

    def __init__(self, args):

        self.args = args

    def report_exception(self, e):

        print('----------------------------------------')
        print_tb(e.__traceback__)
        print(e.__class__.__name__ + ': ' + str(e))
        print('----------------------------------------')

    def serve_forever(self):

        while True:
            try:
                self.purgeq()
                sleep(self.args.purge_frequency)
            except Exception as e:
                self.report_exception(e)
                sleep(10)

    def purgeq(self):

        entries = list(scandir(self.args.results_dir))
        entries.sort(key = lambda entry: entry.stat(follow_symlinks = False).st_mtime)

        for entry in entries:

            age = time() - entry.stat(follow_symlinks = False).st_mtime

            if age <= self.args.purge_keep_time:
                break

            dir = self.args.results_dir + '/' + entry.name
            s = statvfs(self.args.results_dir)
            free = float(s.f_bavail) / s.f_blocks
            ifree = float(s.f_favail) / s.f_files

            if entry.name.startswith('healthcheck-'):
                purge_time = self.args.purge_time_healthcheck
            else:
                try:
                    stat(dir + '/models')
                    purge_time = self.args.purge_time_full
                except IOError:
                    purge_time = self.args.purge_time_prelim

            if free < self.args.purge_keep_free or ifree < self.args.purge_keep_free or age >= purge_time:
                def rmfail(function, path, excinfo):
                    print('Error purging file:', path)
                rmtree(dir, onerror = rmfail)

def main():

    parser = ArgumentParser()

    # Generic options.
    parser.add_argument('--serve', action = 'append', default = [], choices=('http', 'runq', 'purgeq'))
    parser.add_argument('--root-dir', default = '~/aiplanner-data')
    parser.add_argument('--num-concurrent-jobs', type = int, default = 1) # Each job represents the concurrent execution of num_models models in a single scenario.
    parser.add_argument('--num-models', type = int, default = 10)
    parser.add_argument('--num-trace-episodes', type = int, default = 5) # Number of sample traces to generate.
    parser.add_argument('--num-environments', type = int, default = 10) # Number of parallel environments to use for a single model evaluation. Speeds up tensor flow.
    parser.add_argument('--pdf-buckets', type = int, default = 20) # Number of non de minus buckets to use in computing consume probability density distribution.

    # HTTP options.
    parser.add_argument('--host', default = 'localhost')
    parser.add_argument('--port', type = int, default = 3000)
    parser.add_argument('--stocks-price', type = float, default = 1)
    parser.add_argument('--modelset-dir', default = '~/aiplanner-data/models')
    parser.add_argument('--modelset-suffix')
    parser.add_argument('--eval-prelim-num-timesteps', type = int, default = 20000)

    # runq options.
    parser.add_argument('--notify-email', default = 'notify@aiplanner.com')
    parser.add_argument('--notify-name', default = 'AIPlanner')
    parser.add_argument('--admin-email', default = 'admin@aiplanner.com')
    parser.add_argument('--project-name', default = 'AIPlanner')
    parser.add_argument('--base-url', default = 'https://www.aiplanner.com/')
    parser.add_argument('--train-num-timesteps', type = int, default = 10000000)
    parser.add_argument('--eval-full-num-timesteps', type = int, default = 2000000)

    # purgeq options.
    parser.add_argument('--purge-frequency', type = int, default = 3600) # Purge the run queue of old files every this many seconds.
    parser.add_argument('--purge-keep-free', type = float, default = 0.02) # Keep this much proportion of disk space/inodes free.
    parser.add_argument('--purge-keep-time', type = int, default = 3600) # Keep directories around for this long regardless.
    parser.add_argument('--purge-time-healthcheck', type = int, default = 3600) # Delete healthcheck scenarios after this long.
    parser.add_argument('--purge-time-prelim', type = int, default = 30 * 86400) # Delete prelim run only scenarios after this long.
    parser.add_argument('--purge-time-full', type = int, default = 365 * 86400) # Delete full run scenarios after this long.

    args = parser.parse_args()
    root_dir = expanduser(args.root_dir)
    args.results_dir = root_dir + '/results'
    args.run_queue = root_dir + '/runq'

    makedirs(args.results_dir, exist_ok = True)
    makedirs(args.run_queue, exist_ok = True)

    if not args.serve or 'http' in args.serve:
        server = ApiHTTPServer(args)
        Thread(target = server.serve_forever, daemon = True).start()

    if not args.serve or 'runq' in args.serve:
        server = RunQueueServer(args)
        Thread(target = server.serve_forever, daemon = True).start()

    if not args.serve or 'purgeq' in args.serve:
        server = PurgeQueueServer(args)
        Thread(target = server.serve_forever, daemon = True).start()

    try:
        while True:
            sleep(86400)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
