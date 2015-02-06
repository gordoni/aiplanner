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
from django.shortcuts import render

from aacalc.forms import LeForm
from aacalc.views.utils import default_params, get_le, OPALServerOverloadedError, run_dirname

def le(request):

    errors_present = False

    le_cohort = ['-'] * 6
    le_cohort_healthy = ['-'] * 6
    le_period = ['-'] * 6

    if request.method == 'POST':

        le_form = LeForm(request.POST)
        if le_form.is_valid():
            scenario_dict = dict(default_params)
            scenario_dict['calculator'] = 'le'
            for param in ('sex', 'dob', 'sex2', 'dob2'):
                scenario_dict[param] = le_form.cleaned_data.get(param)
            scenario_dict['retirement_year'] = 2000 # Hack.
            scenario_dict['consume_discount_rate_pct'] = Decimal('0.0') # Don't want discounted percentiles.
            try:
                dirname = run_dirname(request, scenario_dict)
            except OPALServerOverloadedError:
                return render(request, 'notice.html', {
                    'msg' :
'''We are temporarily overloaded.  Please return to this site at a
later time and try your query then.'''
        })
            le_cohort, le_cohort_healthy, le_period = get_le(dirname)
        else:
            errors_present = True

    else:

        le_form = LeForm({'sex': 'male', 'dob': 65})

    le_labels = [
        '5th',
        '10th',
        '20th',
        '50th',
        '80th',
        '90th',
        '95th',
        '98th',
        '99th',
    ]

    index = 1 + le_labels.index('95th')
    le_cohort[index] = '<span style="font-weight:bold;">' + le_cohort[index] + '</span>'
    le_cohort_healthy[index] = '<span style="font-weight:bold;">' + le_cohort_healthy[index] + '</span>'
    le_period[0] = '<span style="font-weight:bold;">' + le_period[0] + '</span>'

    index = 1 + le_labels.index('50th')
    del le_labels[0 : index]
    del le_cohort[1 : index + 1]
    del le_cohort_healthy[1 : index + 1]
    del le_period[1 : index + 1]

    return render(request, 'le.html', {
        'errors_present': errors_present,
        'le_form': le_form,
        'le_labels': le_labels,
        'le_cohort': le_cohort,
        'le_cohort_healthy': le_cohort_healthy,
        'le_period': le_period,
    })
