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
from json import dumps
from math import ceil, exp, sqrt
from os import chmod, environ, getpriority, mkdir, PRIO_PROCESS, setpriority
from os.path import exists
from subprocess import run

from baselines.common import boolean_flag
from baselines.common.misc_util import set_global_seeds

from gym_fin.envs.asset_allocation import AssetAllocation
from gym_fin.envs.model_params import load_params_file
from gym_fin.envs.policies import policy
from gym_fin.common.cmd_util import arg_parser, fin_arg_parse, make_fin_env
from gym_fin.common.evaluator import Evaluator
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
    # obs is currently ignored in favor of direcct env lookups.
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

def eval_models(eval_model_params, *, train_seeds, nice, train_seed, model_dir, result_dir, **kwargs):

    priority = getpriority(PRIO_PROCESS, 0)
    priority += nice
    setpriority(PRIO_PROCESS, 0, priority)

    try:
        mkdir(result_dir)
    except FileExistsError:
        pass

    object_id_to_evaluator = {}
    evaluator_to_info = {}
    for i in range(train_seeds):

        train_dir_seed = train_seed + i
        train_dir = model_dir + '/seed_' + str(train_dir_seed)
        result_seed_dir = result_dir + '/seed_' + str(train_dir_seed)

        try:
            mkdir(result_seed_dir)
        except FileExistsError:
            pass

        out = open(result_seed_dir + '/eval.log', 'w')

        object_ids, evaluator = eval_model(eval_model_params, model_dir = model_dir, train_seed = train_dir_seed, train_dir = train_dir,
            result_seed_dir = result_seed_dir, out = out, **kwargs)

        for object_id in object_ids:
            object_id_to_evaluator[object_id] = evaluator
        evaluator_to_info[evaluator] = {'out': out, 'prefix': result_seed_dir + '/aiplanner'}

    any_exception = None
    object_ids = list(object_id_to_evaluator.keys())
    while object_ids:

        if all(type(id) == int for id in object_ids):
            object_id = pop(object_ids)
        else:
            import ray
            (object_id, ), object_ids = ray.wait(object_ids)

        evaluator = object_id_to_evaluator[object_id]
        del object_id_to_evaluator[object_id]
        if evaluator not in object_id_to_evaluator.values():

            info = evaluator_to_info[evaluator]
            out = info['out']
            prefix = info['prefix']

            try:

                ce, ce_stderr, low, high = evaluator.summarize()

                if evaluator.couple:
                    print('Couple certainty equivalent:', ce, '+/-', ce_stderr, '(80% confidence interval:', low, '-', str(high) + ')', file = out)
                print('Evaluation certainty equivalent:', evaluator.indiv_ce, '+/-', evaluator.indiv_ce_stderr,
                    '(80% confidence interval:', evaluator.indiv_low, '-', str(evaluator.indiv_high) + ')', file = out)

                plot(prefix, evaluator.trace, evaluator.consume_pdf)

                final_data = {
                    'error': None,
                    'ce': ce,
                    'ce_stderr': ce_stderr,
                    'ce_low': low,
                    'ce_high': high,
                    'consume_preretirement': evaluator.consume_preretirement,
                    'preretirement_ppf': evaluator.preretirement_ppf,
                }
                exception = None

            except Exception as e:
                exception = any_exception = e
                error_msg = str(e)
                if not error_msg:
                    error_msg = e.__class__.__name__ + ' exception encountered.'
                final_data = {
                    'error': error_msg,
                }

            final_str = dumps(final_data)
            with open(prefix + '-final.json', 'w') as w:
                w.write(final_str)

            # Allow evaluator to be garbage collected to conserve RAM and also allow agent actor process to be killed.
            del evaluator_to_info[evaluator]
            del evaluator

    if any_exception:
        raise any_exception

def eval_model(eval_model_params, *, merton, samuelson, annuitize, opal, opal_file, redis_address, checkpoint_name,
    eval_couple_net, eval_seed, eval_num_timesteps, eval_render,
    num_cpu, model_dir, train_seed, train_dir, search_consume_initial_around, result_seed_dir, out, num_trace_episodes, num_workers, num_environments, pdf_buckets):

    assert sum((model_dir != 'aiplanner.tf', merton, samuelson, annuitize, opal)) <= 1
    model = not (merton or samuelson or annuitize or opal)

    eval_seed += 1000000 # Use a different seed than might have been used during training.
    set_global_seeds(eval_seed)

    if model:
        train_model_params = load_params_file(model_dir + '/params.txt')
        eval_model_params['action_space_unbounded'] = train_model_params['action_space_unbounded']
        eval_model_params['observation_space_ignores_range'] = train_model_params['observation_space_ignores_range']
    else:
        num_environments = 1
        eval_model_params['action_space_unbounded'] = True
        eval_model_params['observation_space_ignores_range'] = False

    envs = []
    for _ in range(num_environments):
        envs.append(make_fin_env(**eval_model_params, direct_action = not model))
        eval_model_params['display_returns'] = False # Only have at most one env display returns.
    env = envs[0].unwrapped

    if env.params.consume_policy != 'rl' and env.params.annuitization_policy != 'rl' and env.params.asset_allocation_policy != 'rl' and \
        (not env.params.real_bonds or env.params.real_bonds_duration != None) and \
        (not env.params.nominal_bonds or env.params.nominal_bonds_duration != None):
        model = False

    obs = env.reset()

    remote_evaluators = None

    if merton or samuelson:

        consume_fraction, stocks_allocation = pi_merton(env, obs, continuous_time = merton)
        asset_allocation = AssetAllocation(stocks = stocks_allocation, bills = 1 - stocks_allocation)
        interp = env.interpret_spending(consume_fraction, asset_allocation)

    elif annuitize:

        consume_initial = env.gi_sum() + env.p_sum() / (env.params.time_period + env.real_spia.premium(1, mwr = env.params.real_spias_mwr))
        consume_fraction_initial = consume_initial / env.p_plus_income()
        asset_allocation = AssetAllocation(stocks = 1)
        interp = env.interpret_spending(consume_fraction_initial, asset_allocation, real_spias_fraction = 1)

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
        interp = env.interpret_spending(consume_fraction, asset_allocation)

    else:

        ray_checkpoints = glob(train_dir + '/*/checkpoint_*')
        if ray_checkpoints:
            if not checkpoint_name:
                checkpoint_name = 'checkpoint_' + str(sorted(int(ray_checkpoint.split('_')[-1]) for ray_checkpoint in ray_checkpoints)[-1])
            tf_dir, = glob(train_dir + '/*/' + checkpoint_name)
            import ray
            if not ray.is_initialized():
                ray.init(redis_address = redis_address)
        else:
            if not checkpoint_name:
                checkpoint_name = 'tensorflow'
            tf_dir = train_dir + '/' + checkpoint_name
        runner = TFRunner(tf_dir = tf_dir, eval_model_params = eval_model_params, couple_net = eval_couple_net,
            num_workers = num_workers, num_cpu = num_cpu).__enter__()
        remote_evaluators = runner.remote_evaluators

        action, = runner.run([obs], policy_graph = runner.local_policy_graph)
        interp = env.interpret_action(action)

    interp['asset_classes'] = interp['asset_allocation'].classes()
    interp['asset_allocation'] = interp['asset_allocation'].as_list()
    interp['name'] = env.params.name
    interp['pv_guaranteed_income'] = sum(env.pv_income.values())
    interp['p'] = env.p_sum()
    interp['pv_preretirement'] = env.pv_income_preretirement + env.pv_income_preretirement2 - env.pv_consume_preretirement
    interp_str = dumps(interp)
    with open(result_seed_dir + '/aiplanner-initial.json', 'w') as w:
        w.write(interp_str)

    print('Initial properties for first episode:', file = out)
    print('    Consume:', interp['consume'], file = out)
    print('    Asset allocation:', interp['asset_allocation'], file = out)
    print('    401(k)/IRA contribution:', interp['retirement_contribution'], file = out)
    print('    Real income annuities purchase:', interp['real_spias_purchase'], file = out)
    print('    Nominal income annuities purchase:', interp['nominal_spias_purchase'], file = out)
    print('    Real bonds duration:', interp['real_bonds_duration'], file = out)
    print('    Nominal bonds duration:', interp['nominal_bonds_duration'], file = out)

    print(file = out)

    evaluator = Evaluator(envs, eval_seed, eval_num_timesteps,
        remote_evaluators = remote_evaluators, render = eval_render, num_trace_episodes = num_trace_episodes, pdf_buckets = pdf_buckets)

    def pi(obss):

        if model:

            action = runner.run(obss, policy_graph = runner.local_policy_graph)
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

            return None

    if search_consume_initial_around != None:

        f_cache = {}

        def f(x):

            try:

                return f_cache[x]

            except KeyError:

                print('    Consume: ', x)
                for e in envs:
                    e.unwrapped.params.consume_initial = x
                evaluator.evaluate(pi)
                f_x, tol_x, _, _ = evaluator.summarize()
                results = (f_x, tol_x)
                f_cache[x] = results
                return results

        x, f_x = gss(f, search_consume_initial_around / 2, search_consume_initial_around * 2)
        print('    Consume: ', x)
        for e in envs:
            e.unwrapped.params.consume_initial = x

    object_ids = evaluator.evaluate(pi) or [train_seed]

    runner.__exit__(None, None, None)

    return object_ids, evaluator

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

def plot(prefix, traces, consume_pdf):

    with open(prefix + '-paths.csv', 'w') as f:
        csv_writer = writer(f)
        for trace in traces:
            for i, step in enumerate(trace):
                couple_plot = step['alive_count'] == 2
                single_plot = step['alive_count'] == 1
                try:
                    if step['alive_count'] == 2 and trace[i + 1]['alive_count'] == 1:
                        single_plot = True
                except KeyError:
                    pass
                aa = step['asset_allocation']
                aa = () if aa == None else aa.as_list()
                csv_writer.writerow((step['age'], int(couple_plot), int(single_plot), step['gi_sum'], step['p_sum'], step['consume'],
                                     step['real_spias_purchase'], step['nominal_spias_purchase'], *aa))
            csv_writer.writerow(())

    with open(prefix + '-consume-pdf.csv', 'w') as f:
        csv_writer = writer(f)
        csv_writer.writerows(consume_pdf)

    environ['AIPLANNER_FILE_PREFIX'] = prefix
    run([environ['AIPLANNER_HOME'] + '/ai/plot'], check = True)

def main():
    parser = arg_parser()
    boolean_flag(parser, 'merton', default = False)
    boolean_flag(parser, 'samuelson', default = False)
    boolean_flag(parser, 'annuitize', default = False)
    boolean_flag(parser, 'opal', default = False)
    parser.add_argument('--opal-file', default = 'opal-linear.csv')
    parser.add_argument('--redis-address')
    parser.add_argument('--train-seeds', type = int, default = 1) # Number of possibly parallel seeds to evaluate.
    parser.add_argument('--checkpoint-name')
    boolean_flag(parser, 'eval-couple-net', default = True)
    parser.add_argument('--search-consume-initial-around', type = float)
        # Search for the initial consumption that maximizes the certainty equivalent using the supplied value as a hint as to where to search.
    parser.add_argument('--result-dir', default = 'results')
    parser.add_argument('--num-trace-episodes', type = int, default = 5)
    parser.add_argument('--num-workers', type = int, default = 1) # Number of remote processes for Ray evaluation. Zero for local evaluation.
    parser.add_argument('--num-environments', type = int, default = 10) # Number of parallel environments to use for a single model. Speeds up tensor flow.
    parser.add_argument('--pdf-buckets', type = int, default = 20) # Number of non de minus buckets to use in computing consume probability density distribution.
    training_model_params, eval_model_params, args = fin_arg_parse(parser, training = False)
    eval_models(eval_model_params, **args)

if __name__ == '__main__':
    main()
