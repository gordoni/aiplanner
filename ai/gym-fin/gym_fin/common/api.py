# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import log

def parse_api_scenario(api_scenario, *, permissive = False):

    for name in api_scenario.keys():
        if not name in [
            'cid',

            'sex',
            'sex2',
            'age',
            'age2',
            'life_expectancy_additional',
            'life_expectancy_additional2',

            'age_retirement',
            'income_preretirement',
            'income_preretirement2',
            'income_preretirement_age_end',
            'income_preretirement_age_end2',
            'consume_preretirement',
            'have_401k',
            'have_401k2',

            'guaranteed_income',

            'p_tax_deferred',
            'p_tax_free',
            'p_taxable_bonds',
            'p_taxable_stocks',
            'p_taxable_stocks_basis',

            'stocks_price',
            'stocks_volatility',
            'nominal_short_rate',
            'real_short_rate',
            'inflation_short_rate',

            'spias',

            'rra',

            'num_evaluate_timesteps',
            'num_sample_paths',
        ]:
            assert False, 'Unknown api parameter: ' + name

    for guaranteed_income in api_scenario.get('guaranteed_income', []):
        for name in guaranteed_income.keys():
            if not name in [
                'type',
                'owner',
                'start',
                'end',
                'payout',
                'inflation_adjustment',
                'joint',
                'payout_fraction',
                'source_of_funds',
                'exclusion_period',
                'exclusion_amount',
            ]:
                assert False, 'Unknown api guaranteed income field: ' + name

    model_params = {}

    for name in [
        'sex',

        'income_preretirement_age_end',
        'income_preretirement_age_end2',
        'consume_preretirement',

        'guaranteed_income',
    ]:
        if name in api_scenario:
            model_params[name] = api_scenario[name]

    for name in [
        'life_expectancy_additional',
        'life_expectancy_additional2',

        'age_retirement',
        'income_preretirement',
        'income_preretirement2',
        'have_401k',
        'have_401k2',

        'p_tax_deferred',
        'p_tax_free',
        'p_taxable_stocks',

        'stocks_price',
    ]:
        if name in api_scenario:
            model_params[name + '_low'] = model_params[name + '_high'] = api_scenario[name]

    try:
        model_params['age_start'] = api_scenario['age']
    except KeyError:
        assert permissive, 'No age specified.'
    if api_scenario.get('sex2') != None:
        model_params['sex2'] = api_scenario['sex2']
        try:
            model_params['age_start2_low'] = model_params['age_start2_high'] = api_scenario['age2']
        except KeyError:
            assert permissive, 'No age2 specified.'
    assert ('age_retirement' in api_scenario) or permissive, 'No age_retirement.'
    if 'stocks_volatility' in api_scenario:
        model_params['stocks_sigma_level_type'] = 'value'
        model_params['stocks_sigma_level_value'] = api_scenario['stocks_volatility']
    assert sum(x in api_scenario for x in ['real_short_rate', 'nominal_short_rate', 'inflation_short_rate']) <= 2, \
        "Specify at most two of real, nominal, and inflation short rates."
    if 'real_short_rate' in api_scenario:
        model_params['real_short_rate_type'] = 'value'
        model_params['real_short_rate_value'] = log(1 + api_scenario['real_short_rate'])
    if 'inflation_short_rate' in api_scenario:
        model_params['inflation_short_rate_type'] = 'value'
        model_params['inflation_short_rate_value'] = log(1 + api_scenario['inflation_short_rate'])
    if 'nominal_short_rate' in api_scenario:
        if 'real_short_rate' in api_scenario:
            model_params['inflation_short_rate_type'] = 'value'
            model_params['inflation_short_rate_value'] = log(1 + api_scenario['nominal_short_rate']) - log(1 + api_scenario['real_short_rate'])
        elif 'inflation_short_rate' in api_scenario:
            model_params['real_short_rate_type'] = 'value'
            model_params['real_short_rate_value'] = log(1 + api_scenario['nominal_short_rate']) - log(1 + api_scenario['inflation_short_rate'])
        else:
            assert False, 'nominal_short_rate requires a value for real_short_rate or inflation_short_rate also be specified.'
    if 'p_taxable_stocks_basis' in api_scenario:
        try:
            p_taxable_stocks_basis_fraction = api_scenario['p_taxable_stocks_basis'] / api_scenario['p_taxable_stocks']
        except ZeroDivisionError:
            assert api_scenario['p_taxable_stocks_basis'] == 0, 'Zero stocks must have a zero cost basis.'
            p_taxable_stocks_basis_fraction = 0
    else:
        p_taxable_stocks_basis_fraction = 1
    model_params['p_taxable_stocks_basis_fraction_low'] = model_params['p_taxable_stocks_basis_fraction_high'] = p_taxable_stocks_basis_fraction

    model_params['couple_probability'] = int(api_scenario.get('sex2') != None)

    control_params = {
        'cid': api_scenario.get('cid'),
        'spias': api_scenario.get('spias', True),
        'p_taxable_bonds': api_scenario.get('p_taxable_bonds', 0),
        'gammas': [int(gamma) if int(gamma) == gamma else gamma for gamma in api_scenario['rra']] if api_scenario.get('rra') != None else None,
    }

    return model_params, control_params
