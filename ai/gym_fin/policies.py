# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from json import loads

from ai.gym_fin.asset_allocation import AssetAllocation

def _pmt(rate, nper, pv):

    try:
        return pv * rate * (1 + rate) ** (nper - 1) / ((1 + rate) ** nper - 1)
    except ZeroDivisionError:
        return pv / nper

def bonds_type(env):

    assert sum(int(env.params.real_bonds) + int(env.params.nominal_bonds) + int(env.params.iid_bonds) + (env.params.bills)) == 1

    if env.params.real_bonds:
        return 'real_bonds'
    elif env.params.nominal_bonds:
        return 'nominal_bonds'
    elif env.params.iid_bonds:
        return 'iid_bonds'
    elif env.params.bills:
        return 'bills'
    else:
        assert False

def policy(env, action):

    global consume_rate_initial, consume_prev, life_expectancy_initial, p_initial, annuitized

    if action is not None:
        consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = action

    if env.params.consume_policy == 'constant':

        consume_fraction = env.params.consume_initial / env.p_plus_income

    elif env.params.consume_policy == 'percent_rule':

        if env.age < env.age_retirement:
            consume_fraction = 0
        else:
            if env.age < env.age_retirement + env.params.time_period:
                consume_rate_initial = env.params.consume_policy_fraction * env.p_wealth
            consume_fraction = (env.net_gi + consume_rate_initial) / env.p_plus_income

    elif env.params.consume_policy == 'guyton_rule2':

        assert env.age >= env.age_retirement

        if env.episode_length == 0:
            consume = env.params.consume_initial - env.net_gi
        elif env.prev_ret * env.prev_inflation >= 1:
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume_prev = consume
        consume += env.net_gi
        consume_fraction = consume / env.p_plus_income

    elif env.params.consume_policy == 'guyton_klinger':

        assert env.age >= env.age_retirement

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy_both[env.episode_length] + env.life_expectancy_one[env.episode_length]
        else:
            life_expectancy = env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period
        if env.episode_length == 0:
            consume = env.params.consume_initial - env.net_gi
            consume_rate_initial = consume / env.p_wealth
        else:
            consume = consume_prev
            if consume < 0.8 * consume_rate_initial * env.p_wealth:
                consume *= 1.1
            if consume > 1.2 * consume_rate_initial * env.p_wealth and life_expectancy > 15:
                consume *= 0.9
            if env.prev_ret * env.prev_inflation < 1 and consume > consume_rate_initial * env.p_wealth:
                consume /= env.prev_inflation
        consume_prev = consume
        consume += env.net_gi
        consume_fraction = consume / env.p_plus_income

    elif env.params.consume_policy == 'target_percentage':

        assert env.age >= env.age_retirement

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy_both[env.episode_length] + env.life_expectancy_one[env.episode_length]
        else:
            life_expectancy = max(1, env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period)
        if env.episode_length == 0:
            life_expectancy_initial = life_expectancy
            p_initial = env.p_wealth
            consume = env.params.consume_initial - env.net_gi
        elif _pmt(env.params.consume_policy_return, life_expectancy, env.p_wealth) >= \
            _pmt(env.params.consume_policy_return, life_expectancy_initial, p_initial):
            consume = consume_prev
        else:
            consume = consume_prev / env.prev_inflation
        consume_prev = consume
        consume += env.net_gi
        consume_fraction = consume / env.p_plus_income

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
        consume = env.net_gi + env.p_wealth / rmd_period * env.params.time_period
        consume_fraction = consume / env.p_plus_income

    elif env.params.consume_policy == 'pmt':

        if env.params.consume_policy_life_expectancy == None:
            life_expectancy = env.life_expectancy_both[env.episode_length] + env.life_expectancy_one[env.episode_length]
        else:
            life_expectancy = env.params.consume_policy_life_expectancy - env.episode_length * env.params.time_period
        life_expectancy = max(1, life_expectancy)
        consume = env.net_gi + _pmt(env.params.consume_policy_return, life_expectancy, env.p_wealth)
        consume_fraction = consume / env.p_plus_income

    consume_fraction = max(1e-6, min(consume_fraction, env.params.consume_policy_fraction_max / env.params.time_period))

    if env.params.annuitization_policy in ('age_real', 'age_nominal'):

        if env.episode_length == 0:
            annuitized = False

        if env.couple:
            min_age = min(env.age, env.age2)
            max_age = max(env.age, env.age2)
        else:
            min_age = max_age = env.age2 if env.only_alive2 else env.age

        spias_allowed = (env.params.couple_spias or not env.couple) and min_age >= env.params.spias_permitted_from_age and max_age <= env.params.spias_permitted_to_age
        spias = spias_allowed and min_age >= env.params.annuitization_policy_age
        real_spias_fraction = env.params.annuitization_policy_annuitization_fraction if spias and env.params.annuitization_policy == 'age_real' else 0
        nominal_spias_fraction =  env.params.annuitization_policy_annuitization_fraction if spias and env.params.annuitization_policy == 'age_nominal' else 0

        if real_spias_fraction or nominal_spias_fraction:
            annuitized = True

    elif env.params.annuitization_policy == 'none':

        real_spias_fraction = 0
        nominal_spias_fraction = 0

    if env.params.asset_allocation_policy == 'age-in-bonds':

        bonds = max(env.age / 100, 1)
        asset_allocation = AssetAllocation(**{'stocks': 1 - bonds, bonds_type(env): bonds})

    elif env.params.asset_allocation_policy == 'glide-path':

        t = env.age - env.age_retirement
        t0, stocks0 = env.params.asset_allocation_glide_path[0]
        for t1, stocks1 in env.params.asset_allocation_glide_path:
            if t < t1:
                break
            t0, stocks0 = t1, stocks1
        if t0 == t1:
            stocks = stocks0
        else:
            t = min(max(t0, t), t1)
            stocks = (stocks0 * (t1 - t) + stocks1 * (t - t0)) / (t1 - t0)
        asset_allocation = AssetAllocation(**{'stocks': stocks, bonds_type(env): 1 - stocks})

    elif env.params.asset_allocation_policy != 'rl':

        asset_allocation = loads(env.params.asset_allocation_policy)
        asset_allocation = AssetAllocation(**asset_allocation)

    if env.params.asset_allocation_annuitized_policy != 'asset_allocation_policy' and annuitized:

        asset_allocation = loads(env.params.asset_allocation_annuitized_policy)
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
