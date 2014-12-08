from decimal import Decimal
from datetime import datetime

from oaa.views.utils import default_params, get_le, run_response, run_dirname

def healthcheck(request):

    # Life expectancy.
    scenario_dict = dict(default_params)
    scenario_dict['calculator'] = 'le'
    scenario_dict['sex'] = 'male'
    scenario_dict['dob'] = 65
    scenario_dict['retirement_year'] = 2000 # Hack.
    scenario_dict['consume_discount_rate_pct'] = Decimal('0.0') # Don't want discounted percentiles.
    dirname = run_dirname(request, scenario_dict)
    le_cohort, le_cohort_healthy, le_period = get_le(dirname)
    assert(17 < float(le_cohort[0]) < 20)
    assert(22 < float(le_cohort_healthy[0]) < 25)
    assert(17 < float(le_period[0]) < 20)
    assert(abs(float(le_cohort[0]) - float(le_cohort[1])) < 2)
    assert(abs(float(le_cohort_healthy[0]) - float(le_cohort_healthy[1])) < 2)
    assert(abs(float(le_period[0]) - float(le_period[1])) < 2)

    # Asset allocation.
    scenario_dict = dict(default_params)
    scenario_dict['name'] = 'Healthcheck'
    scenario_dict['sex'] = 'male'
    scenario_dict['dob'] = 90
    scenario_dict['p'] = Decimal(100000)
    scenario_dict['retirement_year'] = datetime.utcnow().timetuple().tm_year
    return run_response(request, scenario_dict)
