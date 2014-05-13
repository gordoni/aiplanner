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
from socket import gethostname
from stat import S_IRWXU
from subprocess import call, Popen
from tempfile import mkdtemp
from time import strptime

from oaa.utils import asset_class_names, asset_class_symbols
from settings import SECRET_KEY, STATIC_ROOT, STATIC_URL

# Deleted names can only be judicially re-used, since inactive users might still hold an old parameter of that name. This means types can never be changed.
default_params = {
    #'name': None,
    'sex': None,
    'dob': None,
    'sex2': None,
    'dob2': None,
    'advanced_position': False,
    'defined_benefit_social_security': Decimal(0),
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
    'floor': Decimal(30000),
    'risk_tolerance': Decimal(20),
    'vw': True,
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
    'class_aaa': False,
    'class_baa': False,
    'class_reits': False,
    'class_gold': False,
    'class_risk_free' : False,
    'ret_risk_free_pct': Decimal('1.0'),
    'generate_start_year': 1927,
    'generate_end_year': 2013,
    'validate_start_year': 1927,
    'validate_end_year': 2013,
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
    #'donate_inherit_discount_rate_pct': Decimal(15),
    'advanced_well_being': False,
    'consume_discount_rate_pct': Decimal(2.0),
    'public_assistance': Decimal(10000),
    'public_assistance_phaseout_rate_pct': Decimal(50),
    'utility_method': 'ce',
    'utility_ce': Decimal('1.26'),
    'utility_slope_double_withdrawal': Decimal(8),
    'utility_eta': Decimal('3.0'),
    'utility_alpha': Decimal('4.0'),
}

resolution = 'medium'
if resolution == 'low':
    zero_bucket_size = 0.2
    scaling_factor = 1.02
    aa_steps = 50
    spend_steps = 5000
elif resolution == 'medium':
    zero_bucket_size = 0.1
    scaling_factor = 1.001
    aa_steps = 1000
    spend_steps = 10000  # Some noise in withdrawal map, and possibly consumption paths.
else:
    zero_bucket_size = 0.1
    scaling_factor = 1.0001
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
    response = run_response(request, scenario_dict)
    return response

def run_response(request, scenario_dict):
    umask(0077)
    dirname = mkdtemp(prefix='', dir=STATIC_ROOT + 'results')
    run_opal(dirname, scenario_dict)
    return display_result(request, dirname, False, scenario_dict)

def sample_scenario_dict():
    s = dict(default_params)
    s['name'] = 'Sample Results'
    s['sex'] = 'male'
    s['dob'] = 45
    s['p'] = Decimal(600000)
    s['contribution'] = Decimal(5000)
    s['retirement_year'] = datetime.utcnow().timetuple().tm_year + 65 - 45
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
            data['number'] = int(float(number))
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
        if float(failure_chance) >= 10:
            data['risk'] = 'high'
        elif float(failure_chance) >= 1:
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

def write_scenario(dirname, s):
    gnuplot_max_portfolio = min(max(50 * float(s['withdrawal']), 2 * start_tp(s)), 1000 * float(s['withdrawal']))
    guaranteed_max_portfolio = 1000 * float(s['withdrawal'])
    retirement_age = dob_to_age(s['dob']) + max(0, s['retirement_year'] - datetime.utcnow().timetuple().tm_year)
    # Caution: Config.java maintains values from previous runs, so all modified values must be updated each time.
    s_only = {
        'skip_retirement_number': not s['retirement_number'],
        'skip_compare': s['retirement_number'],
        'vw_percentage': 0.04,
        'skip_validate': s['retirement_number'],
        'zero_bucket_size': zero_bucket_size * float(s['withdrawal']),
        'scaling_factor': scaling_factor,
        'search' : 'hill',
        'aa_steps': aa_steps,
        'pf_guaranteed': guaranteed_max_portfolio,
          # Compute map using portfolio size up to 1000 times withdrawal.
        'pf_validate': guaranteed_max_portfolio,
          # Now that we skip dump_load we compute metrics on the same map (we used to cut off at 60 times withdrawal).
        'pf_retirement_number': 200 * max(float(s['floor']), float(s['withdrawal'])),
            # Worst case seen ages 70/50, risk tolerance 5%, ret_equity=ret_bonds=0, floor=20k, withdrawal=25k.
        'pf_gnuplot': gnuplot_max_portfolio,
          # And we record the map 100-1000 times withdrawal.
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
        'sex2': s['sex2'],
        'start_age2': dob_to_age(s['dob2']),
        'retirement_age': retirement_age,
        'start_tp': start_tp(s),
        'defined_benefit': db(s),
        'rcr': s['contribution'],
        'accumulation_ramp': 1 + float(s['contribution_growth_pct']) / 100,
        'tax_rate_cg': float(s['tax_rate_cg_pct']) / 100,
        'tax_rate_div_default': float(s['tax_rate_div_default_pct']) / 100,
        'cost_basis_method' : s['cost_basis_method'],
        'withdrawal': s['withdrawal'],
        'floor': s['floor'],
        'vw_strategy': 'sdp' if s['vw'] else 'amount',
        'spend_steps': spend_steps,
        'utility_retire': True,
        'utility_inherit_years': s['utility_inherit_years'],
        #'utility_slope_zero': s['utility_slope_zero'],
        'utility_dead_limit': float(s['utility_dead_limit_pct']) / 100 if s['inherit'] else 0,
        'consume_discount_rate': float(s['consume_discount_rate_pct']) / 100,
        'public_assistance': s['public_assistance'],
        'public_assistance_phaseout_rate': float(s['public_assistance_phaseout_rate_pct']) / 100,
        'utility_consume_fn': 'exponential' if s['utility_method'] == 'alpha' else 'power',
        'utility_ce': s['utility_ce'] if s['utility_method'] == 'ce' else None,
        'utility_slope_double_withdrawal': s['utility_slope_double_withdrawal'],
        'utility_eta': s['utility_eta'] if s['utility_method'] == 'eta' else None,
        'utility_alpha': s['utility_alpha'],
        'ret_risk_free': float(s['ret_risk_free_pct']) / 100,
        'generate_ret_equity': float(s['ret_equity_pct']) / 100,
        'validate_ret_equity': float(s['ret_equity_pct']) / 100,
        'generate_ret_bonds': float(s['ret_bonds_pct']) / 100,
        'validate_ret_bonds': float(s['ret_bonds_pct']) / 100,
        'management_expense': float(s['expense_pct']) / 100,
        'validate_all_adjust': - float(s['neg_validate_all_adjust_pct']) / 100,
        'validate_equity_vol_adjust': float(s['validate_equity_vol_adjust_pct']) / 100,
        'target_schemes': ('age_in_bonds', 'age_minus_10_in_bonds', 'target_date'),
        'num_sequences_target' : 20000,
    }
    f = open(dirname + '/opal-scenario.txt', mode='w')
    for field, value in s_only.items():
        f.write(field + ' = ' + stringize(value) + '\n')
    f.close()

def write_gnuplot(dirname, s):
    now_year = s['retirement_year'] if s['retirement_number'] else datetime.utcnow().timetuple().tm_year
    age = dob_to_age(s['dob'])
    age2 = dob_to_age(s['dob2'])
    youngest = age
    if age2 != None and age2 < age:
        youngest = age2
    if s['retirement_number']:
        years_to_retire = max(0, s['retirement_year'] - datetime.utcnow().timetuple().tm_year)
        age += years_to_retire
        youngest += years_to_retire
    years = max(0, 100 - youngest)
    gnuplot_max_portfolio = min(max(50 * float(s['withdrawal']), 2 * start_tp(s)), 1000 * float(s['withdrawal']))

    f = open(dirname + '/plot.gnuplot', mode='w')

    f.write('''#!/usr/bin/gnuplot

set datafile separator ","
set terminal png transparent size 800,400 font "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
# Specify font path to work around Ubuntu 12.04 bug (warning message generated because unable to find font).

set xrange [*:*]
set format x "%.1s%c"
set ylabel "utility"
set yrange [*:*]
set format y "%.1s%c"

set xlabel "consumption ($)"
set output "opal-utility-consume.png"
plot "opal-utility-consume.csv" using 1:2 with lines notitle

set xlabel "bequest ($)"
set output "opal-utility-inherit.png"
plot "opal-utility-inherit.csv" using 1:2 with lines notitle

set xlabel "consumption slope ($)"
set yrange [0:20]
set format y "%.0f"
set output "opal-utility-slope-consume.png"
plot "opal-utility-consume.csv" using 1:3 with lines notitle

set xlabel "bequest slope ($)"
set yrange [*:*]
set format y "%.2f"
set output "opal-utility-slope-inherit.png"
plot "opal-utility-inherit.csv" using 1:3 with lines notitle

unset format
''')

    if s['vw'] and not s['retirement_number']:
        f.write('''
set xrange [0:*]
set format x "%.1s%c"
set ylabel "probability density"
set yrange [0:*]
unset ytics

set xlabel "annual consumption ($)"
set output "opal-distrib-consume.png"
plot "opal-distrib-consume.csv" using 1:2:(0.1) smooth acsplines with lines notitle
  # Spline makes look nicer due to limited number of buckets used.

set xrange [*:*]
set format x "%.0f%%"

set xlabel "change in annual consumption"
set output "opal-distrib-change-consume.png"
plot "opal-distrib-change-consume.csv" using ($1*100):2:(0.1) smooth acsplines with lines notitle
  # Splines needed because results are very noisy due to use of limited historical data.

set ytics

set ylabel "cummulative probability"
set yrange[0:100]
set format y "%.0f%%"

set xlabel "change in annual consumption"
set output "opal-distrib-change-consume-cdf.png"
plot "opal-distrib-change-consume.csv" using ($1*100):($3*100) with lines notitle
''')

    f.write('''
set xlabel "year"
set xrange [''' + str(now_year) + ':' + str(now_year + years) + ''']
set format x "%.0f"

set ylabel "portfolio size ($)"
set format y "%.1s%c"
set yrange [0:''' + str(gnuplot_max_portfolio) + ''']

set cblabel "utility"
set cbrange [''' + str(- 20 * s['withdrawal']) + ''':0]
  # Lower bound is somewhat arbitrary.
set format cb "%.1s%c"
set palette defined (0.0 "red", 25.0 "light-red", 50.0 "orange", 75.0 "light-green", 100.0 "green")
set output "opal-success-raw.png"
plot "opal-linear.csv" using (''' + str(now_year - age) + ''' + $1):2:3 with image notitle
''')

    if s['vw']:
        f.write('''
set cblabel "annual consumption amount"
set cbrange [0:''' + str(2 * s['withdrawal']) + ''']
set format cb "%.1s%c"
set palette defined (0.0 "red", 25.0 "light-red", 50.0 "orange", 75.0 "light-green", 100.0 "green")
set output "opal-consume.png"
plot "opal-linear.csv" using (''' + str(now_year - age) + ''' + $1):2:7 with image notitle

set yrange [0:''' + str(gnuplot_max_portfolio) + ''']
''')

    symbols = asset_class_symbols(s)
    names = asset_class_names(s)
    for (offset, (symbol, name)) in enumerate(zip(symbols, names)):
        f.write('''
set cblabel "''' + name + ''' / total assets"
set cbrange [0:100]
set format cb "%.0f%%"
set palette defined (0.0 "blue", 50.0 "yellow", 100.0 "red")
set output "opal-''' + symbol + '''.png"
plot "opal-linear.csv" using (''' + str(now_year - age) + ''' + $1):2:($''' + str(9 + offset) + ''' * 100) with image notitle
''')

    if s['retirement_number']:

        f.write('''
set xlabel "retirement number ($)"
set xrange [0:*]
set format x "%.1s%c"

set ylabel "failure probability"
set yrange [0:20]
set format y "%.0f%%"
set output "opal-rn-probability.png"
plot "opal-number.csv" using 1:($2 * 100) with lines notitle

set ylabel "failure length (years)"
set yrange [0:10]
set format y "%.0f"
set output "opal-rn-length.png"
plot "opal-number.csv" using 1:3 with lines notitle

set ylabel "equivalent guaranteed amount ($)"
set yrange [0:*]
set format y "%.1s%c"
set output "opal-rn-inverse-utility.png"
plot "opal-number.csv" using 1:4 with lines notitle
''')
    else:

        f.write('''
set output "opal-paths-p.png"
plot "opal-paths.csv" using (''' + str(now_year - age) + ''' + $1):2 with lines notitle

set output "opal-pct-p.png"
plot "opal-pct-p.csv" using (''' + str(now_year - age) + ''' + $1):2:3:4 with errorlines notitle

set ylabel "consumption ($)"
set yrange [0:*]
set format y "%.1s%c"
set output "opal-paths-consume.png"
plot "opal-paths.csv" using (''' + str(now_year - age) + ''' + $1):3 with lines notitle
''')

        if s['vw']:
            f.write('''
set output "opal-pct-consume.png"
plot "opal-pct-consume.csv" using (''' + str(now_year - age) + ''' + $1):2:3:4 with errorlines notitle
''')

    f.close()
    chmod(dirname + '/plot.gnuplot', S_IRWXU)

def run_opal(dirname, s):
    write_scenario(dirname, s)
    write_gnuplot(dirname, s)
    boundary = "================8ijgvfdijoew8dvfijfgdij9i43i32jk"
    headers = {'Content-Type': 'multipart/form-data; boundary=' + boundary + ''}
    body = ''
    for name in ('opal-scenario.txt', 'plot.gnuplot'):
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
    current_site = gethostname()
    if '.' in current_site:
        load_balancer = current_site.domain.replace('.', '-lb.', 1)
    else:
        load_balancer = current_site + '-lb'
    try:
        conn = HTTPConnection(load_balancer, 8000)
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
