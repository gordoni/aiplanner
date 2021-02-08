#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from bisect import bisect
from csv import reader, writer
from glob import glob
from json import dumps, loads
from math import ceil, exp, isnan, sqrt
from os import chmod, devnull, environ, getpriority, mkdir, PRIO_PROCESS, setpriority
from os.path import basename, exists, normpath
from random import seed
from shlex import split
from subprocess import CalledProcessError, run
from sys import argv, stderr, stdin, stdout
from traceback import print_exc

import numpy as np

from setproctitle import setproctitle

from ai.common.api import parse_api_scenario
from ai.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from ai.common.evaluator import Evaluator
from ai.common.scenario_space import allowed_gammas, enumerate_model_params_api, scenario_space_model_filename, scenario_space_update_params
from ai.common.tf_util import TFRunner
from ai.common.utils import AttributeObject, boolean_flag
from ai.gym_fin.model_params import dump_params, load_params_file

def pi_merton(env, params, obs, continuous_time = False):
    observation = env.decode_observation(obs)
    assert observation['life_expectancy_both'] == 0
    life_expectancy = observation['life_expectancy_one']
    gamma = params.gamma_low
    mu = env.stocks.mu
    sigma = env.stocks.sigma
    r = env.bills.mu
    alpha = mu + sigma ** 2 / 2
    stocks_allocation = (alpha - r) / (sigma ** 2 * gamma)
    nu = ((gamma - 1) / gamma) * ((alpha - r) * stocks_allocation / 2 + r)
    if nu == 0:
        consume_fraction = 1 / life_expectancy
    elif continuous_time:
        # Merton.
        consume_fraction = nu / (1 - exp(- nu * life_expectancy))
    else:
        # Samuelson.
        a = exp(nu * params.time_period)
        t = ceil(life_expectancy / params.time_period) - 1
        consume_fraction = a ** t * (a - 1) / (a ** (t + 1) - 1) / params.time_period
    return consume_fraction, stocks_allocation

def pi_opal(opal_data, env, params, obs):
    # obs is currently ignored in favor of direct env lookups.
    age = env.age
    age_data = opal_data[age]
    p = env.p_sum()
    i = bisect(age_data['p'], p)
    try:
        p_hi = age_data['p'][i]
    except IndexError:
        print('Extrapolating out of range portfolio lookup:', age, p)
        i -= 1
        p_hi = age_data['p'][i]
    p_lo = age_data['p'][i - 1]
    consume = ((p_hi - p) * age_data['consume'][i - 1] + (p - p_lo) * age_data['consume'][i]) / (p_hi - p_lo)
    stocks = ((p_hi - p) * age_data['stocks'][i - 1] + (p - p_lo) * age_data['stocks'][i]) / (p_hi - p_lo)
    consume_fraction = consume / env.p_plus_income()
    stocks = max(0, min(stocks, 1))
    consume_fraction = max(0, min(consume_fraction, 1 / params.time_period))
    return consume_fraction, stocks

params_cache = {}

def eval_models(eval_model_params, *, api = [{}], daemon, api_content_length, stdin,
    merton, samuelson, opal, models_dir, models_adjust, evaluate, warm_cache, gamma, train_seeds, ensemble, nice,
    train_seed, model_dir, result_dir, aid, num_environments, permissive_api = False, **kwargs):

    priority = getpriority(PRIO_PROCESS, 0)
    priority += nice
    setpriority(PRIO_PROCESS, 0, priority)

    assert not daemon or train_seeds == 1 or ensemble

    assert models_dir is None or model_dir == 'aiplanner.tf'

    assert sum((model_dir != 'aiplanner.tf', merton, samuelson, opal)) <= 1
    model = not (merton or samuelson or opal)

    if not warm_cache:
        try:
            mkdir(result_dir)
        except FileExistsError:
            pass

    results = [{'cid': a.get('cid'), 'results': []} for a in api] # Gets multiply overwritten but is not used, when train_seeds > 1 and not ensemble.

    any_exception = None
    object_id_to_evaluator = {}
    evaluator_to_info = {}
    for i in range(1 if ensemble else train_seeds):

        train_dir_seed = train_seed + i
        result_seed_dir = result_dir + '/seed_' + ('all' if ensemble else str(train_dir_seed))

        if not warm_cache:
            try:
                mkdir(result_seed_dir)
            except FileExistsError:
                pass

        out = open(devnull if daemon else result_seed_dir + '/eval.log', 'w')

        for scenario_num, api_scenario in enumerate(api):

            parse_exception = None
            assert eval_model_params['gamma_low'] == eval_model_params['gamma_high'], "Can't evaluate a gamma range."
            g = eval_model_params['gamma_low']
            if int(g) == g:
                g = int(g)
            control_params = {
                'cid': api_scenario.get('cid'),
                'gammas': [g],
            }

            try:

                if daemon:
                    api_model_params, control_params = parse_api_scenario(api_scenario, permissive = permissive_api)
                    model_params = dict(eval_model_params)
                    for param in api_model_params:
                        if param in model_params:
                            model_params[param] = api_model_params[param]
                        else:
                            assert False, 'Unknown parameter: ' + param
                    scenario_space_update_params(model_params, control_params)
                else:
                    model_params = eval_model_params

            except Exception as e:

                parse_exception = e

            for sub_num, g in enumerate(control_params['gammas']):

                try:

                    prefix = result_seed_dir + '/aiplanner'

                    if parse_exception:
                        raise parse_exception

                    if daemon:
                        assert g in gamma, 'Unsupported gamma value: ' + str(g)
                        model_params['gamma_low'] = model_params['gamma_high'] = g

                    if models_dir is None:
                        model_filename = basename(normpath(model_dir))
                    else:
                        model_filename = scenario_space_model_filename(model_params)
                        model_dir = models_dir + '/' + model_filename

                    if model:
                        try:
                            train_model_params = params_cache[model_dir]
                        except KeyError:
                            train_model_params = params_cache[model_dir] = load_params_file(model_dir + '/params.txt')
                        model_params['action_space_unbounded'] = train_model_params['action_space_unbounded']
                        model_params['observation_space_ignores_range'] = train_model_params['observation_space_ignores_range']
                        model_params['observation_space_clip'] = train_model_params.get('observation_space_clip', False)
                    else:
                        train_model_params = None
                        num_environments = 1
                        model_params['action_space_unbounded'] = True
                        model_params['observation_space_ignores_range'] = False
                        model_params['observation_space_clip'] = False

                    if models_adjust:
                        adjust_json = open(models_adjust).read()
                        adjust = loads(adjust_json)
                        try:
                            adjust_model = adjust[model_filename]
                        except KeyError:
                            adjust_model = {}
                        if adjust_model:
                            if not daemon:
                                print('Adjustments:')
                            for param in sorted(adjust_model.keys()):
                                if param in model_params:
                                    if not daemon:
                                        print('    ' + param + ' = ' + str(adjust_model[param]))
                                    model_params[param] = adjust_model[param]
                                else:
                                    assert False, 'Unknown adjustment: ' + param

                    train_dirs = [model_dir + '/seed_' + str(train_dir_seed + j) for j in range(train_seeds if ensemble else 1)]

                    object_ids, evaluator, initial_results = eval_model(model_params, daemon = daemon,
                        merton = merton, samuelson = samuelson, opal = opal,
                        model = model, evaluate = evaluate, warm_cache = warm_cache, default_object_id = (i, scenario_num, sub_num),
                        train_dirs = train_dirs, out = out, aid = aid, num_environments = num_environments, **kwargs)
                    initial_results['cid'] = control_params['cid']

                    for object_id in object_ids:
                        object_id_to_evaluator[object_id] = evaluator
                    evaluator_to_info[evaluator] = {
                        'scenario_num': scenario_num,
                        'sub_num': sub_num,
                        'out': out,
                        'prefix': prefix,
                        'train_model_params': train_model_params,
                        'eval_model_params': model_params,
                    }

                except Exception as e:
                    if daemon:
                        print_exc(file = stderr)
                        stderr.flush()
                    any_exception = e
                    error_msg = str(e) or e.__class__.__name__ + ' exception encountered.'
                    initial_results = {
                        'aid': aid,
                        'cid': control_params['cid'],
                        'error': error_msg,
                    }

                results[scenario_num]['results'].append(initial_results)

                if (not daemon or evaluate) and not warm_cache:
                    initial_str = dumps(initial_results, indent = 4, sort_keys = True)
                    with open(prefix + '.json', 'w') as w:
                        w.write(initial_str + '\n')

    object_ids = list(object_id_to_evaluator.keys())
    while object_ids:

        if all(type(id) == tuple for id in object_ids):
            object_id = object_ids.pop(0)
        else:
            import ray
            (object_id, ), object_ids = ray.wait(object_ids)

        evaluator = object_id_to_evaluator[object_id]
        del object_id_to_evaluator[object_id]
        if evaluator and (evaluator not in object_id_to_evaluator.values()):

            info = evaluator_to_info[evaluator]
            scenario_num = info['scenario_num']
            sub_num = info['sub_num']
            out = info['out']
            prefix = info['prefix']
            train_model_params = info['train_model_params']
            eval_model_params = info['eval_model_params']

            try:

                res = evaluator.summarize()

                warnings = [] if train_model_params is None else \
                    compatibility_warnings(train_model_params, eval_model_params, results[scenario_num]['results'][sub_num])
                warnings += res['warnings']
                for warning in warnings:
                    print('WARNING:', warning, file = out)

                if res['couple']:
                    print('Couple certainty equivalent:', res['ce'], '+/-', res['ce_stderr'],
                        '(80% confidence interval:', res['consume10'], '-', str(res['consume90']) + ')', file = out)
                print('Evaluation certainty equivalent:', res['ce_individual'], '+/-', res['ce_stderr_individual'],
                    '(80% confidence interval:', res['consume10_individual'], '-', str(res['consume90_individual']) + ')', file = out, flush = True)

                plot(prefix, res['paths'], res['consume_pdf'], res['estate_pdf'], res['consume_cr'], res['alive'])

                final_results = dict(results[scenario_num]['results'][sub_num], **{
                    'error': None,
                    'warnings': warnings,
                    'ce': res['ce'],
                    'ce_stderr': None if isnan(res['ce_stderr']) else res['ce_stderr'],
                    'consume10': res['consume10'],
                    'consume90': res['consume90'],
                    'consume_mean': res['consume_mean'],
                    'consume_stdev': res['consume_stdev'],
                    'consume_preretirement': res['consume_preretirement'],
                    'consume_preretirement_ppf': res['consume_preretirement_ppf'],
                    'consume_pdf': res['consume_pdf'],
                    'estate_pdf': res['estate_pdf'],
                    'consume_cr': res['consume_cr'],
                    'sample_paths': res['paths'],
                    'alive': res['alive'],
                })

            except Exception as e:
                if daemon:
                    print_exc(file = stderr)
                    stderr.flush()
                any_exception = e
                error_msg = e.__class__.__name__ + ': ' + (str(e) or 'Exception encountered.')
                final_results = {
                    'aid': aid,
                    'cid': results[scenario_num]['results'][sub_num]['cid'],
                    'error': error_msg,
                }

            results[scenario_num]['results'][sub_num] = final_results

            #final_str = dumps(final_results, indent = 4, sort_keys = True)
            #with open(prefix + '.json', 'w') as w:
            #    w.write(final_str + '\n')

            # Allow evaluator to be garbage collected to conserve RAM and also allow agent actor process to be killed.
            del evaluator_to_info[evaluator]
            del evaluator

    if daemon and not warm_cache:

        if evaluate:
            api_str = dumps(api, indent = 4, sort_keys = True)
            with open(result_seed_dir + '/api.json', 'w') as w:
                w.write(api_str + '\n')

        failures = [scenario for scenario, result in zip(api, results) if any((sub_result['error'] is not None for sub_result in result['results']))]
        if failures:
            failures_str = dumps(failures, indent = 4, sort_keys = True)
            with open(result_seed_dir + '/failures.json', 'w') as w:
                w.write(failures_str + '\n')

    elif any_exception:

        raise any_exception

    return results

runner_cache = {}

def eval_model(eval_model_params, *, daemon, merton, samuelson, opal, opal_file, address, allow_tensorflow, checkpoint_name,
    evaluate, warm_cache, eval_couple_net, eval_seed, eval_num_timesteps, eval_render,
    num_cpu, model, default_object_id, train_dirs, search_consume_initial_around, out,
               aid, num_workers, num_environments, num_trace_episodes, pdf_buckets, pdf_smoothing_window, pdf_constant_initial_consume):

    eval_seed += 1000 # Use a different seed than might have been used during training.
    # The next two lines should only be needed if we are attempting to evaluate variable scenarios, so that we get the same initial_results each time.
    seed(eval_seed)
    np.random.seed(eval_seed)

    env = make_fin_env(**eval_model_params, direct_action = not model)
    env = env.fin
    params = AttributeObject(env.params_dict)

    eval_model_params['display_returns'] = False # Only have at most one env display returns, which will be computed on the local node.

    skip_model = params.consume_policy != 'rl' and params.annuitization_policy != 'rl' and params.asset_allocation_policy != 'rl' and \
        (not params.real_bonds or params.real_bonds_duration is not None) and \
        (not params.nominal_bonds or params.nominal_bonds_duration is not None)

    env.set_info(strategy = True)

    obs = env.reset()

    remote_evaluators = None

    if merton or samuelson:

        consume_fraction, stocks_allocation = pi_merton(env, params, obs, continuous_time = merton)
        action = env.encode_direct_action(consume_fraction, stocks = stocks_allocation, bills = 1 - stocks_allocation)

    elif opal:

        opal_dat = {}
        with open(opal_file) as f:
            r = reader(f)
            for row in r:
                if row:
                    age, p, _, _, _, _, consume, _, stocks, _ = row
                    age = float(age)
                    p = float(p)
                    consume = float(consume)
                    stocks = float(stocks)
                    try:
                        l = opal_dat[age]
                    except KeyError:
                        l = []
                        opal_dat[age] = l
                    l.append((p, consume, stocks))
        opal_data = {}
        for age, data in opal_dat.items():
            p, consume, stocks = zip(*sorted(data))
            opal_data[age] = {'p': p, 'consume': consume, 'stocks': stocks}

        consume_fraction, stocks_allocation = pi_opal(opal_data, env, params, obs)
        action = env.encode_direct_action(consume_fraction, stocks = stocks_allocation, iid_bonds = 1 - stocks_allocation)

    else:

        try:
            runner = runner_cache[train_dirs[0]]
        except KeyError:
            runner = TFRunner(train_dirs = train_dirs, allow_tensorflow = allow_tensorflow, checkpoint_name = checkpoint_name, eval_model_params = eval_model_params, couple_net = eval_couple_net,
                address = address, num_workers = num_workers, runner_seed = eval_seed, num_environments = num_environments, num_cpu = num_cpu).__enter__()
            if daemon and not runner.remote_evaluators:
                # Don't cache runner if not daemon as it prevents termination of Ray workers.
                # Don't cache runner if remote evaluators as remote evaluators would cache old eval_model_params.
                runner_cache[train_dirs[0]] = runner
        remote_evaluators = runner.remote_evaluators

        action, = runner.run([obs])

    _, _, _, initial_results = env.step(action)

    initial_results = {
        'error': None,
        'aid': aid,
        'rra': params.gamma_low,
        'consume': initial_results['consume'],
        'asset_classes': initial_results['asset_allocation'].classes(),
        'asset_allocation': initial_results['asset_allocation'].as_list(),
        'asset_allocation_tax_free': initial_results['asset_allocation_tax_free'].as_list() if initial_results['asset_allocation_tax_free'] else None,
        'asset_allocation_tax_deferred': initial_results['asset_allocation_tax_deferred'].as_list() if initial_results['asset_allocation_tax_deferred'] else None,
        'asset_allocation_taxable': initial_results['asset_allocation_taxable'].as_list() if initial_results['asset_allocation_taxable'] else None,
        'retirement_contribution': initial_results['retirement_contribution'],
        'real_spias_purchase': initial_results['real_spias_purchase'],
        'nominal_spias_purchase': initial_results['nominal_spias_purchase'],
        'nominal_spias_adjust': initial_results['nominal_spias_adjust'],
        'pv_spias_purchase': initial_results['pv_spias_purchase'],
        'real_bonds_duration': initial_results['real_bonds_duration'],
        'nominal_bonds_duration': initial_results['nominal_bonds_duration'],
        'pv_preretirement_income': initial_results['pv_preretirement_income'],
        'pv_retired_income': initial_results['pv_retired_income'],
        'pv_future_taxes': initial_results['pv_future_taxes'],
        'portfolio_wealth': initial_results['portfolio_wealth'],
    }

    if not daemon:

        print('Initial properties for first episode:', file = out)
        print('    Consume:', initial_results['consume'], file = out)
        print('    Asset allocation:', initial_results['asset_allocation'], file = out)
        print('    401(k)/IRA contribution:', initial_results['retirement_contribution'], file = out)
        print('    Real income annuities purchase:', initial_results['real_spias_purchase'], file = out)
        print('    Nominal income annuities purchase:', initial_results['nominal_spias_purchase'], file = out)
        print('    Real bonds duration:', initial_results['real_bonds_duration'], file = out)
        print('    Nominal bonds duration:', initial_results['nominal_bonds_duration'], file = out)

        print(file = out, flush = True)

    if evaluate and not warm_cache:

        envs = []
        for _ in range(num_environments):
            envs.append(make_fin_env(**eval_model_params, direct_action = not model))

        evaluator = Evaluator(envs, eval_seed, eval_num_timesteps, remote_evaluators = remote_evaluators, render = eval_render,
            num_trace_episodes = num_trace_episodes, pdf_buckets = pdf_buckets, pdf_smoothing_window = pdf_smoothing_window, pdf_constant_initial_consume = pdf_constant_initial_consume)

        def pi(obss):

            if model:

                if skip_model:
                    action = [None] * len(obss)
                else:
                    action = runner.run(obss)

                return action

            elif merton or samuelson:

                results = []
                for obs in obss:
                    consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
                    observation = env.decode_observation(obs)
                    assert observation['life_expectancy_both'] == 0
                    life_expectancy = observation['life_expectancy_one']
                    t = ceil(life_expectancy / params.time_period) - 1
                    if t == 0:
                        consume_fraction = min(consume_fraction, 1 / params.time_period) # Bound may be exceeded in continuous time case.
                    results.append(env.encode_direct_action(consume_fraction, stocks = stocks_allocation, bills = 1 - stocks_allocation))
                return results

            elif opal:

                results = []
                for obs in obss:
                    consume_fraction, stocks_allocation = pi_opal(opal_data, env, obs)
                    results.append(env.encode_direct_action(consume_fraction, stocks = stocks_allocation, iid_bonds = 1 - stocks_allocation))
                return results

            else:

                assert False

        if search_consume_initial_around is not None:

            f_cache = {}

            def f(x):

                try:

                    return f_cache[x]

                except KeyError:

                    print('    Consume: ', x)
                    for e in envs:
                        e.fin.params.consume_initial = x
                    evaluator.evaluate(pi)
                    res = evaluator.summarize()
                    f_x = res['ce']
                    tol_x = res['ce_stderr']
                    results = (f_x, tol_x)
                    f_cache[x] = results
                    return results

            x, f_x = gss(f, search_consume_initial_around / 2, search_consume_initial_around * 2)
            print('    Consume: ', x)
            for e in envs:
                e.fin.params.consume_initial = x

        object_ids = evaluator.evaluate(pi)

    else:

        evaluator = None
        object_ids = None

    if not daemon:
        runner.__exit__(None, None, None)

    if not object_ids:
        object_ids = [default_object_id]

    return object_ids, evaluator, initial_results

def gss(f, a, b):
    '''Golden segment search for maximum of f on [a, b].'''

    f_a, tol_a = f(a)
    f_b, tol_b = f(b)
    tol = (tol_a + tol_b) / 2
    g = (1 + sqrt(5)) / 2
    while (b - a) > tol:
        c = b - (b - a) / g
        d = a + (b - a) / g
        f_c, tol_c = f(c)
        f_d, tol_d = f(d)
        if f_c >= f_d:
            b = d
            f_b = f_d
        else:
            a = c
            f_a = f_c
        tol = (tol_c + tol_d) / 2
    if f_a > f_b:
        found = a
        f_found = f_a
    else:
        found = b
        f_found = f_b

    return found, f_found

def compatibility_warnings(train_params, eval_params, initial_results):

    warnings = []

    eval_couple = eval_params['couple_probability'] > 0
    train_couple = train_params['couple_probability'] > 0
    eval_retired = eval_params['age_start'] >= eval_params['age_retirement_high']
    train_retired = train_params['age_start'] >= train_params['age_retirement_high']

    def couple_val(params, what):

        return params[what] if params['couple_probability'] > 0 else 0

    def gi_payout(params, what):

        payout = 0
        for gi in loads(params['guaranteed_income']) + loads(params['guaranteed_income_additional']):
            if gi.get('end', None) is None and gi.get('source_of_funds', 'tax_deferred') in what:
                if gi.get('owner', 'self') == 'self' or params['couple_probability'] > 0:
                    try:
                        payout_low, payout_high = gi['payout']
                    except TypeError:
                        payout_high = gi['payout']
                    payout += payout_high
        return payout

    def p(params):

        return params['p_tax_free_high'] + params['p_tax_deferred_high'] + params['p_taxable_stocks_high'] + params['p_taxable_real_bonds_high'] + \
            params['p_taxable_nominal_bonds_high'] + params['p_taxable_iid_bonds_high'] + params['p_taxable_other_high'] + params['p_weighted_high']

    if eval_params['age_start'] < train_params['age_start'] or \
        eval_params['age_start2_low'] < (train_params['age_start2_low'] if train_couple else train_params['age_start']):
        warnings.append('Model was not trained for such a young starting age.')

    if eval_params['life_expectancy_additional_low'] < train_params['life_expectancy_additional_low'] or \
        eval_couple and eval_params['life_expectancy_additional2_low'] < train_params['life_expectancy_additional2_low']:
        warnings.append('Model was not trained for such poor health.')

    if eval_params['life_expectancy_additional_high'] > train_params['life_expectancy_additional_high'] or \
        eval_couple and eval_params['life_expectancy_additional2_high'] > train_params['life_expectancy_additional2_high']:
        warnings.append('Model was not trained for such exceptionally good health.')

    if max(eval_params['age_retirement_low'], eval_params['age_start']) < max(train_params['age_retirement_low'], train_params['age_start']):
        warnings.append('Model was not trained for such an early retirement age.')

    if not train_retired and max(eval_params['age_retirement_high'], eval_params['age_start']) > max(train_params['age_retirement_high'], train_params['age_start']):
        warnings.append('Model was not trained for such a late retirement age.')

    if gi_payout(eval_params, ['tax_free']) > gi_payout(train_params, ['tax_free']):
        warnings.append('Model was not trained for such a large tax free guaranteed income.')

    if gi_payout(eval_params, ['tax_deferred']) > gi_payout(train_params, ['tax_deferred']):
        warnings.append('Model was not trained for such a large tax deferred guaranteed income.')

    if gi_payout(eval_params, ['taxable']) > gi_payout(train_params, ['taxable']):
        warnings.append('Model was not trained for such a large taxable guaranteed income.')

    if eval_retired:

        gi_preretirement_eval = 0
        gi_preretirement_train_high = 0

    else:

        gi_preretirement_eval = (eval_params['income_preretirement_high'] + couple_val(eval_params, 'income_preretirement2_high')) * \
            (1 - eval_params['consume_preretirement_income_ratio_low']) - eval_params['consume_preretirement']
        gi_preretirement_train_high = (train_params['income_preretirement_high'] + couple_val(train_params, 'income_preretirement2_high')) * \
            (1 - train_params['consume_preretirement_income_ratio_low']) - train_params['consume_preretirement']

        if gi_preretirement_eval > gi_preretirement_train_high:
            warnings.append('Model was not trained for such a high pre-retirement net income.')

    growth_rate = 1.05
    preretirement_years_eval = max(0, eval_params['age_retirement_high'] - eval_params['age_start'])
    preretirement_years_train = max(0, train_params['age_retirement_high'] - train_params['age_start'])
    retirement_net_worth_eval = preretirement_years_eval * gi_preretirement_eval + growth_rate ** preretirement_years_eval * p(eval_params)
    retirement_net_worth_train_high = preretirement_years_train * gi_preretirement_train_high + growth_rate ** preretirement_years_train * p(train_params)

    if retirement_net_worth_eval > retirement_net_worth_train_high:
        if eval_retired:
            warnings.append('Model was not trained for such a large retirement investment portfolio.')
        else:
            warnings.append('Model was not trained for such a large expected retirement investment portfolio.')

    pv_income_eval = (0 if eval_retired else initial_results['pv_preretirement_income']) + initial_results['pv_retired_income']
    try:
        gi_fraction = pv_income_eval / (pv_income_eval + initial_results['portfolio_wealth'])
    except ZeroDivisionError:
        gi_fraction = 0
    if gi_fraction < train_params['gi_fraction_low']:
        warnings.append('Model was not trained for such a low guaranteed income to investments ratio.')

    return warnings

def plot(prefix, traces, consume_pdf, estate_pdf, consume_cr, alive):

    try:
        couple_status = alive['couple'][0] > 0
        age_low = alive['age'][0]
    except IndexError:
        couple_status = False
        age_low = 0
    age_high = age_low
    for age, couple, single in zip(alive['age'], alive['couple'], alive['single']):
        if couple + single < 0.01:
            age_high = age
            break
    try:
        consume_high_trace = max(max(trace['consume']) for trace in traces)
    except ValueError:
        consume_high_trace = 0
    try:
        consume_high_cr = max(max(region['high']) for region in consume_cr)
    except ValueError:
        consume_high_cr = 0
    consume_high = max(consume_high_trace, consume_high_cr)
    with open(prefix + '-params.gnuplot', 'w') as f:
        print('couple =', int(couple_status), file = f)
        print('age_low =', age_low, file = f)
        print('age_high =', age_high, file = f)
        print('consume_high =', consume_high, file = f)

    with open(prefix + '-paths.csv', 'w') as f:
        csv_writer = writer(f)
        for trace in traces:
            for i, (age, alive_count, total_guaranteed_income, portfolio_wealth_pretax, consume, real_spias_purchase, nominal_spias_purchase, asset_allocation) in \
                enumerate(zip(trace['age'], trace['alive_count'], trace['total_guaranteed_income'], trace['portfolio_wealth_pretax'], trace['consume'],
                    trace['real_spias_purchase'], trace['nominal_spias_purchase'], trace['asset_allocation'])):

                couple_plot = alive_count == 2
                single_plot = alive_count == 1
                try:
                    if alive_count == 2 and trace['alive_count'][i + 1] == 1:
                        single_plot = True
                except IndexError:
                    pass
                csv_writer.writerow((age, int(couple_plot), int(single_plot), total_guaranteed_income, portfolio_wealth_pretax, consume,
                    real_spias_purchase, nominal_spias_purchase, *asset_allocation))
            csv_writer.writerow(())

    pdf = zip(consume_pdf['consume'], consume_pdf['weight'])
    with open(prefix + '-consume-pdf.csv', 'w') as f:
        csv_writer = writer(f)
        csv_writer.writerows(pdf)

    pdf = zip(estate_pdf['estate'], estate_pdf['weight'])
    with open(prefix + '-estate-pdf.csv', 'w') as f:
        csv_writer = writer(f)
        csv_writer.writerows(pdf)

    for region in consume_cr:
        cr = zip(region['age'], region['low'], region['high'])
        with open(prefix + '-consume-cr%4.2f.csv' % region['confidence_level'], 'w') as f:
            csv_writer = writer(f)
            csv_writer.writerows(cr)

    data = zip(alive['age'], alive['couple'], alive['single'])
    with open(prefix + '-alive.csv', 'w') as f:
        csv_writer = writer(f)
        csv_writer.writerows(data)

    try:
        environ['AIPLANNER_FILE_PREFIX'] = prefix
        run([environ['AIPLANNER_HOME'] + '/ai/plot'], stderr = stderr, check = True) # stderr = stderr is needed because stderr may have been reassigned.
    except CalledProcessError:
        assert not traces, 'Error ploting results.'

def main():
    parser = arg_parser(training = False)
    parser.add_argument('-d', '--daemon', action = "store_true", default = False)
    parser.add_argument('--api-content-length', type = int, default = None)
    boolean_flag(parser, 'stdin', default = False)
    boolean_flag(parser, 'merton', default = False)
    boolean_flag(parser, 'samuelson', default = False)
    boolean_flag(parser, 'opal', default = False)
    parser.add_argument('--opal-file', default = 'opal-linear.csv')
    parser.add_argument('--address')
    parser.add_argument('--models-dir')
    parser.add_argument('--models-adjust') # JSON file containing adjustments to apply to each model.
    parser.add_argument('--gamma', action = 'append', type = float, default = [])
    parser.add_argument('--train-seeds', type = int, default = 1) # Number of seeds to evaluate.
    boolean_flag(parser, 'ensemble', default = False)
        # Whether to evaluate the average recommendation of the seeds or to evaluate the seeds individually in parallel.
    boolean_flag(parser, 'allow-tensorflow', default = True)
    parser.add_argument('--checkpoint-name')
    boolean_flag(parser, 'evaluate', default = True) # Inference and simulation, otherwise inference only.
    boolean_flag(parser, 'warm-cache', default = True) # Pre-load tensorflow/Rllib models.
    boolean_flag(parser, 'eval-couple-net', default = False)
    parser.add_argument('--search-consume-initial-around', type = float)
        # Search for the initial consumption that maximizes the certainty equivalent using the supplied value as a hint as to where to search.
    parser.add_argument('--result-dir', default = 'results')
    parser.add_argument('--aid') # AIPlanner id.
    parser.add_argument('--num-workers', type = int, default = 0) # Number of remote processes for Ray evaluation. Zero for local evaluation.
        # Evaluation results are deterministic for a given num_workers value.
    parser.add_argument('--num-environments', type = int, default = 200) # Number of parallel environments to use for per worker. Speeds up torch/tensorflow.
    parser.add_argument('--num-trace-episodes', type = int, default = 5) # Number of sample traces to generate.
    parser.add_argument('--pdf-buckets', type = int, default = 100) # Number of non de minus buckets to use in computing probability density distributions.
    parser.add_argument('--pdf-smoothing-window', type = float, default = 0.02) # Width of smoothing window to use in computing probability density distributions.
    boolean_flag(parser, 'pdf-constant-initial-consume', default = False) # Whether to include the initial consumption spike for retired scenarios in the consumption probability density distribution.
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False, dump = False)
    setproctitle('evaluate' if args['evaluate'] else 'infer')
    if args['stdin']:
        args['daemon'] = True
    if not args['daemon']:
        assert args['api_content_length'] is None and not args['gamma']
        args['warm_cache'] = False
        dump_params(dict(eval_model_params, **args))
        eval_models(eval_model_params, **args)
    else:
        if not args['gamma']:
            args['gamma'] = allowed_gammas
        if args['stdin']:
            args['warm_cache'] = False
            api_json = stdin.read()
            api = loads(api_json)
            results = eval_models(eval_model_params, api = api, permissive_api = True, **args)
            results_str = dumps(results, indent = 4, sort_keys = True)
            print(results_str)
        else:
            if args['models_dir'] is not None and args['warm_cache']:
                for model_params, api in enumerate_model_params_api(args['gamma']):
                    model_params = dict(eval_model_params, **model_params)
                    eval_args = dict(args, api = api, permissive_api = True, eval_num_timesteps = 1)
                    eval_models(model_params, **eval_args)
            global stderr
            original_stderr = stderr
            while True:
                try:
                    line = stdin.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    args = argv[1:] + split(line)
                    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False, dump = False, args = args)
                    args['warm_cache'] = False
                    api_content_length = args['api_content_length']
                    assert api_content_length is not None, 'No --api-content-length parameter.'
                    api_json = stdin.read(api_content_length)
                    api = loads(api_json)
                    if args.get('aid'):
                        try:
                            mkdir(args['result_dir'])
                        except FileExistsError:
                            pass
                        stderr = open(args['result_dir'] + '/eval.err', 'w')
                    assert len(api) <= 10000, 'Too many scenarios in a single request.'
                    results = {
                        'error': None,
                        'result': eval_models(eval_model_params, api = api, **args)
                    }
                except Exception as e:
                    print_exc(file = stderr)
                    results = {'error': e.__class__.__name__ + ': ' + (str(e) or 'Exception encountered.')}
                except SystemExit as e:
                    results = {'error': 'Invalid argument.'}
                finally:
                    stderr.flush()
                    stderr = original_stderr
                results_str = dumps(results, sort_keys = True) + '\n'
                print('\nAIPlanner-Result')
                print('Content-Length:', len(results_str.encode('utf-8')))
                stdout.write(results_str)
                stdout.flush()

if __name__ == '__main__':
    main()
