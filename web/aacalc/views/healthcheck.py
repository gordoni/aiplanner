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

from decimal import Decimal
from datetime import datetime

from aacalc.views.utils import default_params, get_le, run_response, run_dirname

def healthcheck(request):

    # Life expectancy.
    scenario_dict = dict(default_params)
    scenario_dict['calculator'] = 'le'
    scenario_dict['sex'] = 'male'
    scenario_dict['dob'] = 65
    scenario_dict['retirement_year'] = 2000 # Hack.
    scenario_dict['consume_discount_rate_pct'] = Decimal('0.0') # Don't want discounted percentiles.
    dirname = run_dirname(request, scenario_dict, True)
    le_cohort, le_cohort_healthy, le_period = get_le(dirname)
    assert(17 < float(le_cohort[0]) < 20)
    assert(21 < float(le_cohort_healthy[0]) < 24)
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
    return run_response(request, scenario_dict, True)
