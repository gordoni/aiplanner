# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

allowed_gammas = [1.5, 3, 6]

spias_type = 'nominal_spias'
bonds_type = 'real_bonds'

def scenario_space_update_params(model_params, control_params):

    model_params[spias_type] = control_params['spias']
    model_params['p_taxable_' + bonds_type] = control_params['p_taxable_bonds']
    model_params['p_taxable_' + bonds_type + '_basis'] = control_params['p_taxable_bonds_basis']
    if bonds_type == 'real_bonds':
        assert model_params['real_bonds']
    elif bonds_type == 'nominal_bonds':
        assert model_params['nominal_bonds']

    if control_params['gammas'] == None:
        control_params['gammas'] = allowed_gammas

def scenario_space_model_filename(model_params):

    spias = 'spias' if model_params['real_spias'] or model_params['nominal_spias'] else 'no_spias'
    retired = 'retired' if model_params['age_start'] >= max(50, model_params['age_retirement_low']) else 'preretirement'
        # Retirement model is trained starting from age 50.
    assert model_params['gamma_low'] == model_params['gamma_high'], "Can't evaluate a gamma range."
    gamma = model_params['gamma_low']
    if int(gamma) == gamma:
        gamma = int(gamma)
    assert gamma in allowed_gammas, 'gamma values must be selected from ' + allowed_gammas

    return 'aiplanner-' + retired + '-' + spias + '-gamma' + str(gamma) + '.tf'

def enumerate_model_params_api(gammas):

    return [({
        'age_start': age,
        'age_retirement_low': 65,
        'age_retirement_high': 65,
        'stocks_price_low': 1,
        'stocks_price_high': 1,
        'stocks_sigma_level_type': 'average',
        'real_short_rate_type': 'current',
        'inflation_short_rate_type': 'current',
    }, [{
        'spias': spias,
        'rra': gammas,
    }]) for age in (20, 100) for spias in (False, True)]
