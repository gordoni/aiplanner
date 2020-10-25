# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2020 Gordon Irlam
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
from re import DOTALL, match
from traceback import format_exc

from django.http import HttpResponse
from django.test.client import RequestFactory

from aacalc.views.alloc import Alloc, alloc
from aacalc.views.le import le
from aacalc.views.spia import default_spia_params, spia

def healthcheck(request):

    try:
        check()
    except Exception:
        text = 'FAIL\n\n' + format_exc()
    else:
        text = 'OK'

    return HttpResponse(text, content_type = 'text/plain')

def check():

    # Life expectancy.
    request_factory = RequestFactory()
    request = request_factory.post('/calculators/le', {
        'sex': 'male',
        'age' : 65,
    })
    response = le(request)
    page = response.content.decode('utf8')
    cohort, cohort95 = match('^.*<table id="ssa_cohort".*?<td class="right">(.*?)</td>.*?<span.*?>(.*?)</span>.*$', page, DOTALL).groups()
    assert(17 < float(cohort) < 20)
    assert(31 < float(cohort95) < 35)
    cohort_healthy, cohort_healthy95 = match('^.*<table id="iam".*?<td class="right">(.*?)</td>.*?<span.*?>(.*?)</span>.*$', page, DOTALL).groups()
    assert(22 < float(cohort_healthy) < 25)
    assert(34 < float(cohort_healthy95) < 40)
    period, = match('^.*<table id="ssa_period".*?<td class="right">.*?<span.*?>(.*?)</span>.*$', page, DOTALL).groups()
    assert(17 < float(period) < 20)

    # SPIA.
    today = datetime.utcnow().date()
    request_factory = RequestFactory()
    params = default_spia_params()

    params['adjust'] = 0
    params['payout'] = 1000
    request = request_factory.post('/calculators/spia', params)
    response = spia(request)
    page = response.content.decode('utf8')
    premium1, premium2, yield_curve_date, cost1, cost2 = match('^.*Actuarially fair premium:.*?(\d+),(\d+).*?Yield curve date: (\d\d\d\d-\d\d-\d\d).*?Cost to self insure: (\d+),(\d+).*$', page, DOTALL).groups()
    assert(150000 < int(premium1 + premium2) < 350000)
    assert(200000 < int(cost1 + cost2) < 500000)
    quote = datetime.strptime(yield_curve_date, '%Y-%m-%d').date()
    assert(0 <= (today - quote).days <= 8)

    params['bond_type'] = 'nominal'
    request = request_factory.post('/calculators/spia', params)
    response = spia(request)
    page = response.content.decode('utf8')
    premium1, premium2, yield_curve_date = match('^.*Actuarially fair premium:.*?(\d+),(\d+).*?Yield curve date: (\d\d\d\d-\d\d-\d\d).*$', page, DOTALL).groups()
    assert(100000 < int(premium1 + premium2) < 300000)
    quote = datetime.strptime(yield_curve_date, '%Y-%m-%d').date()
    assert(0 <= (today - quote).days <= 8)

    params['bond_type'] = 'corporate'
    request = request_factory.post('/calculators/spia', params)
    response = spia(request)
    page = response.content.decode('utf8')
    premium1, premium2, yield_curve_date = match('^.*Actuarially fair premium:.*?(\d+),(\d+).*?Yield curve date: (\d\d\d\d-\d\d).*$', page, DOTALL).groups()
    assert(100000 < int(premium1 + premium2) < 250000)
    quote = datetime.strptime(yield_curve_date, '%Y-%m').date()
    assert(0 <= (today - quote).days <= 100)

    # Asset allocation.
    params = Alloc().default_alloc_params()
    params['p'] = 1000000
    params['desired_income'] = 1000000
    params['purchase_income_annuity'] = False
    # No way to generate the appropriate POSTed parameter values for a formset. Set manually.
    for i, db in enumerate(params['db']):
        for k, v in db.items():
            params['form-%d-%s' % (i, k)] = v
    params['form-TOTAL_FORMS'] = len(params['db'])
    params['form-INITIAL_FORMS'] = len(params['db'])
    params['form-MAX_NUM_FORMS'] = len(params['db'])
    del params['db']
    for k, v in params.items():
        if v == None:
            params[k] = ''
    request = request_factory.post('/calculators/aa', params)
    response = alloc(request, 'aa', healthcheck=True)
    page = response.content.decode('utf8')
    stocks, consume, _ = match('^.*<!-- healthcheck_aa --> (\d+)/\d+.*<!-- healthcheck_consume --> ((\d|,)+).*$', page, DOTALL).groups()
    assert(60 < float(stocks) <= 100)
    assert(80000 < float(consume.replace(',', '')) < 110000)
