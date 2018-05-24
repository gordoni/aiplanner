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
import math
from os.path import expanduser, isdir, join, normpath
import statistics

from monotone_convex import MonotoneConvex

datapath = ('~/aacalc/opal/data/public', '~ubuntu/aacalc/opal/data/public')

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

                with open(join(YieldCurve.datadir, 'rcmt' if self.interest_rate == 'real' else 'cmt', self.interest_rate + '-' + year_str + '.csv')) as f:

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

        if len(yield_curve_date) == 0:
            raise self.NoData
        elif len(yield_curve_date) == 1:
            yield_curve_date_str = yield_curve_date[0]
        else:
            yield_curve_date_str = date_str_low + ' - ' + date_str

        assert(len(yield_curve_date) == len(yield_curve_years) == len(yield_curve_rates))

        return yield_curve_years, yield_curve_rates, yield_curve_date_str

    def _get_corporate(self, date_year, date_str, date_str_low):

        assert(date_str_low == None) # Not yet implemented.

        if date_year < 1984:
            raise self.NoData

        date_month = int(date_str.split('-')[1])
        assert(1 <= date_month <= 12)

        year_step = 5
        file_year = 1984 + int((date_year - 1984) / year_step) * year_step
        file_year_offset = (date_year - 1984) % year_step
        file_name = 'hqm_%(start)02d_%(end)02d' % {'start' : file_year % 100, 'end' : (file_year + year_step - 1) % 100}

        try:

            with open(join(YieldCurve.datadir, 'hqm', file_name + '.csv')) as f:

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
                            raise self.NoData
                        spot_month = (offset - 2) % 12 + 1
                        spot_date = '%d-%02d' % (spot_year, spot_month)
                    maturity += 0.5
                    assert(float(line[0]) == maturity)
                    assert(line[1] == '')
                    spot_years.append(maturity)
                    spot_rates.append(float(line[offset]) / 100.0)
                assert(maturity == 100)

        except IOError:

            raise self.NoData

        return [spot_years], [spot_rates], spot_date

    def __init__(self, interest_rate, date_str, *, date_str_low = None, adjust = 0, datapath = datapath):
        '''Initialize an object representing a particular yield curve on a
        date specified by the ISO format date string 'date_str'. If
        necessary the relevant interest rate data will be loaded from
        interest rate data files that are kept up to date using the
        fetch_yield_curve script.  If no yield curve is available for
        that date the nearest date before that date will be
        used. Rates are computed for every 6 months.

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

        'adjust' is an adjustment to add to spot yield curve
        annualized rates.

        'datapath' is a list of locations to search for the interest
        rate data files.

        Raises YieldCurve.NoData if not interest rate data can be
        found for the requested date or dates.

        '''

        self.interest_rate = interest_rate
        assert(interest_rate in ('real', 'nominal', 'corporate', 'fixed', 'le'))
        self.date = date_str
        self.date_low = date_str_low
        self.adjust = adjust

        if YieldCurve.datadir == None:
            for datadir in datapath:
                datadir = normpath(expanduser(datadir))
                if isdir(datadir):
                    break
            YieldCurve.datadir = datadir

        if interest_rate in ('real', 'nominal'):

            yield_curve_years, yield_curve_rates, self.yield_curve_date = self._get_treasury(date_str, date_str_low)

        elif interest_rate == 'corporate':

            date_year = int(date_str.split('-')[0])

            try:
                yield_curve_years, yield_curve_rates, self.yield_curve_date = self._get_corporate(date_year, date_str, date_str_low)
            except self.NoData:
                yield_curve_years, yield_curve_rates, self.yield_curve_date = self._get_corporate(date_year - 1, date_str, date_str_low)

        elif interest_rate in ('fixed', 'le'):

            self.yield_curve_date = 'none'

            return

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
        for yield_curve_year, yield_curve_rate in zip(yield_curve_years, yield_curve_rates):
            yield_curve_rate = tuple(math.log((1 + r / 2) ** 2 + self.adjust) for r in yield_curve_rate) # Treasury rates are twice the semi-annualized rate.
            interpolator = MonotoneConvex(yield_curve_year, yield_curve_rate, min_long_term_forward = 15, force_forwards_non_negative = False)
                # Treasury methodology; extrapolate using average forward rate 15 years and longer.
                # Real forwards are not required to be positive, and favor mathematical consistency for nominal forward rates.
            interpolators.append(interpolator)

        # Average the yield curves.
        interpolate_spots = tuple(statistics.mean(interpolator.spot(year) for interpolator in interpolators) for year in interpolate_years)

        # Construct a master interpolator.
        self.monotone_convex = MonotoneConvex(interpolate_years, interpolate_spots, min_long_term_forward = 15, force_forwards_non_negative = False)

    def spot(self, y):
        '''Return the continuously compounded annual spot rate.'''

        if self.interest_rate == 'fixed':
            return math.log(1 + self.adjust)
        elif self.interest_rate == 'le':
            return 0
        else:
            # Spot rates do not match spot rates at
            # https://www.treasury.gov/resource-center/economic-policy/corp-bond-yield/Pages/TNC-YC.aspx
            # because the PchipInterpolator is not being used here and
            # the input par rates of the daily quotes used here differ
            # from the end of month quotes reported there.
            return self.monotone_convex.spot(y)

    def forward(self, y):
        '''Return the continuously compounded annual forward rate.'''

        return self.monotone_convex.forward(y)

    def discount_rate(self, y):
        '''Return 1 + the annual discount rate associated with time period 'y'
        which is expressed in years. Raise the result to the power 'y'
        to get the applicable discount factor.

        '''

        return math.exp(self.monotone_convex.spot(y))

    @property
    def risk_free_rate(self):
        '''Return the average annual risk free rate.'''

        return self.discount_rate(0) - 1
