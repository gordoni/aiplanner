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

    global consume_prev

    if action != None:
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = action

    if env.params.consume_policy == 'constant':

        consume_fraction = env.params.consume_initial / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'pmt':

        consume = (env.gi_real + env.gi_nominal) * env.params.time_period + \
            _pmt(env.params.pmt_annual_return, env.life_expectancy[env.episode_length], env.p_notax)
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'guyton_rule2':

        if env.episode_length == 0:
            consume = env.params.consume_initial
        elif env.prev_ret >= env.prev_inflation:
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume_prev = consume
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
