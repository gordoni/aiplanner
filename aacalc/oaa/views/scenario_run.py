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
