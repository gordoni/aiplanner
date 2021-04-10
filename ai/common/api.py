# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from json import dumps
from math import log

def parse_api_scenario(api_scenario, *, permissive = False):

    def anything(name, value):
        return True

    def boolean(name, value):
        return type(value) == bool

    def number(name, value):
        return type(value) in [int, float]

    def string(name, value):
        return type(value) == str

    def enumeration(values):
        def f(name, value):
            return any((compare(name, value, schema) for schema in values))
        return f

    def array(element):
        def f(name, value):
            if not type(value) in [list, tuple]:
                return False
            for i, v in enumerate(value):
                check(name + ' element ' + str(i), v, element)
            return True
        return f

    def object(schema):
        def f(name, value):
            if not type(value) in [dict]:
                return False
            for n, v in value.items():
                try:
                    s = schema[n]
                except KeyError:
                    assert False, 'Unknown api parameter:' + name + ' ' + n
                check(name + ' ' + n, v, s)
            return True
        return f

    def compare(name, value, schema):
        return schema(name, value) if callable(schema) else value == schema

    def check(name, value, schema):
        if not compare(name, value, schema):
            assert False, 'Invalid api parameter value for' + name + ': ' + str(value)

    schema = object({
        'cid': anything,
        'customer_name': string,
        'scenario_name': string,

        'sex': enumeration(['female', 'male']),
        'sex2': enumeration(['female', 'male', None]),
        'age': number,
        'age2': number,
        'life_expectancy_additional': number,
        'life_expectancy_additional2': number,

        'age_retirement': number,
        'income_preretirement': number,
        'income_preretirement2': number,
        'income_preretirement_age_end': enumeration([number, None]),
        'income_preretirement_age_end2': enumeration([number, None]),
        'consume_preretirement': number,
        'have_401k': boolean,
        'have_401k2': boolean,

        'guaranteed_income': array(
            object({
                'type': string,
                'owner': enumeration(['self', 'spouse']),
                'start': enumeration([number, None]),
                'end': enumeration([number, None]),
                'payout': number,
                'inflation_adjustment': enumeration([number, 'cpi']),
                'joint': boolean,
                'payout_fraction': number,
                'source_of_funds': enumeration(['taxable', 'tax_deferred', 'tax_free']),
                'exclusion_period': number,
                'exclusion_amount': number,
            })
        ),

        'p_tax_deferred': number,
        'p_tax_free': number,
        'p_taxable_cash': number,
        'p_taxable_bonds': number,
        'p_taxable_stocks': number,
        'p_taxable_other': number,
        'p_taxable_bonds_basis': number,
        'p_taxable_stocks_basis': number,
        'p_taxable_other_basis': number,

        'observe_market_conditions': boolean,
        'stocks_price': number,
        'stocks_volatility': number,
        'nominal_short_rate': number,
        'real_short_rate': number,
        'inflation_short_rate': number,

        'spias': boolean,

        'rra': enumeration([None, array(number)]), # Must put None first as array() asserts if it doesn't match.

        'rl_stocks_max': number,

        'num_evaluate_timesteps': number,
        'num_sample_paths': number,
    })

    check('', api_scenario, schema)

    model_params = {}

    for name in [
        'sex',

        'consume_preretirement',

        'rl_stocks_max',
    ]:
        if name in api_scenario:
            model_params[name] = api_scenario[name]

    for name in [
        'income_preretirement_age_end',
        'income_preretirement_age_end2',
    ]:
        if name in api_scenario:
            model_params[name] = api_scenario[name] if api_scenario[name] is not None else -1

    if 'guaranteed_income' in api_scenario:
        model_params['guaranteed_income'] = dumps(api_scenario['guaranteed_income'])

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
    if api_scenario.get('sex2') is not None:
        model_params['sex2'] = api_scenario['sex2']
        try:
            model_params['age_start2_low'] = model_params['age_start2_high'] = api_scenario['age2']
        except KeyError:
            assert permissive, 'No age2 specified.'
    assert ('age_retirement' in api_scenario) or permissive, 'No age_retirement.'
    model_params['observe_stocks_price'] = api_scenario.get('observe_market_conditions', True)
    model_params['observe_stocks_volatility'] = api_scenario.get('observe_market_conditions', True)
    model_params['observe_interest_rate'] = api_scenario.get('observe_market_conditions', True)
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
    cash = api_scenario.get('p_taxable_cash', 0)
    model_params['p_taxable_other_low'] = model_params['p_taxable_other_high'] = api_scenario.get('p_taxable_other', 0) + cash
    model_params['p_taxable_stocks_basis'] = api_scenario.get('p_taxable_stocks_basis', api_scenario.get('p_taxable_stocks', 0))
    model_params['p_taxable_other_basis'] = api_scenario.get('p_taxable_other_basis', api_scenario.get('p_taxable_other', 0)) + cash
    model_params['p_taxable_stocks_basis_fraction_low'] = model_params['p_taxable_stocks_basis_fraction_high'] = 0
    model_params['p_taxable_real_bonds_basis_fraction_low'] = model_params['p_taxable_real_bonds_basis_fraction_high'] = 0
    model_params['p_taxable_nominal_bonds_basis_fraction_low'] = model_params['p_taxable_nominal_bonds_basis_fraction_high'] = 0
    model_params['p_taxable_other_basis_fraction_low'] = model_params['p_taxable_other_basis_fraction_high'] = 0

    model_params['couple_probability'] = int(api_scenario.get('sex2') is not None)

    control_params = {
        'cid': api_scenario.get('cid'),
        'spias': api_scenario.get('spias', True),
        'p_taxable_bonds': api_scenario.get('p_taxable_bonds', 0),
        'p_taxable_bonds_basis': api_scenario.get('p_taxable_bonds_basis', api_scenario.get('p_taxable_bonds', 0)),
        'gammas': [int(gamma) if int(gamma) == gamma else gamma for gamma in api_scenario['rra']] if api_scenario.get('rra') is not None else None,
    }

    return model_params, control_params
