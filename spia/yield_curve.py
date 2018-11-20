# SPIA - Income annuity (SPIA and DIA) price calculator.
# Copyright (C) 2014-2018 Gordon Irlam
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

import csv
from datetime import datetime
from json import dumps, loads
import math
from os import makedirs
from os.path import expanduser, isdir, join, normpath
import statistics

import scipy.interpolate

from .fetch_yield_curve import datadir, fetch_yield_curve
from .monotone_convex import MonotoneConvex

cachedir = '~/.cache/spia'

class YieldCurve(object):

    class NoData(Exception):
        pass

    datadir = None

    def _get_treasury(self, date_str, date_str_low):

        date_year_str = date_str.split('-')[0]
        special = False
        try:
            date_year = int(date_year_str)
        except ValueError:
            special = True
            date_year = 0

        if date_str_low:
            date_year_low = int(date_str_low.split('-')[0])
        else:
            date_year_low = date_year - 1

        yield_curve_date = []
        yield_curve_years = []
        yield_curve_rates = []
        for year in range(date_year, date_year_low - 1, -1):

            year_str = date_year_str if special else str(year)

            try:

                with open(join(self.datadir, self.interest_rate, self.interest_rate + '-' + year_str + '.csv')) as f:

                    r = csv.reader(f)
                    assert(next(r)[0].startswith('#'))

                    years = next(r)
                    years.pop(0)
                    years = tuple(float(v) for v in years)

                    date = []
                    rates = []
                    for line in r:
                        d = line[0]
                        rate = line[1:]
                        if special:
                            match = d == date_str
                        else:
                            match = d <= date_str
                            if date_str_low:
                                match = match and date_str_low <= d
                        if match:
                            if not date_str_low:
                                date = []
                                rates = []
                            assert(len(years) == len(rate))
                            if not all(r == '' for r in rate):
                                date.append(d)
                                rates.append(rate)
                        elif not date_str_low:
                            break

                yield_curve_date.extend(date)
                for rate in rates:
                    yield_curve_years.append(tuple(y for y, r in zip(years, rate) if r != ''))
                    yield_curve_rates.append(tuple(float(r) / 100 for r in rate if r != ''))

                if not date_str_low and yield_curve_date:
                    break

            except IOError:

                pass

        try:
            yield_curve_date_str = max(yield_curve_date)
        except ValueError:
            raise self.NoData('Requested interest rate data unavailable.')

        assert(len(yield_curve_date) == len(yield_curve_years) == len(yield_curve_rates))

        return yield_curve_years, yield_curve_rates, yield_curve_date_str

    def _get_corporate(self, date_year, date_str, date_str_low):

        assert(date_str_low == None) # Not yet implemented.

        if date_year < 1984:
            raise self.NoData('Requested interest rate data unavailable.')

        date_month = int(date_str.split('-')[1])
        assert(1 <= date_month <= 12)

        year_step = 5
        file_year = 1984 + int((date_year - 1984) / year_step) * year_step
        file_year_offset = (date_year - 1984) % year_step
        file_name = 'hqm_%(start)02d_%(end)02d' % {'start' : file_year % 100, 'end' : (file_year + year_step - 1) % 100}

        try:

            with open(join(self.datadir, self.interest_rate, file_name + '.csv')) as f:

                r = csv.reader(f)
                line = next(r)
                line = next(r)
                line = next(r)
                if ''.join(line) == '':  # catdoc xls2csv ommits this line for reasons unknown.
                    line = next(r)
                years = tuple(int(year) for year in line if year != '')
                assert(years[file_year_offset] == date_year)
                line = next(r)
                line = next(r)
                maturity = 0
                spot_years = []
                spot_rates = []
                for line in r:
                    if line[0].startswith("\f"):  # catdoc xls2csv uses formfeed as end of sheet marker.
                        break
                    if maturity == 0:
                        while line[-1] == '':
                            line.pop()
                        offset = min(len(line) - 1, 2 + file_year_offset * 12 + date_month - 1)
                        spot_year = file_year + (offset - 2) / 12
                        if spot_year < file_year:
                            raise self.NoData('Requested interest rate data unavailable.')
                        spot_month = (offset - 2) % 12 + 1
                        spot_date = '%d-%02d' % (spot_year, spot_month)
                    maturity += 0.5
                    assert(float(line[0]) == maturity)
                    assert(line[1] == '')
                    spot_years.append(maturity)
                    spot_rates.append(float(line[offset]) / 100.0)
                assert(maturity == 100)

        except IOError:

            raise self.NoData('Requested interest rate data unavailable.')

        return [spot_years], [spot_rates], spot_date

    def __init__(self, interest_rate, date_str, *, date_str_low = None, adjust = 0.0, permit_stale_days = float('inf'), cache = True):
        '''Initialize an object representing a particular yield curve on a
        date specified by the ISO format date string 'date_str'. If
        necessary the relevant interest rate data will be loaded from
        interest rate data files that are kept up to date using the
        fetch_yield_curve script.

        'interest_rate' should be one of the following:

            "real": U.S. Treasury daily real yield curve.

                If the ISO format date, 'date_str_low', is specified
                then the average of the spot yield curves between date
                and 'date_str' will be used.

            "nominal": U.S. Treasury daily nominal yield curve.

                If the ISO format date, 'date_str_low', is specified
                then the average of the spot yield curves between date
                and 'date_str' will be used.

            "corporate": U.S. Corporate High Quality Markets (AAA, AA,
            A rated bonds) monthly yield curve as reported by the
            U.S. Treasury.

            "fixed": A constant yield curve of zero.

            "le": A constant yield curve of zero. 'adjust' is ignored.
            When computing SPIA prices 'le' specifies to ignore the
            first time period zero payout, and if percentile is
            specified to interpolate the final payout. As such the
            SPIA price corresponds to the life expectancy.

        'date_str' an ISO format date string describing the requested
        yield curve date. If no yield curve is available for that date
        the nearest date before that date will be used.

        'date_str_low' specifies the lower bound date of a range of
        dates ending at 'date_str' for which to compute the average
        yield curve.

        'adjust' is an adjustment to add to spot yield curve
        annualized rates.

        'permit_stale_days' is the maximum number of days the returned
        yield curve is allowed to be out of date without triggering a
        new download of the interest rate data from the web.

        'cache' specifies whether to cache and utilize any cache of
        the yield curve saved to the directory "~/.cache/spia" when
        'date_str_low' is specified. This can speed up initialization.
        Cache should be False if 'date_str' exceeds the latest yield
        curve data date. The cache should be manually cleared if this
        package is changed.

        Raises YieldCurve.NoData if not interest rate data can be
        found for the requested date or dates.

        '''

        self.interest_rate = interest_rate
        assert(interest_rate in ('real', 'nominal', 'corporate', 'fixed', 'le'))
        self.date = date_str
        self.date_low = date_str_low
        self.adjust = adjust
        self.permit_stale_days = permit_stale_days
        self.cache = cache and interest_rate not in ('fixed', 'le')

        self._spot_cache = {}

        if self.interest_rate in ('fixed', 'le'):
            self.yield_curve_date = 'none'
            return

        self.datadir = normpath(expanduser(datadir))

        yield_curve_date = None
        cached = False

        if self.cache and self.date_low:

            cache_dir = normpath(expanduser(cachedir))
            makedirs(cache_dir, exist_ok = True)
            cache_path = join(cache_dir, 'spia-' + self.interest_rate + '-' + self.date + '-' + self.date_low + '-' + str(self.adjust))

            try:
                json_str = open(cache_path).read()
                cached = True
            except IOError:
                pass

            if cached:
                cache_data = loads(json_str)
                version = cache_data['version']
                yield_curve_date = cache_data['yield_curve_date']
                interpolate_years = cache_data['years']
                interpolate_spots = cache_data['spots']
                cached = version == 1

        for count in range(2):

            try:
                if not cached:
                    interpolate_years, interpolate_spots = self._load_yield_curve()
                    yield_curve_date = self.yield_curve_date
            except self.NoData:
                stale_days = float('inf')
            else:
                wanted_date = min(datetime.utcnow().date(), datetime.strptime(self.date, '%Y-%m-%d').date())
                have_date = yield_curve_date
                if self.interest_rate == 'corporate':
                    have_date += '-28'
                have_date = datetime.strptime(have_date, '%Y-%m-%d').date()
                stale_days = (wanted_date - have_date).days

            if stale_days <= self.permit_stale_days:
                break

            fetch_yield_curve(self.interest_rate)
            interpolate_years, interpolate_spots = self._load_yield_curve()
            if self.yield_curve_date != yield_curve_date:
                cached = False

        if stale_days == float('inf'):
            raise self.NoData('Requested interest rate data unavailable.')
        if stale_days > self.permit_stale_days:
            raise self.NoData('Interest rate data is stale.')

        if not cached and self.cache and self.date_low:

            cache_data = {'version': 1, 'yield_curve_date': self.yield_curve_date, 'years': interpolate_years, 'spots': interpolate_spots}
            json_str = dumps(cache_data)
            try:
                open(cache_path, 'w').write(json_str)
            except IOError:
                pass

        # Construct a master interpolator.
        self.monotone_convex = MonotoneConvex(interpolate_years, interpolate_spots, min_long_term_forward = 15, force_forwards_non_negative = False)

    def _load_yield_curve(self):

        if self.interest_rate in ('real', 'nominal'):

            yield_curve_years, yield_curve_rates, self.yield_curve_date = self._get_treasury(self.date, self.date_low)

            # Convert par rates to spot rates.
            spot_rates = []
            for yield_curve_year, yield_curve_rate in zip(yield_curve_years, yield_curve_rates):

                # First interpolate the spot returns.
                coupon_yield_curve = []
                yield_curve = scipy.interpolate.PchipInterpolator(yield_curve_year, yield_curve_rate)

                for i in range(1, int(2 * max(yield_curve_year)) + 1):
                    year = i / 2.0
                    # For below range values Scipy just uses the polynominal, which is problematic, so we use linear interpolation in this case.
                    if year < min(yield_curve_year):
                        slope = yield_curve(min(yield_curve_year), 1)
                        slope = float(slope) # De-numpify.
                        rate = yield_curve_rate[0] + slope * (year - min(yield_curve_year))
                    else:
                        rate = float(yield_curve(year))
                    coupon_yield_curve.append(rate)

                spot_rate = self.par_to_spot(coupon_yield_curve)
                    # Does not match spot rates at https://www.treasury.gov/resource-center/economic-policy/corp-bond-yield/Pages/TNC-YC.aspx
                    # because the input par rates of the daily quotes used differ from the end of month quotes reported there.
                # Extract just the spot rates of the original yield curve.
                spot_rate = tuple(spot_rate[math.ceil(y * 2 - 1)] for y in yield_curve_year)
                    # Rates less than 6 months will all get the 6 month spot rate. This is only relevant for nominals.
                    # This is fine for computing immediate annuity prices.
                    # For some applications it may be necessary to interpolate the spot rates, but this would slow things down.
                spot_rates.append(spot_rate)

        elif self.interest_rate == 'corporate':

            date_year = int(self.date.split('-')[0])

            try:
                yield_curve_years, spot_rates, self.yield_curve_date = self._get_corporate(date_year, self.date, self.date_low)
            except self.NoData:
                yield_curve_years, spot_rates, self.yield_curve_date = self._get_corporate(date_year - 1, self.date, self.date_low)

        else:

            assert False

        # When dealing with a date range not all of the yield curves might have rates for all of the same years.

        # Figure out what years have been reported.
        interpolate_years = set()
        for yield_curve_year in yield_curve_years:
               interpolate_years |= set(yield_curve_year)
        interpolate_years = sorted(interpolate_years)

        # Construct interpolators for each yield curve.
        interpolators = []
        for yield_curve_year, spot_rate in zip(yield_curve_years, spot_rates):
            continuous_spot_rate = tuple(math.log((1 + r / 2) ** 2 + self.adjust) for r in spot_rate) # Treasury rates are twice the semi-annualized rate.
            interpolator = MonotoneConvex(yield_curve_year, continuous_spot_rate, min_long_term_forward = 15, force_forwards_non_negative = False)
                # Treasury methodology; extrapolate using average forward rate 15 years and longer.
                # Real forwards are not required to be positive, and favor mathematical consistency for nominal forward rates.
            interpolators.append(interpolator)

        # Average the yield curves.
        interpolate_spots = tuple(statistics.mean(interpolator.spot(year) for interpolator in interpolators) for year in interpolate_years)

        return interpolate_years, interpolate_spots

    def par_to_spot(self, rates):
        '''Convert semi-annual par rates to semi-annual spot rates.'''
        # See: https://en.wikipedia.org/wiki/Bootstrapping_%28finance%29
        spots = []
        discount_rate_sum = 0
        count = 0
        for rate in rates:
            count += 1
            coupon_yield = rate / 2.0
            discount_rate = (1 - coupon_yield * discount_rate_sum) / (1 + coupon_yield)
            spot_yield = discount_rate ** (- 1.0 / count) - 1
            spots.append(spot_yield * 2)
            discount_rate_sum += discount_rate
        return spots

    def spot_to_par(self, rates):
        '''Convert semi-annual spot rates to semi-annual par rates.'''
        pars = []
        count = 0
        coupons = 0
        for spot, forward in zip(rates, self.spot_to_forward(rates)):
            count += 1
            coupons = 1 + coupons * (1 + forward / 2)
            pars.append(((1 + spot / 2) ** count - 1) / coupons * 2)
        return pars

    def spot_to_forward(self, rates):
        '''Convert semi-annual spot rates to semi-annual forward rates.'''
        forwards = []
        count = 0
        old_spot_rate = 0
        for rate in rates:
            count += 1
            new_spot_rate = rate / 2
            forward_rate = (1 + new_spot_rate) ** count / (1 + old_spot_rate) ** (count - 1)
            forwards.append((forward_rate - 1) * 2)
            old_spot_rate = new_spot_rate
        return forwards

    def forward_to_spot(self, rates):
        '''Convert semi-annual forward rates to semi-annual spot rates.'''
        spots = []
        count = 0
        spot_rate = 1
        for rate in rates:
            count += 1
            forward_rate = 1 + rate / 2
            spot_rate = (forward_rate * spot_rate ** (count - 1)) ** (1.0 / count)
            spots.append((spot_rate - 1) * 2)
        return spots

    def spot(self, y):
        '''Return the continuously compounded annual spot rate.'''

        try:
            spt = self._spot_cache[y]
        except KeyError:
            if self.interest_rate == 'fixed':
                spt = math.log(1 + self.adjust)
            elif self.interest_rate == 'le':
                spt = 0
            else:
                # Spot rates do not match spot rates at
                # https://www.treasury.gov/resource-center/economic-policy/corp-bond-yield/Pages/TNC-YC.aspx
                # because the PchipInterpolator is not being used here and
                # the input par rates of the daily quotes used here differ
                # from the end of month quotes reported there.
                spt = self.monotone_convex.spot(y)
            if len(self._spot_cache) < 1000:
                self._spot_cache[y] = spt

        return spt

    def forward(self, y):
        '''Return the continuously compounded annual forward rate.'''

        if self.interest_rate == 'fixed':
            return math.log(1 + self.adjust)
        elif self.interest_rate == 'le':
            return 0
        else:
            return self.monotone_convex.forward(y)

    def discount_rate(self, y):
        '''Return 1 + the annual discount rate associated with time period 'y'
        which is expressed in years. Raise the result to the power 'y'
        to get the applicable discount factor.

        '''

        if self.interest_rate == 'fixed':
            return 1 + self.adjust
        elif self.interest_rate == 'le':
            return 1
        else:
            return math.exp(self.monotone_convex.spot(y))

    @property
    def risk_free_rate(self):
        '''Return the average annual risk free rate.'''

        return self.discount_rate(0) - 1
