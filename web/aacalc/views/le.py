# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2016 Gordon Irlam
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

from aacalc.forms import LeForm
from aacalc.spia import LifeTable, Scenario, YieldCurve

le_percentiles = (None, 80, 90, 95, 98, 99, )

le_labels = ('80th', '90th', '95th', '98th', '99th', )

def get_le(table, date_str, sex, age, sex2, age2):

    yield_curve = YieldCurve('le', date_str)
    life_table = LifeTable(table, sex, age, ae = 'aer2005_08-summary')
    if sex2 == None:
        life_table2 = None
    else:
        life_table2 = LifeTable(table, sex2, age2, ae = 'aer2005_08-summary')
    le = []
    for percentile in le_percentiles:
        scenario = Scenario(yield_curve, 0, None, None, 0, life_table, life_table2 = life_table2, frequency = 12, percentile = percentile)
        le.append("%.2f" % (scenario.price(), ))

    return le

def le(request):

    errors_present = False

    le_cohort = ['-'] * len(le_percentiles)
    le_cohort_healthy = ['-'] * len(le_percentiles)
    le_period = ['-'] * len(le_percentiles)

    if request.method == 'POST':

        le_form = LeForm(request.POST)
        if le_form.is_valid():
            data = le_form.cleaned_data
            date_str = datetime.utcnow().date().isoformat()
            sex = data['sex']
            age = float(data['age'])
            sex2 = data['sex2']
            age2 = float(data['age2']) if data['sex2'] != None else None
            le_cohort = get_le('ssa-cohort', date_str, sex, age, sex2, age2)
            le_cohort_healthy = get_le('iam2012-basic', date_str, sex, age, sex2, age2)
            le_period = get_le('ssa-period', date_str, sex, age, sex2, age2)
        else:
            errors_present = True

    else:

        le_form = LeForm({'sex': 'male', 'age': 65})

    index = 1 + le_labels.index('95th')
    le_cohort[index] = '<span class="bold">' + le_cohort[index] + '</span>'
    le_cohort_healthy[index] = '<span class="bold">' + le_cohort_healthy[index] + '</span>'
    le_period[0] = '<span class="bold">' + le_period[0] + '</span>'

    return render(request, 'le.html', {
        'errors_present': errors_present,
        'le_form': le_form,
        'le_labels': le_labels,
        'le_cohort': le_cohort,
        'le_cohort_healthy': le_cohort_healthy,
        'le_period': le_period,
    })
