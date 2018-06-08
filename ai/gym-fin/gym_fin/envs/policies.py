# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from gym_fin.envs.asset_allocation import AssetAllocation

def _pmt(rate, nper, pv):

    try:
        return pv * rate * (1 + rate) ** (nper - 1) / ((1 + rate) ** nper - 1)
    except ZeroDivisionError:
        return pv / nper

def policy(env, action):

    global consume_prev, life_expectancy_initial, p_notax_initial

    if action != None:
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = action

    if env.params.consume_policy == 'constant':

        consume_fraction = env.params.consume_initial / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'guyton_rule2':

        if env.episode_length == 0:
            consume = env.params.consume_initial
        elif env.prev_ret * env.prev_inflation >= 1:
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume = max(consume, env.gi_real + env.gi_nominal)
        consume_prev = consume
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'target_percentage':

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy[env.episode_length]
        else:
            life_expectancy = max(1, env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period)
        if env.episode_length == 0:
            life_expectancy_initial = life_expectancy
            p_notax_initial = env.p_notax
            consume = env.params.consume_initial
        elif _pmt(env.params.consume_policy_return, life_expectancy, env.p_notax) >= \
            _pmt(env.params.consume_policy_return, life_expectancy_initial, p_notax_initial):
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume = max(consume, env.gi_real + env.gi_nominal)
        consume_prev = consume
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'pmt':

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy[env.episode_length]
        else:
            life_expectancy = max(1, env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period)
        consume = (env.gi_real + env.gi_nominal) * env.params.time_period + _pmt(env.params.consume_policy_return, life_expectancy, env.p_notax)
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    if env.params.annuitization_policy == 'none':

        real_spias_fraction = 0
        nominal_spias_fraction = 0

    if env.params.asset_allocation_policy == 'age-in-nominal-bonds':

        bonds = max(env.age / 100, 1)
        stocks = 1 - bonds
        asset_allocation = AssetAllocation(stocks = stocks, nominal_bonds = bonds)

    elif env.params.asset_allocation_policy != 'rl':

        asset_allocation = {}
        exec(env.params.asset_allocation_policy, None, asset_allocation)
        asset_allocation = AssetAllocation(**asset_allocation)

    if env.params.real_bonds:
        if env.params.real_bonds_duration != None:
            real_bonds_duration = env.params.real_bonds_duration
    else:
        real_bonds_duration = None

    if env.params.nominal_bonds:
        if env.params.nominal_bonds_duration != None:
            nominal_bonds_duration = env.params.nominal_bonds_duration
    else:
        nominal_bonds_duration = None

    return consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration
