from datetime import datetime
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from oaa.models import Scenario
from oaa.views.utils import decrypt, default_params, OPALServerOverloadedError, run_http

@login_required
def scenario_run(request, scenario_id):
    user = request.user
    account = user.account
    try:
        scenario = Scenario.objects.get(id=int(scenario_id), account=account)
    except Scenario.DoesNotExist:
        return render(request, 'notice.html', { 'msg': 'Scenario does not exist.' })
    scenario_dict = decrypt(scenario.data)
    for field, default in default_params.items():
        if isinstance(default, Decimal):
            scenario_dict[field] = Decimal(scenario_dict[field])
    try:
        return run_http(request, scenario_id, scenario_dict)
    except OPALServerOverloadedError:
        account.last_fail = datetime.utcnow()
        account.save()
        return render(request, 'notice.html', {
            'msg' :
'''We are temporarily overloaded.  Please return to this site at a
later time and try your query then.'''
        })
