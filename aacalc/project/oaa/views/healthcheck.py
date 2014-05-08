from datetime import datetime

from oaa.views.utils import default_params, run_response

def healthcheck(request):
    scenario_dict = dict(default_params)
    scenario_dict['name'] = 'Healthcheck'
    scenario_dict['sex'] = 'male'
    scenario_dict['dob'] = 99
    scenario_dict['retirement_year'] = datetime.utcnow().timetuple().tm_year
    return run_response(request, '0', scenario_dict)
