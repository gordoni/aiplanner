# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2015 Gordon Irlam
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime
from decimal import Decimal
from django.forms.forms import NON_FIELD_ERRORS
from django.shortcuts import render
from time import strptime

from oaa.forms import ScenarioAaForm, ScenarioNumberForm, ScenarioEditForm
from oaa.views.utils import default_params, dob_to_age

def init_se_form(mode, s):
    if mode == 'aa':
        return ScenarioAaForm(s)
    elif mode == 'number':
        return ScenarioNumberForm(s)
    else:
        return ScenarioEditForm(s)

def do_scenario_edit(request, form):
    data = {}
    for field, value in default_params.items():
        if field in form.cleaned_data:
            val = form.cleaned_data[field]
            if isinstance(val, Decimal):
                val = str(val)  # JSON can't handle Decimals.
            data[field] = val
        else:
            if isinstance(value, Decimal):
                value = str(value)
            data[field] = value
    request.session['scenario'] = data
    request.session.set_expiry(365 * 86400)
    return data

def scenario_edit(request, mode):

    cookies_ok = True

    if request.method == 'POST':
        cookies_ok = request.session.test_cookie_worked()
        se_form = init_se_form(mode, request.POST)
        if se_form.is_valid() and cookies_ok:
            do_scenario_edit(request, se_form)
            return render(request, 'scenario_wait.html', {
                'suppress_navigation': True,
            })
        if not cookies_ok:
            se_form.errors[NON_FIELD_ERRORS] = se_form.error_class(["Cookies need to be enabled to use this site."])
        errors_present = True
    else:

        errors_present = False

        if mode == 'edit':
            scenario_dict = request.session.get('scenario', {})
        else:
            scenario_dict = {}

        defaults = dict(default_params)
        defaults['retirement_year'] = datetime.utcnow().timetuple().tm_year
        if mode != 'edit':
            defaults['retirement_number'] = 'on'

        for field, default in defaults.items():
            if field not in scenario_dict:
                scenario_dict[field] = default
            if isinstance(default, Decimal):
                scenario_dict[field] = Decimal(scenario_dict[field])
        se_form = init_se_form(mode, scenario_dict)

    request.session.set_test_cookie()
    return render(request, 'mega_form.html', {
        'mode': mode,
        'errors_present': errors_present,
        'cookies_ok': cookies_ok,
        'se_form': se_form,
    })
