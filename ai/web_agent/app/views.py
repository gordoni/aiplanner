# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from csv import writer
from json import dumps
from locale import LC_ALL, setlocale
from math import exp
from os import chdir, getcwd, mkdir
from os.path import dirname
from random import randrange, seed
from re import match
from subprocess import run

from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import BooleanField, CharField, FloatField, Form, HiddenInput, IntegerField, NumberInput, Textarea, TextInput
from django.shortcuts import redirect, render

from ai.common.cmd_util import arg_parser, fin_arg_parse
from ai.gym_fin.fin_env import FinEnv
from ai.gym_fin.model_params import ModelParams

class HomeForm(Form):

    name = CharField(min_length = 1, widget = TextInput(attrs = {'size': 30}))
    qualifications = CharField(min_length = 2, widget = TextInput(attrs = {'size': 30}))
    software = CharField(required = False, widget = TextInput(attrs = {'size': 60}))

def home(request):

    errors_present = False

    if request.method == 'POST':

        home_form = HomeForm(request.POST)
        if home_form.is_valid():

            data = home_form.cleaned_data

            uid = request.COOKIES.get('uid')
            if uid == None:
                seed()
                uid = randrange(1000000000)
                uid = str(uid)
                mkdir(settings.STATIC_ROOT + 'user' + uid)

            with open(settings.STATIC_ROOT + 'user' + uid + '/info.json', 'a') as f:
                f.write(dumps(data) + '\n')

            response = redirect('episode')
            response.set_cookie('uid', uid, max_age = 7 * 86400)
            response.set_cookie('episode', '0', max_age = 7 * 86400)
            return response

        else:

            errors_present = True

    else:

        home_form = HomeForm()

    response = render(request, 'home.html', {
        'errors_present': errors_present,
        'home_form': home_form,
    })

    return response

def episode(request):

    uid = request.COOKIES.get('uid')
    if uid == None or not match(r'^\d{1,9}$', uid):
        return render(request, 'no-cookie.html')

    episode = request.COOKIES.get('episode')
    if episode == None or not match(r'^\d{1,3}$', episode):
        return render(request, 'no-cookie.html')
    episode = int(episode)

    return render(request, 'episode.html', {
        'episode': episode,
    })

class StateForm(Form):

    step = IntegerField(widget = HiddenInput())
    real_oup_x = FloatField(widget = HiddenInput())
    inflation_oup_x = FloatField(widget = HiddenInput())
    gi_real = FloatField(widget = HiddenInput())
    gi_nominal = FloatField(widget = HiddenInput())
    p_notax = FloatField(widget = HiddenInput())

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

    consume = FloatField(min_value = 0, widget = NumberInput(attrs = {'class': 'numeric'}))
    consume_all = BooleanField(required = False, initial = False)
    real_spias = FloatField(min_value = 0, initial = 0, widget = NumberInput(attrs = {'class': 'numeric'}))
    nominal_spias = FloatField(min_value = 0, initial = 0, widget = NumberInput(attrs = {'class': 'numeric'}))
    stocks = FloatField(min_value = 0, max_value = 100, widget = NumberInput(attrs = {'class': 'small-numeric'}))
    real_bonds = FloatField(min_value = 0, max_value = 100, initial = 0, widget = NumberInput(attrs = {'class': 'small-numeric'}))
    nominal_bonds = FloatField(min_value = 0, max_value = 100, widget = NumberInput(attrs = {'class': 'small-numeric'}))
    real_bonds_duration = FloatField(min_value = 1, max_value = 30, initial = 5, widget = NumberInput(attrs = {'class': 'small-numeric'}))
    nominal_bonds_duration = FloatField(min_value = 1, max_value = 30, initial = 5, widget = NumberInput(attrs = {'class': 'small-numeric'}))

def step(request):

    uid = request.COOKIES.get('uid')
    if uid == None or not match(r'^\d{1,9}$', uid):
        return render(request, 'no-cookie.html')

    episode = request.COOKIES.get('episode')
    if episode == None or not match(r'^\d{1,3}$', episode):
        return render(request, 'no-cookie.html')
    episode = int(episode)
    env.set_reproduce_episode(episode)

    errors_present = False
    action = None
    done = False
    consume_all = False

    if request.method == 'POST':

        state_form = StateForm(request.POST)
        assert state_form.is_valid()
        state = state_form.cleaned_data
        step = state['step']

        obs = env.goto(state['step'], state['real_oup_x'], state['inflation_oup_x'], state['gi_real'], state['gi_nominal'], state['p_notax'])

        step_form = StepForm(request.POST)
        if step_form.is_valid():

            data = step_form.cleaned_data

            if not data['consume_all'] and data['consume'] + data['real_spias'] + data['nominal_spias'] > env.p_plus_income():

                step_form.add_error(None, 'Spending exceeds total available.')
                errors_present = True

            elif data['consume_all'] and (data['real_spias'] != 0 or data['nominal_spias'] != 0):

                step_form.add_error(None, 'SPIA purchases must be zero when selecting consume all.')
                errors_present = True

            elif data['consume_all'] and (env.p_notax > 10000):

                step_form.add_error(None, 'Investment portfolio must be spent down before selecting consume all.')
                errors_present = True

            else:

                if data['consume_all']:
                    consume_all = True
                    consume = env.p_plus_income()
                    consume_fraction = 1
                    p = 0
                else:
                    consume = data['consume']
                    consume_fraction =  consume / env.p_plus_income()
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

                step += 1

        else:

            errors_present = True

    else:

        step_form = StepForm()
        step = 0

        obs = env.reset()

    state = StateForm({
        'step': step,
        'real_oup_x': env.real_bonds.oup.x,
        'inflation_oup_x': env.inflation.oup.x,
        'gi_real': env.gi_real,
        'gi_nominal': env.gi_nominal,
        'p_notax': env.p_notax,
    })

    user_dir = 'user' + uid

    with open(settings.STATIC_ROOT + user_dir + '/' + 'log.json', 'a') as f:

        while True:

            if done:

                observe = None
                observation = None

            else:

                observe = env.decode_observation(obs)

                observation = {}
                observation['alive'] = '{:.1%}'.format(env.alive[env.episode_length])
                observation['age'] = '{:.0f}'.format(env.age)
                observation['gi'] = '{:n}'.format(round(observe['gi_real'] + observe['gi_nominal']))
                observation['p_plus_income'] = '{:n}'.format(round(env.p_plus_income()))
                if env.episode_length > 0:
                    observation['prev_nominal_return'] = '{:.1%}'.format(env.prev_ret * env.prev_inflation - 1)
                observation['nominal_interest_rate'] = '{:.1%}'.format((1 + observe['real_interest_rate']) * (1 + observe['inflation_rate']) - 1)
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

                observation['life_expectancy'] = '{:.1f}'.format(round(observe['life_expectancy'], 1))
                observation['gi_real'] = '{:n}'.format(round(observe['gi_real']))
                observation['gi_nominal'] = '{:n}'.format(round(observe['gi_nominal']))
                observation['p_notax'] = '{:n}'.format(int(observe['p_notax']))
                observation['real_interest_rate'] = '{:.1%}'.format(observe['real_interest_rate'])
                observation['inflation_rate'] = '{:.1%}'.format(observe['inflation_rate'])

            if not action:
                break

            step_data = {
                'episode': episode,
                'step': step - 1,
                'alive': env.alive[env.episode_length - 1],
                'consume': consume,
                'action': data,
                'new_observation': observe,
                'real_oup_x': env.real_bonds.oup.x,
                'inflation_oup_x': env.inflation.oup.x,
                'human_new_observation': observation,
            }
            if episode > 0:
                f.write(dumps(step_data) + '\n')

            if done or not consume_all:
                break

            consume = env.p_plus_income()
            consume_fraction = 1
            action = env.encode_direct_action(consume_fraction, stocks = 1)
            obs, reward, done, info = env.step(action)
            step += 1

    if done:
        response = redirect('episode')
        response.set_cookie('episode', episode + 1, max_age = 7 * 86400)
        return response

    dump_yield_curve(user_dir, 'real', env.real_bonds)
    dump_yield_curve(user_dir, 'nominal', env.nominal_bonds)
    plot_yield_curves(user_dir)

    return render(request, 'step.html', {
        'errors_present': errors_present,
        'user_dir': user_dir,
        'state': state,
        'observation': observation,
        'step_form': step_form,
    })

def dump_yield_curve(user_dir, style, bonds):

    maturity = tuple(i / 2 for i in range(1, 30 * 2 + 1))
    spots = tuple(2 * (exp(bonds.spot(y) / 2) - 1) for y in maturity)
        # Treasury par rates are twice the semi-annual rate.
    pars = bonds.yield_curve.spot_to_par(spots)

    with open(settings.STATIC_ROOT + user_dir + '/' + style + '.csv', 'w') as f:
        csv = writer(f)
        csv.writerows(zip(maturity, pars))

def plot_yield_curves(user_dir):

    dir = getcwd()
    chdir(settings.STATIC_ROOT + user_dir)
    try:
        run([dirname(__file__) + '/plot-step.gnuplot'], check = True)
    finally:
        chdir(dir)

class FinishForm(Form):

    comments = CharField(widget = Textarea(attrs = {'rows': 15, 'cols': 80}))

def finish(request):

    uid = request.COOKIES.get('uid')
    if uid == None or not match(r'^\d{1,9}$', uid):
        return render(request, 'no-cookie.html')

    errors_present = False

    if request.method == 'POST':

        finish_form = FinishForm(request.POST)
        if finish_form.is_valid():

            data = finish_form.cleaned_data

            with open(settings.STATIC_ROOT + 'user' + uid + '/comments.json', 'a') as f:
                f.write(dumps(data) + '\n')

            return render(request, 'finished.html')

        else:

            errors_present = True

    else:

        finish_form = FinishForm()

    response = render(request, 'finish.html', {
        'errors_present': errors_present,
        'finish_form': finish_form,
    })

    return response

setlocale(LC_ALL, '') # For "," as thousands separator in numbers.

parser = arg_parser()
_, eval_model_params, _ = fin_arg_parse(parser, dump = False,
    args = ('-c', '../validation/aiplanner-scenario.txt', '--master-real-spias', '--master-nominal-spias'))
env = FinEnv(direct_action = True, **eval_model_params)
