from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from json import loads

from oaa.models import Scenario
from oaa.views.utils import decrypt

@login_required
def scenarios(request):
    user = request.user
    account = user.account
    db_scenarios = Scenario.objects.filter(account=account)
    scenarios = []
    for db_scenario in db_scenarios:
        scenario = decrypt(db_scenario.data)
        scenarios.append({'name': scenario['name'], 'id': db_scenario.id})
    scenarios.sort(key=lambda scenario: scenario['name'].lower())
    return render(request, 'scenarios.html', {
        'scenarios': scenarios,
    })
