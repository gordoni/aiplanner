from datetime import datetime
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from json import loads
from time import strptime

from oaa.forms import ScenarioEditForm
from oaa.models import Scenario
from oaa.views.utils import decrypt, default_params, dob_to_age, do_scenario_edit

def dob_to_birth_year(dob_str_or_age):
    if isinstance(dob_str_or_age, int):
        now = datetime.utcnow().timetuple()
        return now.tm_year - dob_str_or_age
    else:
        return strptime(dob_str_or_age, '%Y-%m-%d').tm_year

@login_required
def scenario_edit(request, scenario_id):

    user = request.user
    account = user.account
    try:
        scenario = Scenario.objects.get(id=int(scenario_id), account=account)
    except Scenario.DoesNotExist:
        return render(request, 'notice.html', { 'msg': 'Scenario does not exist.' })
    scenario_dict = decrypt(scenario.data)

    if request.method == 'POST':
        se_form = ScenarioEditForm(account.temp_user, request.POST)
        if se_form.is_valid():
            do_scenario_edit(request, se_form, int(scenario_id))
            return render(request, 'scenario_wait.html', {
                'suppress_navigation': True,
                'scenario_id': scenario_id,
            })
        errors_present = True
    else:

        errors_present = False

        defaults = dict(default_params)
        #birth_year = dob_to_birth_year(scenario_dict['dob'])
        #if scenario_dict['dob2'] != None:
        #    birth_year2 = dob_to_birth_year(scenario_dict['dob2'])
        #    birth_year = (birth_year + birth_year2) / 2
        #defaults['retirement_year'] = birth_year + 65
        defaults['retirement_year'] = datetime.utcnow().timetuple().tm_year

        for field, default in defaults.items():
            if field not in scenario_dict:
                scenario_dict[field] = default
            if isinstance(default, Decimal):
                scenario_dict[field] = Decimal(scenario_dict[field])
        se_form = ScenarioEditForm(account.temp_user, scenario_dict)

    data = dict(scenario_dict)
    data['id'] = scenario_id
    data['age'] = str(dob_to_age(scenario_dict['dob']))
    data['age2'] = str(dob_to_age(scenario_dict['dob2']))
    data['readonly'] = account.temp_user

    return render(request, 'mega_form.html', {
        'errors_present': errors_present,
        'data': data,
        'se_form': se_form,
    })
