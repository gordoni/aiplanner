# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from json import loads

from gym_fin.envs.asset_allocation import AssetAllocation

def _pmt(rate, nper, pv):

    try:
        return pv * rate * (1 + rate) ** (nper - 1) / ((1 + rate) ** nper - 1)
    except ZeroDivisionError:
        return pv / nper

def policy(env, action):

    global consume_rate_initial, consume_prev, life_expectancy_initial, p_initial

    if action is not None:
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = action

    if env.params.consume_policy == 'constant':

        consume_fraction = env.params.consume_initial / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'guyton_rule2':

        if env.episode_length == 0:
            consume = env.params.consume_initial - env.gi_sum() * env.params.time_period
        elif env.prev_ret * env.prev_inflation >= 1:
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume_prev = consume
        consume += env.gi_sum() * env.params.time_period
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'guyton_klinger':

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy_both[env.episode_length] + env.life_expectancy_one[env.episode_length]
        else:
            life_expectancy = env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period
        if env.episode_length == 0:
            consume = env.params.consume_initial - env.gi_sum() * env.params.time_period
            consume_rate_initial = consume / env.p_sum()
        else:
            consume = consume_prev
            if consume < 0.8 * consume_rate_initial * env.p_sum():
                consume *= 1.1
            if consume > 1.2 * consume_rate_initial * env.p_sum() and life_expectancy > 15:
                consume *= 0.9
            if env.prev_ret * env.prev_inflation < 1 and consume > consume_rate_initial * env.p_sum():
                consume /= env.prev_inflation
        consume_prev = consume
        consume += env.gi_sum() * env.params.time_period
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'target_percentage':

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy_both[env.episode_length] + env.life_expectancy_one[env.episode_length]
        else:
            life_expectancy = max(1, env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period)
        if env.episode_length == 0:
            life_expectancy_initial = life_expectancy
            p_initial = env.p_sum()
            consume = env.params.consume_initial - env.gi_sum() * env.params.time_period
        elif _pmt(env.params.consume_policy_return, life_expectancy, env.p_sum()) >= \
            _pmt(env.params.consume_policy_return, life_expectancy_initial, p_initial):
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume_prev = consume
        consume += env.gi_sum() * env.params.time_period
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'extended_rmd':

        extended_rmd_table = {
            50: 46.5, # IRS Pub. 590B Table II diagonal.
            51: 45.5,
            52: 44.6,
            53: 43.6,
            54: 42.6,
            55: 41.6,
            56: 40.7,
            57: 39.7,
            58: 38.7,
            59: 37.8,
            60: 36.8,
            61: 35.8,
            62: 34.9,
            63: 33.9,
            64: 33.0,
            65: 32.0,
            66: 31.1,
            67: 30.2,
            68: 29.2,
            69: 28.3,
            70: 27.4, # IRS Pub. 590B Table III.
            71: 26.5,
            72: 25.6,
            73: 24.7,
            74: 23.8,
            75: 22.9,
            76: 22.0,
            77: 21.2,
            78: 20.3,
            79: 19.5,
            80: 18.7,
            81: 17.9,
            82: 17.1,
            83: 16.3,
            84: 15.5,
            85: 14.8,
            86: 14.1,
            87: 13.4,
            88: 12.7,
            89: 12.0,
            90: 11.4,
            91: 10.8,
            92: 10.2,
            93: 9.6,
            94: 9.1,
            95: 8.6,
            96: 8.1,
            97: 7.6,
            98: 7.1,
            99: 6.7,
            100: 6.3,
            101: 5.9,
            102: 5.5,
            103: 5.2,
            104: 4.9,
            105: 4.5,
            106: 4.2,
            107: 3.9,
            108: 3.7,
            109: 3.4,
            110: 3.1,
            111: 2.9,
            112: 2.6,
            113: 2.4,
            114: 2.1,
            115: 1.9,
        }

        assert env.alive_single[env.episode_length] != None or env.age == env.age2
        rmd_period = extended_rmd_table[min(int(env.age), max(extended_rmd_table.keys()))]
        consume = (env.gi_sum() + env.p_sum() / rmd_period) * env.params.time_period
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    elif env.params.consume_policy == 'pmt':

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy_both[env.episode_length] + env.life_expectancy_one[env.episode_length]
        else:
            life_expectancy = env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period
        life_expectancy = max(1, life_expectancy)
        consume = env.gi_sum() * env.params.time_period + _pmt(env.params.consume_policy_return, life_expectancy, env.p_sum())
        consume_fraction = consume / env.p_plus_income()
        consume_fraction = min(consume_fraction, 1 / env.params.time_period)

    if env.params.annuitization_policy == 'age_real':

        if env.alive_single[env.episode_length] == None:
            min_age = min(env.age, env.age2)
        else:
            min_age = env.age

        spias_allowed = (env.params.couple_spias or env.alive_single[env.episode_length] != None) and min_age >= env.params.spias_permitted_from_age
        real_spias_fraction = 1 if spias_allowed and min_age >= env.params.annuitization_policy_age_real else 0
        nominal_spias_fraction = 0

    elif env.params.annuitization_policy == 'none':

        real_spias_fraction = 0
        nominal_spias_fraction = 0

    if env.params.asset_allocation_policy == 'age-in-nominal-bonds':

        bonds = max(env.age / 100, 1)
        stocks = 1 - bonds
        asset_allocation = AssetAllocation(stocks = stocks, nominal_bonds = bonds)

    elif env.params.asset_allocation_policy != 'rl':

        asset_allocation = loads(env.params.asset_allocation_policy)
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
