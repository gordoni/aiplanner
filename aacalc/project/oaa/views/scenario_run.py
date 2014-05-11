from datetime import datetime
from decimal import Decimal
from django.shortcuts import render

from oaa.views.utils import default_params, OPALServerOverloadedError, run_http

def scenario_run(request):
    scenario_dict = request.session.get('scenario', None)
    if scenario_dict == None:
        return render(request, 'notice.html', { 'msg': 'Scenario does not exist.' })
    for field, default in default_params.items():
        if isinstance(default, Decimal):
            scenario_dict[field] = Decimal(scenario_dict[field])
    try:
        return run_http(request, scenario_dict)
    except OPALServerOverloadedError:
        return render(request, 'notice.html', {
            'msg' :
'''We are temporarily overloaded.  Please return to this site at a
later time and try your query then.'''
        })
