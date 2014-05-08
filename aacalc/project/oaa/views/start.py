from datetime import datetime
from django.core.urlresolvers import reverse
from django.forms.forms import NON_FIELD_ERRORS
from django.http import HttpResponseRedirect
from django.shortcuts import render

from oaa.forms import ScenarioCreateForm, ScenarioAaForm, ScenarioNumberForm, ScenarioEditForm
from oaa.models import Scenario
from oaa.views.utils import dob_to_age, default_params, temp_account_create, do_scenario_create, do_scenario_edit

def start(request, mode):
    if request.method == 'POST':
        sc_form = ScenarioCreateForm(request.POST)
        se_form = ScenarioAaForm(True, request.POST) if mode == 'aa' else ScenarioNumberForm(True, request.POST)
        if sc_form.is_valid() and se_form.is_valid():
            scenario_id = None
            if not request.user.is_authenticated() or request.user.account.temp_user:
                temp_account_create(request)
            else:
                return HttpResponseRedirect(reverse('scenarios'))
            if scenario_id == None:
                scenario_id = do_scenario_create(request, '--- temporary scenario ----', sc_form)
            scenario_dict = do_scenario_edit(request, se_form, scenario_id)
            response = render(request, 'scenario_wait.html', {
                'scenario_id': scenario_id,
            })
            return response
        errors_present = True
    elif request.user.is_authenticated() and not request.user.account.temp_user:
        return HttpResponseRedirect(reverse('scenarios'))
    else:
        errors_present = False
        sc_form = ScenarioCreateForm()
        defaults = dict(default_params)
        defaults['retirement_number'] = 'on'
        defaults['retirement_year'] = datetime.utcnow().timetuple().tm_year
        se_form = ScenarioAaForm(True, defaults) if mode == 'aa' else ScenarioNumberForm(True, defaults)
    data = {
        'mode': mode,
        'readonly': True
    }
    return render(request, 'mega_form.html', {
        'errors_present': errors_present,
        'data': data,
        'sc_form': sc_form,
        'se_form': se_form,
    })
