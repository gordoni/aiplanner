# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2015 Gordon Irlam
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from csv import reader
from datetime import datetime
from decimal import Decimal
from django.contrib.auth import authenticate, login, models
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.forms.forms import NON_FIELD_ERRORS
from django.http import HttpResponseRedirect
from django.shortcuts import render
from email import message_from_string
from httplib import HTTPConnection, HTTPException
from json import dumps, loads
from os import chmod, environ, umask
from random import randint
from re import compile, MULTILINE
import socket # error
from stat import S_IRWXU
from subprocess import call, Popen
from tempfile import mkdtemp
from time import strptime

from aacalc.utils import asset_class_names, asset_class_symbols
from settings import OPAL_HOST, SECRET_KEY, STATIC_ROOT, STATIC_URL

# Deleted names can only be judicially re-used, since inactive users might still hold an old parameter of that name. This means types can never be changed.
default_params = {
    'calculator': 'aa',
    #'name': None,
    'sex': None,
    'dob': None,
    'sex2': None,
    'dob2': None,
    'advanced_position': False,
    'defined_benefit_social_security': Decimal(20000),
    'defined_benefit_pensions': Decimal(0),
    'defined_benefit_fixed_annuities': Decimal(0),
    'retirement_number': False,
    'p_traditional_iras': Decimal(0),
    'p_roth_iras': Decimal(0),
    'p': Decimal(0),
    'contribution': Decimal(10000),
    'contribution_growth_pct': Decimal(7),
    'tax_rate_cg_pct': Decimal(0),
    'tax_rate_div_default_pct': Decimal(0),
    'cost_basis_method': 'hifo',
    'advanced_goals': False,
    'retirement_year': None,
    'withdrawal': Decimal(50000),
    #'floor': Decimal(30000),
    'utility_join_required': Decimal(40000),
    'utility_join_desired': Decimal(20000),
    'risk_tolerance': Decimal(20),
    #'vw': True,
    'vw_amount': False,
    #'vw_withdrawal_low': Decimal(50000),
    #'vw_withdrawal_high': Decimal(100000),
    'advanced_market': False,
    'class_stocks': True,
    'class_bonds': True,
    #'class_cash': False,
    'class_eafe': False,
    'class_ff_bl': False,
    'class_ff_bm': False,
    'class_ff_bh': False,
    'class_ff_sl': False,
    'class_ff_sm': False,
    'class_ff_sh': False,
    'class_reits_e': False,
    'class_reits_m': False,
    'class_t1mo': False,
    'class_t1yr': False,
    'class_t10yr': False,
    'class_tips10yr': False,
    'class_aaa': False,
    'class_baa': False,
    'class_reits': False,
    'class_gold': False,
    'class_risk_free' : False,
    'ret_risk_free_pct': Decimal('1.0'),
    'generate_start_year': 1927,
    'generate_end_year': 2014,
    'validate_start_year': 1927,
    'validate_end_year': 2014,
    'ret_equity_pct': Decimal('5.0'),
    'ret_bonds_pct': Decimal('2.0'),
    'expense_pct': Decimal('0.5'),
    'neg_validate_all_adjust_pct': Decimal('0.0'),
    'validate_equity_vol_adjust_pct': Decimal(100),
    'inherit': False,
    #'inherit_years': Decimal(5),
    #'inherit_nominal': Decimal(250000),
    #'inherit_to_utility_pct': Decimal(20),
    'utility_inherit_years': Decimal(20),
    #'utility_eta': Decimal('1.5'),
    #'utility_cutoff': Decimal('0.5'),
    #'utility_slope_zero': Decimal(100),
    #'utility_donate': False,
    #'utility_donate_above': Decimal(50000),
    #'utility_dead_pct': Decimal(10),
    'utility_dead_limit_pct': Decimal(10),
    'utility_bequest_consume': Decimal(50000),
    #'donate_inherit_discount_rate_pct': Decimal(15),
    'advanced_well_being': False,
    'consume_discount_rate_pct': Decimal('1.5'),
    'upside_discount_rate_pct': Decimal('4.5'),
    #'public_assistance': Decimal(10000),
    #'public_assistance_phaseout_rate_pct': Decimal(50),
    'utility_method': 'floor_plus_upside',
    'utility_join_slope_ratio_pct': Decimal(10),
    'utility_eta_1': Decimal('4.0'),
    'utility_eta_2': Decimal('1.01'),
    'utility_ce': Decimal('1.26'),
    'utility_slope_double_withdrawal': Decimal(8),
    'utility_eta': Decimal('3.0'),
    'utility_alpha': Decimal('0.0001'),
}

resolution = 'medium'
if resolution == 'low':
    tp_zero_factor = 0.001
    scaling_factor = 1.05
    aa_steps = 50
    spend_steps = 5000
elif resolution == 'medium':
    tp_zero_factor = 0.0001
    scaling_factor = 1.05
    aa_steps = 1000
    spend_steps = 10000  # Some noise in withdrawal map, and possibly consumption paths.
else:
    tp_zero_factor = 0.00005
    scaling_factor = 1.02
    aa_steps = 1000
    spend_steps = 100000

def dob_to_age(dob_str_or_age):
    if dob_str_or_age == None:
        return None
    elif isinstance(dob_str_or_age, int):
        return dob_str_or_age
    now = datetime.utcnow().timetuple()
    dob = strptime(dob_str_or_age, '%Y-%m-%d')
    age = now.tm_year - dob.tm_year
    if now.tm_mon < dob.tm_mon or now.tm_mon == dob.tm_mon and now.tm_mday < dob.tm_mday:
          age -= 1
    return age

def run_http(request, scenario_dict):
    response = run_response(request, scenario_dict, False)
    return response

def run_response(request, scenario_dict, healthcheck):
    dirname = run_dirname(request, scenario_dict, healthcheck)
    return display_result(request, dirname, False, scenario_dict)

def run_dirname(request, scenario_dict, healthcheck):
    prefix = 'healthcheck-' if healthcheck else ''
    umask(0077)
    dirname = mkdtemp(prefix=prefix, dir=STATIC_ROOT + 'results')
    run_opal(dirname, scenario_dict)
    return dirname

def get_le(dirname):
    le_file = open(dirname + "/opal-le.csv")
    le_map = {}
    for line in reader(le_file):
        le_map[line[0]] = ['%.2f' % float(le) for le in line[1:]]
    return le_map['ssa-cohort'], le_map['iam2012-basic-period-aer2005_08'], le_map['ssa-period']

def sample_scenario_dict():
    s = dict(default_params)
    s['sex'] = 'male'
    s['sex2'] = 'female'
    s['dob'] = 55
    s['dob2'] = 55
    s['defined_benefit_social_security'] = Decimal(20000)
    s['p'] = Decimal(1000000)
    s['contribution'] = Decimal(30000)
    s['contribution_growth_pct'] = Decimal(7)
    s['tax_rate_cg_pct'] = Decimal(20)
    s['tax_rate_div_default_pct'] = Decimal(20)
    s['retirement_year'] = datetime.utcnow().timetuple().tm_year + 65 - 55
    s['utility_join_required'] = Decimal(60000)
    return s

def run_gen_sample():
    umask(0033)
    run_opal(STATIC_ROOT + 'sample', sample_scenario_dict())

def display_sample(request):
    return display_result(request, STATIC_ROOT + 'sample', True, sample_scenario_dict())

scheme_name = {
    'age_in_bonds': 'Age in bonds / 4% rule',
    'age_minus_10_in_bonds': 'Age minus 10 in bonds / 4% rule',
    'target_date': 'Target date / 4% rule',
}

def start_tp(s):
    return (1 - float(s['tax_rate_div_default_pct']) / 100) * float(s['p_traditional_iras']) + float(s['p_roth_iras']) + float(s['p'])

def db(s):
    return float(s['defined_benefit_social_security']) + float(s['defined_benefit_pensions']) + float(s['defined_benefit_fixed_annuities'])

def display_result(request, dirname, sample, s):
    data = dict(s)
    data['floor'] = floor(s)
    schemes = []
    if s['retirement_number']:
        f = open(dirname + '/opal-number.csv')
        best_fields = None
        for line in f.readlines():
            fields = line.split(',')
            _, probability, _, _ = fields
            if float(probability) > 0.05:
                break
            best_fields = fields
        if best_fields:
            number, failure_chance, failure_length, metric_withdrawal = best_fields
            data['number'] = int(float(number) / 10000) * 10000
            data['failure_chance'] = '%.1f%%' % (float(failure_chance) * 100)
            data['failure_length'] = '%.1f' % float(failure_length)
            data['metric_withdrawal'] = int(float(metric_withdrawal))
        else:
            data['number'] = '-'
            data['failure_chance'] = '-'
            data['failure_length'] = '-'
            data['metric_withdrawal'] = '-'
            metric_withdrawal = 0.0
    else:
        f = open(dirname + '/opal.log')
        log = f.read()
        data['retire'] = s['retirement_year'] <= datetime.utcnow().timetuple().tm_year
        consume_str = compile(r'^Consume: (\S+)$', MULTILINE).search(log).group(1)
        data['consume'] = int(float(consume_str))
        aa_str = compile(r'^Asset allocation: \[(.*)\]$', MULTILINE).search(log).group(1)
        aa_raw = tuple(float(a) for a in aa_str.split(', '))
        # Round aa, so that results aren't reported with more precision than is warranted.
        precise = False
        steps = aa_steps if precise else 20
        data['precision'] = 100 / steps
        aa = []
        remainder = 0.0
        for a_raw in aa_raw:
            a = round((a_raw + remainder) * steps) / steps
            remainder = a_raw - a
            aa.append(a)
        data['aa_name'] = '/'.join(asset_class_names(s))
        data['aa'] = '/'.join(str(int(a * 100 + 0.5)) for a in aa)
        failure_chance, failure_length = compile(r'^(\S+)% chance of failure; (\S+) years weighted failure length$', MULTILINE).search(log).groups()
        metric_tw = compile(r'^Metric tw: *(-?\d+.\d+).*$', MULTILINE).search(log).group(1)
        metric_withdrawal = compile(r'^Metric consume: *(-?\d+.\d+).*$', MULTILINE).search(log).group(1)
        data['failure_chance'] = '%.1f%%' % float(failure_chance)
        data['failure_length'] = '%.1f' % float(failure_length)
        data['metric_withdrawal'] = int(float(metric_withdrawal))
        re = compile(r'^Compare (\S+)/retirement_amount: (\S+)$')
        for line in log.splitlines():
            re_s = re.search(line)
            if re_s:
                scheme, ce = re_s.groups()
                if float(ce) > db(s):
                    improvement = (float(metric_withdrawal) - db(s)) / (float(ce) - db(s)) - 1
                    improvement = str(int(improvement * 100)) + '%'
                else:
                    improvement = '-'
                schemes.append({'name': scheme_name[scheme], 'ce': ce, 'improvement': improvement})
        if float(metric_tw) < 90:
            data['risk'] = 'high'
        elif float(metric_tw) < 99:
            data['risk'] = 'medium'
        else:
            data['risk'] = 'low'
    f.close()
    return render(request, 'scenario_result.html', {
        'sample': sample,
        'data': data,
        'aa_symbol_names': tuple({'symbol': symbol, 'name': name} for (symbol, name) in zip(asset_class_symbols(s), asset_class_names(s))),
        'schemes': schemes,
        'dirurl': dirname.replace(STATIC_ROOT, STATIC_URL),
    })

def stringize(v):
    if isinstance(v, tuple):
        return '(' + ', '.join(stringize(e) for e in v) + ')'
    if isinstance(v, basestring):
        # repr() puts an annoying "u" infront of unicode strings.
        return "'" + v.replace("'", r"\'") + "'"
    elif isinstance(v, Decimal):
        return str(v)
    else:
        return repr(v)

class OPALServerError(Exception):
    pass

class OPALServerOverloadedError(OPALServerError):
    pass

def floor(s):
    ref = (0.9 * float(s['withdrawal'])) if s['vw_amount'] else float(s['utility_join_required'])
    return int(ref)

def write_scenario(dirname, s):
    retirement_age = dob_to_age(s['dob']) + max(0, s['retirement_year'] - datetime.utcnow().timetuple().tm_year)
    # Caution: Config.java maintains values from previous runs, so all modified values must be updated each time.
    s_only = {
        'skip_generate': s['calculator'] == 'le',
        'skip_retirement_number': not s['retirement_number'],
        'skip_compare': s['calculator'] == 'le' or s['retirement_number'],
        'vw_percentage': 0.04,
        'skip_validate':  s['calculator'] == 'le' or s['retirement_number'],
        'tp_zero_factor': tp_zero_factor,
        'scaling_factor': scaling_factor,
        'search' : 'hill',
        'aa_steps': aa_steps,
        'asset_classes': asset_class_symbols(s),
        'asset_class_names': asset_class_names(s),
        'ef': 'mvo',
        'risk_tolerance': float(s['risk_tolerance']) / 100,
        'generate_start_year': s['generate_start_year'],
        'generate_end_year': s['generate_end_year'],
        'target_start_year': s['validate_start_year'],
        'target_end_year': s['validate_end_year'],
        'validate_start_year': s['validate_start_year'],
        'validate_end_year': s['validate_end_year'],
        'success_mode': 'combined',
        'sex': s['sex'],
        'start_age': retirement_age if s['retirement_number'] else dob_to_age(s['dob']),
        'validate_age': retirement_age if s['retirement_number'] else dob_to_age(s['dob']),
        'utility_age': retirement_age,
        'sex2': s['sex2'],
        'start_age2': dob_to_age(s['dob2']),
        'retirement_age': retirement_age,
        'start_tp': start_tp(s),
        'defined_benefit': db(s),
        'accumulation_rate': s['contribution'],
        'accumulation_ramp': 1 + float(s['contribution_growth_pct']) / 100,
        'tax_rate_cg': float(s['tax_rate_cg_pct']) / 100,
        'tax_rate_div_default': float(s['tax_rate_div_default_pct']) / 100,
        'cost_basis_method' : s['cost_basis_method'],
        'withdrawal': s['withdrawal'],
        'floor': floor(s),
        'utility_join_required': float(s['utility_join_required']),
        'utility_join_desired': float(s['utility_join_desired']),
        'vw_strategy': 'amount' if s['vw_amount'] else 'sdp',
        'spend_steps': spend_steps,
        'utility_retire': True,
        'utility_inherit_years': s['utility_inherit_years'],
        'utility_dead_limit': float(s['utility_dead_limit_pct']) / 100 if s['inherit'] else 0,
        'utility_bequest_consume': s['utility_bequest_consume'],
        'consume_discount_rate': float(s['consume_discount_rate_pct']) / 100,
        'upside_discount_rate': float(s['upside_discount_rate_pct']) / 100,
        'utility_consume_fn': 'exponential' if s['utility_method'] == 'alpha' else 'power',
        'utility_join': s['utility_method'] == 'floor_plus_upside',
        'utility_join_slope_ratio': float(s['utility_join_slope_ratio_pct']) / 100,
        'utility_eta_2': s['utility_eta_2'],
        'utility_ce': s['utility_ce'] if s['utility_method'] == 'ce' else None,
        'utility_slope_double_withdrawal': s['utility_slope_double_withdrawal'],
        'utility_eta': s['utility_eta_1'] if s['utility_method'] == 'floor_plus_upside' else s['utility_eta'] if s['utility_method'] == 'eta' else None,
        'utility_alpha': s['utility_alpha'],
        'ret_risk_free': float(s['ret_risk_free_pct']) / 100,
        'generate_ret_equity': float(s['ret_equity_pct']) / 100,
        'validate_ret_equity': float(s['ret_equity_pct']) / 100,
        'generate_ret_bonds': float(s['ret_bonds_pct']) / 100,
        'validate_ret_bonds': float(s['ret_bonds_pct']) / 100,
        'management_expense': float(s['expense_pct']) / 100,
        'validate_all_adjust': - float(s['neg_validate_all_adjust_pct']) / 100,
        'validate_equity_vol_adjust': float(s['validate_equity_vol_adjust_pct']) / 100,
    }
    f = open(dirname + '/opal-scenario.txt', mode='w')
    for field, value in s_only.items():
        f.write(field + ' = ' + stringize(value) + '\n')
    f.close()

def run_opal(dirname, s):
    write_scenario(dirname, s)
    boundary = "================8ijgvfdijoew8dvfijfgdij9i43i32jk"
    headers = {'Content-Type': 'multipart/form-data; boundary=' + boundary + ''}
    body = ''
    for name in ('opal-scenario.txt', ):
        body += \
            '--' + boundary + '\r\n' + \
            'Content-Disposition: form-data; name="' + name + '"; filename="' + name + '"\r\n' + \
            'Content-Type: application/octet-stream\r\n' + \
            '\r\n'
        path = dirname + '/' + name
        f = open(path, 'rb')
        body += f.read();
        f.close()
        body += '\r\n'
    body += '--' + boundary +  '--\r\n'
    try:
        conn = HTTPConnection(OPAL_HOST, 8000)
        conn.request('POST', dirname, body, headers)
    except socket.error:
        raise OPALServerError('OPAL server is down.')
    try:
        response = conn.getresponse()
    except socket.error:
        raise OPALServerOverloadedError('OPAL server is overloaded.')
    except HTTPException:
        raise OPALServerError('OPAL server HTTP error.')
    body = response.read()
    if response.status != 200:
        raise OPALServerError('OPAL server - ' + response.reason + '\n' + body)
    msg_str = \
        'MIME-Version: 1.0\r\n' + \
        'Content-Type: ' + response.getheader('Content-Type') + '\r\n' + \
        '\r\n' + body
    msg = message_from_string(msg_str)
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        name = part.get_filename()
        assert(compile('^[A-Za-z0-9-_.]+$').search(name))
        f = open(dirname + '/' + name, 'wb')
        f.write(part.get_payload(decode=True))
        f.close()

class OPALPlottingError(Exception):
    pass
