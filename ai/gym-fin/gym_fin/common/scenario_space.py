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

spia_type = 'nominal_spias'

def scenario_space_update_params(model_params, control_params):

    model_params[spia_type] = control_params['spias']

    if control_params['gammas'] == None:
        control_params['gammas'] = allowed_gammas

def scenario_space_model_filename(model_params):

    spias = 'spias' if model_params['real_spias'] or model_params['nominal_spias'] else 'no_spias'
    retired = 'retired' if model_params['age'] >= model_params['age_retirement'] else 'preretirement'
    assert model_params['gamma_low'] == model_params['gamma_high'], "Can't evaluate a gamma range."
    gamma = model_params['gamma_low']
    if int(gamma) == gamma:
        gamma = int(gamma)
    assert gamma in allowed_gammas, 'gamma values must be selected from ' + allowed_gammas

    return 'aiplanner-' + retired + '-' + spias + '-gamma' + str(gamma) + '.tf'

def enumerate_model_params_api(gamma):

    gammas = [gamma] if gamma != None else allowed_gammas

    return [({
        'age': age,
        'age_retirement': 65,
    }, [{
        'spias': spias,
        'gammas': gammas,
    }]) for age in (20, 100) for spias in (False, True)]
