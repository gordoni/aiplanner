# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from django.core.exceptions import ValidationError
from django.forms import CharField, FloatField, Form, NumberInput
from django.shortcuts import redirect, render

from gym_fin.common.cmd_util import arg_parser, fin_arg_parse
from gym_fin.envs.fin_env import FinEnv
from gym_fin.envs.model_params import ModelParams

class HomeForm(Form):

    name = CharField(min_length = 1)
    qualifications = CharField(min_length = 2)
    software = CharField(required = False)

def home(request):

    errors_present = False

    if request.method == 'POST':

        home_form = HomeForm(request.POST)
        if home_form.is_valid():
            data = home_form.cleaned_data
            print(data['name'], data['qualifications'], data['software'])
            return redirect('reset')
        else:
            errors_present = True

    else:

        home_form = HomeForm()

    return render(request, 'home.html', {
        'errors_present': errors_present,
        'home_form': home_form,
    })

def reset(request):

    global obs #XXX

    obs = env.reset()

    return render(request, 'reset.html')

class StepForm(Form):

    def clean(self):

        cleaned_data = super().clean()
        try:
            s = cleaned_data['stocks'] + cleaned_data['real_bonds'] + cleaned_data['nominal_bonds']
        except KeyError:
            s = None
        if s != 100:
            raise ValidationError('Asset allocation must add up to 100%.')
        return cleaned_data

    consume = FloatField(min_value = 0)
    real_spias = FloatField(min_value = 0, initial = 0)
    nominal_spias = FloatField(min_value = 0, initial = 0)
    stocks = FloatField(min_value = 0, max_value = 100)
    real_bonds = FloatField(min_value = 0, max_value = 100, initial = 0)
    nominal_bonds = FloatField(min_value = 0, max_value = 100)
    real_bonds_duration = FloatField(min_value = 1, max_value = 30, initial = 5) # min duration XXX
    nominal_bonds_duration = FloatField(min_value = 1, max_value = 30, initial = 5)

def step(request):

    global obs #XXX

    errors_present = False

    if request.method == 'POST':

        step_form = StepForm(request.POST)
        if step_form.is_valid():

            data = step_form.cleaned_data

            if data['consume'] + data['real_spias'] + data['nominal_spias'] > env.p_plus_income():
                
                step_form.add_error(None, 'Spending exceeds portfolio size.')
                errors_present = True

            else:

                consume_fraction = data['consume'] / env.p_plus_income()
                p = env.p_plus_income() - data['consume']
                try:
                    real_spias_fraction = data['real_spias'] / p
                except ZeroDivisionError:
                    real_spias_fraction = 0
                try:
                    nominal_spias_fraction = data['nominal_spias'] / p
                except ZeroDivisionError:
                    nominal_spias_fraction = 0
                stocks = data['stocks'] / 100
                real_bonds = data['real_bonds'] / 100
                nominal_bonds = data['nominal_bonds'] / 100
                real_bonds_duration = data['real_bonds_duration']
                nominal_bonds_duration = data['nominal_bonds_duration']

                action = env.encode_direct_action(consume_fraction, real_spias_fraction = real_spias_fraction, nominal_spias_fraction = nominal_spias_fraction,
                    stocks = stocks, real_bonds = real_bonds, nominal_bonds = nominal_bonds,
                    real_bonds_duration = real_bonds_duration, nominal_bonds_duration = nominal_bonds_duration)

                obs, reward, done, info = env.step(action)
                if done:
                    return redirect('reset')

        else:

            errors_present = True

    else:

        step_form = StepForm()

    observation = env.decode_observation(obs)
    
    observation['age'] = '{:.0f}'.format(env.age)
    observation['gi'] = '{:n}'.format(round(observation['gi_real'] + observation['gi_nominal']))
    observation['nominal_interest_rate'] = '{:.1%}'.format((1 + observation['real_interest_rate']) * (1 + observation['inflation_rate']) - 1)
    env.real_spia.set_age(env.age)
    real_payout = env.real_spia.payout(100000, mwr = env.params.real_spias_mwr)
    try:
        observation['real_payout'] = '{:n}'.format(round(real_payout))
    except OverflowError:
        observation['real_payout'] = '-'
    env.nominal_spia.set_age(env.age)
    nominal_payout = env.nominal_spia.payout(100000, mwr = env.params.nominal_spias_mwr)
    try:
        observation['nominal_payout'] = '{:n}'.format(round(nominal_payout))
    except OverflowError:
        observation['nominal_payout'] = '-'

    observation['life_expectancy'] = '{:.1f}'.format(round(observation['life_expectancy'], 1))
    observation['gi_real'] = '{:n}'.format(round(observation['gi_real']))
    observation['gi_nominal'] = '{:n}'.format(round(observation['gi_nominal']))
    observation['p_notax'] = '{:n}'.format(int(observation['p_notax']))
    observation['real_interest_rate'] = '{:.1%}'.format(observation['real_interest_rate'])
    observation['inflation_rate'] = '{:.1%}'.format(observation['inflation_rate'])

    return render(request, 'step.html', {
        'errors_present': errors_present,
        'observation': observation,
        'step_form': step_form,
    })

from locale import LC_ALL, setlocale

setlocale(LC_ALL, '')

parser = arg_parser()
_, eval_model_params, _ = fin_arg_parse(parser, dump = False, args = ('-c', '../validation/aiplanner-scenario.txt'))
env = FinEnv(direct_action = True, **eval_model_params)
