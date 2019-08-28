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

from bisect import bisect
from csv import reader, writer
from glob import glob
from json import dumps, loads
from math import ceil, exp, isnan, sqrt
from os import chmod, devnull, environ, getpriority, mkdir, PRIO_PROCESS, setpriority
from os.path import exists
from shlex import split
from subprocess import CalledProcessError, run
from sys import argv, stderr, stdin, stdout
from traceback import print_exc

from baselines.common import boolean_flag
#from baselines.common.misc_util import set_global_seeds

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.model_params import dump_params, load_params_file
from gym_fin.envs.policies import policy
from gym_fin.common.api import parse_api_scenario
from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator
from gym_fin.common.scenario_space import allowed_gammas, enumerate_model_params_api, scenario_space_model_filename, scenario_space_update_params
from gym_fin.common.tf_util import TFRunner

def pi_merton(env, obs, continuous_time = False):
    observation = env.decode_observation(obs)
    assert observation['life_expectancy_both'] == 0
    life_expectancy = observation['life_expectancy_one']
    gamma = env.params.gamma_low
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
        a = exp(nu * env.params.time_period)
        t = ceil(life_expectancy / env.params.time_period) - 1
        consume_fraction = a ** t * (a - 1) / (a ** (t + 1) - 1) / env.params.time_period
    return consume_fraction, stocks_allocation

def pi_opal(opal_data, env, obs):
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
    consume_fraction = max(0, min(consume_fraction, 1 / env.params.time_period))
    return consume_fraction, stocks

def eval_models(eval_model_params, *, api = [{}], daemon, api_content_length, stdin,
    merton, samuelson, annuitize, opal, models_dir, evaluate, warm_cache, gamma, train_seeds, ensemble, nice,
    train_seed, model_dir, result_dir, aid, num_environments, permissive_api = False, **kwargs):

    priority = getpriority(PRIO_PROCESS, 0)
    priority += nice
    setpriority(PRIO_PROCESS, 0, priority)

    assert not daemon or train_seeds == 1 or ensemble

    assert models_dir == None or model_dir == 'aiplanner.tf'

    assert sum((model_dir != 'aiplanner.tf', merton, samuelson, annuitize, opal)) <= 1
    model = not (merton or samuelson or annuitize or opal)

    if not warm_cache:
        try:
            mkdir(result_dir)
        except FileExistsError:
            pass

    if model:
        if models_dir != None:
            model_dir = models_dir + '/' + scenario_space_model_filename(eval_model_params)
        train_model_params = load_params_file(model_dir + '/params.txt')
        eval_model_params['action_space_unbounded'] = train_model_params['action_space_unbounded']
        eval_model_params['observation_space_ignores_range'] = train_model_params['observation_space_ignores_range']
        eval_model_params['observation_space_clip'] = train_model_params.get('observation_space_clip', False)
    else:
        num_environments = 1
        eval_model_params['action_space_unbounded'] = True
        eval_model_params['observation_space_ignores_range'] = False
        eval_model_params['observation_space_clip'] = False

    results = [[] for _ in range(len(api))] # Gets multiply overwritten but is not used, when train_seeds > 1 and not ensemble.

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

                    if models_dir != None:
                        model_dir = models_dir + '/' + scenario_space_model_filename(model_params)
                    train_dirs = [model_dir + '/seed_' + str(train_dir_seed + j) for j in range(train_seeds if ensemble else 1)]

                    object_ids, evaluator, initial_results = eval_model(model_params, daemon = daemon,
                        merton = merton, samuelson = samuelson, annuitize = annuitize, opal = opal,
                        model = model, evaluate = evaluate, warm_cache = warm_cache, default_object_id = (scenario_num, sub_num),
                        train_dirs = train_dirs, out = out, aid = aid, num_environments = num_environments, **kwargs)
                    initial_results['cid'] = control_params['cid']

                    for object_id in object_ids:
                        object_id_to_evaluator[object_id] = evaluator
                    evaluator_to_info[evaluator] = {'scenario_num': scenario_num, 'sub_num': sub_num, 'out': out, 'prefix': prefix}

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

                results[scenario_num].append(initial_results)

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

            try:

                res = evaluator.summarize()

                if res['couple']:
                    print('Couple certainty equivalent:', res['ce'], '+/-', res['ce_stderr'],
                        '(80% confidence interval:', res['consume10'], '-', str(res['consume90']) + ')', file = out)
                print('Evaluation certainty equivalent:', res['ce_individual'], '+/-', res['ce_stderr_individual'],
                    '(80% confidence interval:', res['consume10_individual'], '-', str(res['consume90_individual']) + ')', file = out, flush = True)

                plot(prefix, res['paths'], res['consume_pdf'], res['estate_pdf'])

                final_results = dict(results[scenario_num][sub_num], **{
                    'error': None,
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
                    'sample_paths': res['paths'],
                })

            except Exception as e:
                if daemon:
                    print_exc(file = stderr)
                    stderr.flush()
                any_exception = e
                error_msg = e.__class__.__name__ + ': ' + (str(e) or 'Exception encountered.')
                final_results = {
                    'aid': aid,
                    'cid': results[scenario_num][sub_num]['cid'],
                    'error': error_msg,
                }

            results[scenario_num][sub_num] = final_results

            #final_str = dumps(final_results, indent = 4, sort_keys = True)
            #with open(prefix + '.json', 'w') as w:
            #    w.write(final_str + '\n')

            # Allow evaluator to be garbage collected to conserve RAM and also allow agent actor process to be killed.
            del evaluator_to_info[evaluator]
            del evaluator

    if daemon and not warm_cache:

        failures = [scenario for scenario, result in zip(api, results) if any((sub_result['error'] != None for sub_result in result))]
        if failures:
            failures_str = dumps(failures, indent = 4, sort_keys = True)
            with open(result_seed_dir + '/failures.json', 'w') as w:
                w.write(failures_str + '\n')

    elif any_exception:

        raise any_exception

    return results

runner_cache = {}

def eval_model(eval_model_params, *, daemon, merton, samuelson, annuitize, opal, opal_file, redis_address, checkpoint_name,
    evaluate, warm_cache, eval_couple_net, eval_seed, eval_num_timesteps, eval_render,
    num_cpu, model, default_object_id, train_dirs, search_consume_initial_around, out,
    aid, num_workers, num_environments, num_trace_episodes, pdf_buckets):

    eval_seed += 1000000 # Use a different seed than might have been used during training.
    #set_global_seeds(eval_seed) # Not needed for Ray.

    env = make_fin_env(**eval_model_params, direct_action = not model)
    env = env.fin

    eval_model_params['display_returns'] = False # Only have at most one env display returns.

    skip_model = env.params.consume_policy != 'rl' and env.params.annuitization_policy != 'rl' and env.params.asset_allocation_policy != 'rl' and \
        (not env.params.real_bonds or env.params.real_bonds_duration != None) and \
        (not env.params.nominal_bonds or env.params.nominal_bonds_duration != None)

    obs = env.reset()

    remote_evaluators = None

    if merton or samuelson:

        consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
        asset_allocation = AssetAllocation(stocks = stocks_allocation, bills = 1 - stocks_allocation)
        initial_results = env.interpret_spending(consume_fraction, asset_allocation)

    elif annuitize:

        consume_initial = env.gi_sum() + env.p_sum() / (env.params.time_period + env.real_spia.premium(1, mwr = env.params.real_spias_mwr))
        consume_fraction_initial = consume_initial / env.p_plus_income()
        asset_allocation = AssetAllocation(stocks = 1)
        initial_results = env.interpret_spending(consume_fraction_initial, asset_allocation, real_spias_fraction = 1)

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

        consume_fraction, stocks_allocation = pi_opal(opal_data, env, obs)
        asset_allocation = AssetAllocation(stocks = stocks_allocation, iid_bonds = 1 - stocks_allocation)
        initial_results = env.interpret_spending(consume_fraction, asset_allocation)

    else:

        try:
            runner = runner_cache[train_dirs[0]]
        except KeyError:
            runner = TFRunner(train_dirs = train_dirs, checkpoint_name = checkpoint_name, eval_model_params = eval_model_params, couple_net = eval_couple_net,
                redis_address = redis_address, num_workers = num_workers, worker_seed = eval_seed, num_environments = num_environments, num_cpu = num_cpu).__enter__()
            if daemon: # Don't cache runner if not daemon as it prevents termination of Ray workers.
                runner_cache[train_dirs[0]] = runner
        remote_evaluators = runner.remote_evaluators

        action, = runner.run([obs])
        initial_results = env.interpret_action(action)

    initial_results = dict(initial_results, **{
        'error': None,
        'aid': aid,
        'rra': env.params.gamma_low,
        'asset_classes': initial_results['asset_allocation'].classes(),
        'asset_allocation': initial_results['asset_allocation'].as_list(),
        'pv_preretirement_income': env.preretirement_income_wealth if env.preretirement_years > 0 else None,
        'pv_retired_income': env.retired_income_wealth,
        'pv_future_taxes': env.pv_taxes,
        'portfolio_wealth': env.p_wealth,
    })

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

        evaluator = Evaluator(envs, eval_seed, eval_num_timesteps,
            remote_evaluators = remote_evaluators, render = eval_render, num_trace_episodes = num_trace_episodes, pdf_buckets = pdf_buckets)

        def pi(obss):

            if model:

                if skip_model:
                    action = None
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
                    t = ceil(life_expectancy / env.params.time_period) - 1
                    if t == 0:
                        consume_fraction = min(consume_fraction, 1 / env.params.time_period) # Bound may be exceeded in continuous time case.
                    results.append(env.encode_direct_action(consume_fraction, stocks = stocks_allocation, bills = 1 - stocks_allocation))
                return results

            elif annuitize:

                results = []
                for obs in obss:
                    consume_fraction = consume_fraction_initial if env.episode_length == 0 else 1 / env.params.time_period
                    results.append(env.encode_direct_action(consume_fraction, stocks = 1, real_spias_fraction = 1))
                return results

            elif opal:

                results = []
                for obs in obss:
                    consume_fraction, stocks_allocation = pi_opal(opal_data, env, obs)
                    results.append(env.encode_direct_action(consume_fraction, stocks = stocks_allocation, iid_bonds = 1 - stocks_allocation))
                return results

            else:

                assert False

        if search_consume_initial_around != None:

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

def plot(prefix, traces, consume_pdf, estate_pdf):

    with open(prefix + '-paths.csv', 'w') as f:
        csv_writer = writer(f)
        for trace in traces:
            for i, (age, alive_count, total_guaranteed_income, portfolio_wealth, consume, real_spias_purchase, nominal_spias_purchase, asset_allocation) in \
                enumerate(zip(trace['age'], trace['alive_count'], trace['total_guaranteed_income'], trace['portfolio_wealth'], trace['consume'],
                    trace['real_spias_purchase'], trace['nominal_spias_purchase'], trace['asset_allocation'])):

                couple_plot = alive_count == 2
                single_plot = alive_count == 1
                try:
                    if alive_count == 2 and trace['alive_count'][i + 1] == 1:
                        single_plot = True
                except KeyError:
                    pass
                csv_writer.writerow((age, int(couple_plot), int(single_plot), total_guaranteed_income, portfolio_wealth, consume,
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

    try:
        environ['AIPLANNER_FILE_PREFIX'] = prefix
        run([environ['AIPLANNER_HOME'] + '/ai/plot'], check = True)
    except CalledProcessError:
        assert not traces, 'Error ploting results.'

def main():
    parser = arg_parser(training = False)
    parser.add_argument('-d', '--daemon', action = "store_true", default = False)
    parser.add_argument('--api-content-length', type = int, default = None)
    boolean_flag(parser, 'stdin', default = False)
    boolean_flag(parser, 'merton', default = False)
    boolean_flag(parser, 'samuelson', default = False)
    boolean_flag(parser, 'annuitize', default = False)
    boolean_flag(parser, 'opal', default = False)
    parser.add_argument('--opal-file', default = 'opal-linear.csv')
    parser.add_argument('--redis-address')
    parser.add_argument('--models-dir')
    parser.add_argument('--gamma', action = 'append', type = float, default = [])
    parser.add_argument('--train-seeds', type = int, default = 1) # Number of seeds to evaluate.
    boolean_flag(parser, 'ensemble', default = False)
        # Whether to evaluate the average recommendation of the seeds or to evaluate the seeds individually in parallel.
    parser.add_argument('--checkpoint-name')
    boolean_flag(parser, 'evaluate', default = True) # Inference and simulation, otherwise inference only.
    boolean_flag(parser, 'warm-cache', default = True) # Pre-load tensorflow/Rllib models.
    boolean_flag(parser, 'eval-couple-net', default = True)
    parser.add_argument('--search-consume-initial-around', type = float)
        # Search for the initial consumption that maximizes the certainty equivalent using the supplied value as a hint as to where to search.
    parser.add_argument('--result-dir', default = 'results')
    parser.add_argument('--aid') # AIPlanner id.
    parser.add_argument('--num-workers', type = int, default = 1) # Number of remote processes for Ray evaluation. Zero for local evaluation.
    parser.add_argument('--num-environments', type = int, default = 100) # Number of parallel environments to use for a single model. Speeds up tensorflow.
    parser.add_argument('--num-trace-episodes', type = int, default = 5) # Number of sample traces to generate.
    parser.add_argument('--pdf-buckets', type = int, default = 20) # Number of non de minus buckets to use in computing consume probability density distribution.
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False, dump = False)
    if args['stdin']:
        args['daemon'] = True
    if not args['daemon']:
        assert args['api_content_length'] == None and not args['gamma']
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
            if args['models_dir'] != None and args['warm_cache']:
                for model_params, api in enumerate_model_params_api(args['gamma']):
                    model_params = dict(eval_model_params, **model_params)
                    eval_args = dict(args, api = api, permissive_api = True, eval_num_timesteps = 1)
                    eval_models(model_params, **eval_args)
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
                    assert api_content_length != None, 'No --api-content-length parameter.'
                    api_json = stdin.read(api_content_length)
                    api = loads(api_json)
                    assert len(api) <= 10000, 'Too many scenarios in a single request.'
                    results = {
                        'error': None,
                        'result': eval_models(eval_model_params, api = api, **args)
                    }
                except Exception as e:
                    print_exc(file = stderr)
                    stderr.flush()
                    results = {'error': e.__class__.__name__ + ': ' + (str(e) or 'Exception encountered.')}
                except SystemExit as e:
                    results = {'error': 'Invalid argument.'}
                results_str = dumps(results, sort_keys = True) + '\n'
                print('\nAIPlanner-Result')
                print('Content-Length:', len(results_str.encode('utf-8')))
                stdout.write(results_str)
                stdout.flush()

if __name__ == '__main__':
    main()
