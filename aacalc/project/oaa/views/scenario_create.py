from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render

from oaa.forms import ScenarioCreateForm, ScenarioEditForm, ScenarioNameForm
from oaa.views.utils import default_params, do_scenario_create, do_scenario_edit

@login_required
def scenario_create(request):
    if request.method == 'POST':
        sn_form = ScenarioNameForm(request.POST)
        sc_form = ScenarioCreateForm(request.POST)
        se_form = ScenarioEditForm(False, request.POST)
        if sn_form.is_valid() and sc_form.is_valid() and se_form.is_valid():
            name = sn_form.cleaned_data['name']
            scenario_id = do_scenario_create(request, name, sc_form)
            scenario_dict = do_scenario_edit(request, se_form, scenario_id)
            return render(request, 'scenario_wait.html', {
                'scenario_id': scenario_id,
            })
        errors_present = True
    else:
        errors_present = False
        defaults = dict(default_params)
        defaults['retirement_year'] = datetime.utcnow().timetuple().tm_year
        sn_form = ScenarioNameForm()
        sc_form = ScenarioCreateForm()
        se_form = ScenarioEditForm(False, defaults)
    return render(request, 'mega_form.html', {
        'errors_present': errors_present,
        'sn_form': sn_form,
        'sc_form': sc_form,
        'se_form': se_form,
    })
