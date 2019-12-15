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
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import TextIOWrapper
from json import dumps, loads
from os.path import expanduser
from re import match
from signal import SIGHUP, signal
from socketserver import ThreadingMixIn
from subprocess import PIPE, Popen
from sys import stdout
from threading import Thread
from time import sleep
from traceback import print_exc

from yaml import safe_load

class ApiHTTPServer(ThreadingMixIn, HTTPServer):

    def __init__(self, args, logger):

        super().__init__((args.host, args.port), RequestHandler)
        self.args = args
        self.logger = logger

class Logger:

    def __init__(self, args):

        self.args = args

        self.restart()

    def restart(self):

       self.logfile_binary = open(self.args.root_dir + '/web.err', 'ab')
       self.logfile = TextIOWrapper(self.logfile_binary)
       self.info_logfile = open(self.args.root_dir + '/web.log', 'a')

    def log(self, *args):

        print(*args, file = self.logfile)
        self.logfile.flush()

    def log_binary(self, data):

        self.logfile_binary.write(data)
        self.logfile_binary.flush()

    def report_exception(self, e):

        print('----------------------------------------', file = self.logfile)
        print_exc(file = self.logfile)
        print('----------------------------------------', file = self.logfile)
        self.logfile.flush()

class RequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):

        print(self.log_date_time_string(), format % args, file = self.server.logger.info_logfile)
        self.server.logger.info_logfile.flush()

    def send_result(self, result_bytes, mime_type, headers = []):

        self.send_response(200)
        self.send_header('Content-Type', mime_type)
        self.send_header('Content-Length', len(result_bytes))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(result_bytes)

    def do_POST(self):

        try:

            if self.path.startswith('/web/'):

                content_type = self.headers.get('Content-Type')
                content_length = self.headers.get('Content-Length')
                if content_length == None:
                    self.send_error(411) # Length Required
                    return
                content_length = int(content_length)
                if not 0 <= content_length <= 100e6:
                    self.send_error(413) # Payload Too Large
                    return

                data = self.rfile.read(content_length)
                if self.server.args.verbose:
                    stdout.buffer.write(data + '\n'.encode('utf-8'))
                    stdout.flush()
                try:
                    request = loads(data.decode('utf-8'))
                except ValueError:
                    self.send_error(400) # Bad Request
                    return

                data = None
                headers = []
                if self.path == '/web/subscribe':

                    result = self.subscribe(request)
                    if result != None:
                        data = (dumps(result, indent = 4, sort_keys = True) + '\n').encode('utf-8')
                    else:
                        data = None

                else:

                    self.send_error(404) # Not Found
                    return

                if data != None:
                    if self.server.args.verbose:
                        stdout.buffer.write(data)
                        stdout.flush()
                    self.send_result(data, 'application/json', headers = headers)

                return

            self.send_error(404) # Not Found

        except Exception as e:

            self.server.logger.report_exception(e)
            self.send_error(500) # Internal Server Error

    def do_GET(self):

        try:

            data = None
            headers = []
            if self.path == '/web/healthcheck':

                if self.healthcheck():
                    data = 'OK\n'
                else:
                    data = 'FAIL\n'

                data, filetype = data.encode('utf-8'), 'text/plain'
                headers.append(('Cache-Control', 'no-cache'))

            if data != None:

                self.send_result(data, filetype, headers = headers)
                return

            self.send_error(404) # Not Found

        except Exception as e:

            self.server.logger.report_exception(e)
            self.send_error(500) # Internal Server Error

    def healthcheck(self):

        return True

    def subscribe(self, request):

        email = request.get('email', '')
        email = email.strip()
        if not match('^\S+@\S+\.\S+$', email):
            return {'error': 'Invalid email address.'}

        try:
            with open(self.server.args.root_dir + '/subscribe.txt', 'a') as f:
                f.write(email + '\n')
        except IOError:
            raise

        if not self.notify_admin('subscribe', email + ' has subscribed\n'):
            self.send_error(500) # Internal Server Error
            return

        return {
            'error': None,
            'result': None,
        }

    def notify_admin(self, subject, body):

        if self.server.args.admin_email:

            cmd = ['/usr/sbin/sendmail',
                '-f', 'root',
                self.server.args.admin_email,
            ]
            mta = Popen(cmd, stdin = PIPE, universal_newlines = True) # Python 3.5.
            #mta = Popen(cmd, stdin = PIPE, encoding = 'utf-8') # Python3.6+.

            header = 'From: "' + self.server.args.notify_name + '" <' + self.server.args.notify_email + '''>
To: ''' + self.server.args.admin_email + '''
Subject: ''' + self.server.args.project_name + ': ' + subject + '''

'''

            mta.stdin.write(header + body)
            mta.stdin.close()

            return mta.wait() == 0

        else:

            return True

def boolean_flag(parser, name, default = False):

    under_dest = name.replace('-', '_')
    parser.add_argument('--' + name, action = "store_true", default = default, dest = under_dest)
    parser.add_argument('--' + 'no-' + name, action = "store_false", dest = under_dest)

def main():

    root_dir = expanduser('~/aiplanner-data')

    try:
        f = open('/aiplanner.yaml')
    except OSError:
        try:
            f = open(root_dir + '/aiplanner.yaml')
        except OSError:
            f = None
    config = safe_load(f) if f else {}
    web_config = config.get('web', {})

    parser = ArgumentParser()

    # Generic options.
    parser.add_argument('--serve', action = 'append', default = [], choices=('http', ))
    parser.add_argument('--root-dir', default = root_dir)

    # HTTP server options.
    boolean_flag(parser, 'verbose', default = False)
    parser.add_argument('--host', default = web_config.get('host', 'localhost'))
    parser.add_argument('--port', type = int, default = web_config.get('port', 3001))

    # Email options.
    parser.add_argument('--notify-email', default = config.get('notify_email', 'notify@aiplanner.com'))
    parser.add_argument('--notify-name', default = config.get('notify_name', 'AIPlanner Notify'))
    parser.add_argument('--admin-email', default = config.get('admin_email'))
    parser.add_argument('--project-name', default = config.get('project_name', 'AIPlanner'))

    args = parser.parse_args()
    args.root_dir = expanduser(args.root_dir)

    logger = Logger(args)

    if not args.serve or 'http' in args.serve:
        api_server = ApiHTTPServer(args, logger)
        Thread(target = api_server.serve_forever, daemon = True).start()
    else:
        api_server = None

    def rotate_logs(signum, frame):
        logger.restart()

    signal(SIGHUP, rotate_logs)

    try:
        while True:
            sleep(86400)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
