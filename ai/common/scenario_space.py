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
    model_params['p_taxable_' + bonds_type + '_low'] = model_params['p_taxable_' + bonds_type + '_high'] = control_params['p_taxable_bonds']
    model_params['p_taxable_' + bonds_type + '_basis'] = control_params['p_taxable_bonds_basis']
    if bonds_type == 'real_bonds':
        assert model_params['real_bonds']
    elif bonds_type == 'nominal_bonds':
        assert model_params['nominal_bonds']

    if control_params['gammas'] is None:
        control_params['gammas'] = allowed_gammas

def force_preretirement_model(stage, spias, gamma):

    # Performance loss from using pre-retirement trained model in retirement is usually small, and it reduces the number of models we have to train.
    # Performance loss is larger when no spias and gamma >= 6, so use a separately trained retirement model then.
    return stage == 'retired' and (spias or gamma < 6)

def scenario_space_model_filename(model_params):

    stage = 'retired' if model_params['age_start'] >= max(50, model_params['age_retirement_low']) else 'preretirement'
        # Retirement model is trained starting from age 50.
    spias = model_params['real_spias'] or model_params['nominal_spias']
    spias_str = 'spias' if spias else 'no_spias'
    assert model_params['gamma_low'] == model_params['gamma_high'], "Can't evaluate a gamma range."
    gamma = model_params['gamma_low']
    if int(gamma) == gamma:
        gamma = int(gamma)
    assert gamma in allowed_gammas, 'gamma values must be selected from ' + allowed_gammas

    if force_preretirement_model(stage, spias, gamma):
        stage = 'preretirement'

    return 'aiplanner-' + stage + '-' + spias_str + '-gamma' + str(gamma) + '.tf'

def enumerate_model_params_api(gammas):

    return [({
        'age_start': 20 if stage == 'preretirement' else 100,
        'age_retirement_low': 67,
        'age_retirement_high': 67,
        'stocks_price_low': 1,
        'stocks_price_high': 1,
        'stocks_sigma_level_type': 'average',
        'real_short_rate_type': 'current',
        'inflation_short_rate_type': 'current',
    }, [{
        'spias': spias,
        'rra': [gamma for gamma in gammas if not force_preretirement_model(stage, spias, gamma)],
    }]) for stage in ('preretirement', 'retired') for spias in (False, True) if not all((force_preretirement_model(stage, spias, gamma) for gamma in gammas))]
