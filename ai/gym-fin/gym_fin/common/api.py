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

def parse_api_scenario(api_scenario):

    for name in api_scenario.keys():
        if not name in [
            'id',

            'stocks_price',
            'nominal_short_rate',
            'inflation_short_rate',

            'sex',
            'sex2',
            'age_start',
            'age_start2',
            'life_expectancy_additional',
            'life_expectancy_additional2',

            'guaranteed_income',

            'p_tax_deferred',
            'p_tax_free',
            'p_taxable_bonds',
            'p_taxable_stocks',
            'p_taxable_stocks_basis',

            'age_retirement',
            'income_preretirement',
            'income_preretirement2',
            'consume_preretirement',
            'have_401k',
            'have_401k2',
            'spias',

            'gammas',
        ]:
            assert False, 'Unknown api parameter: ' + name

    for name in api_scenario.get('guaranteed_income', []):
        if not name in [
            'type',
            'owner',
            'age',
            'final',
            'probability',
            'payout',
            'inflation_adjustment',
            'joint',
            'payout_fraction',
            'source_of_funds',
            'exclusion_period',
            'exclusion_amount',
        ]:
            assert False, 'Unknown api guaranteed income field: ' + name

    model_params = dict(api_scenario)
    
    for name in [
        'id',
        'nominal_short_rate',
        'inflation_short_rate',
        'spias',
        'gammas',
    ]:
        try:
            del model_params[name]
        except KeyError:
            pass

    if 'nominal_short_rate' in api_scenario:
        assert 'inflation_short_rate' in api_scenario, 'nominal_short_rate requires a value for inflation_short_rate also be specified.'
        model_params['real_short_rate_type'] = 'value'
        model_params['real_short_rate_value'] = log(1 + model_params['nominal_short_rate']) - log(1 + model_params['inflation_short_rate'])
    if 'inflation_short_rate' in api_scenario:
        model_params['real_short_rate_type'] = 'value'
        model_params['real_short_rate_value'] = log(1 + model_params['nominal_short_rate']) - log(1 + model_params['inflation_short_rate'])

    model_params['couple_probability'] = int(api_scenario.get('sex2') != None)

    control_params = {
        'id': api_scenario.get('id'),
        'spias': api_scenario.get('spias', False),
        'gammas': api_scenario.get('gammas', None),
    }

    return model_params, control_params
