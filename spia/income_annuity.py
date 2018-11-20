#!/usr/bin/env python3

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

from argparse import ArgumentParser
from calendar import monthrange
import math

class IncomeAnnuity(object):

    def __init__(self, yield_curve, life_table1, *, life_table2 = None, payout_delay = 0, tax = 0,
                 joint_payout_fraction = 1, joint_contingent = True, period_certain = 0,
                 frequency = 12, cpi_adjust = 'calendar', percentile = None, date_str = None,
                 schedule = None, calcs = False):
        '''Initialize an object representing a Single Premium Immediate
        Annuity or a Deferred Income Annuity.

        'yield_curve' is a YieldCurve object representing the interest
        rates.

        'life_table1' is a LifeTable object for the first annuitant.

        'life_table2' is a LifeTable object for any second annuitant.

        'payout_delay' is the delay in receiving the first payout in
        months.

        'tax' is the annuity gurantee association tax rate to apply.

        'joint_payout_fraction' is the fraction of payout when
        first/either annuitant is dead.

        'joint_contingent' is True for a joint annuity. Payout is
        reduced on the death of either annuitant. False for a
        contingent annuity. Payout is reduced only on the death of the
        first annuitant.

        'period_certain' is the period for which payment is guaranteed
        after payout_delay has past irrespective of the annuitants
        being alive, and is expressed in years.

        'frequency' is the number of payouts per year.

        'cpi_adjust' only applies to real yield curves and specifies
        when any consumer price index adjustment takes place. It must
        be one of:

            'all': At every payout.

            'payout': On the anniversary of the first payout.

            'calendar': On January 1st.

        'percentile' specifies a percentile value expressed as a
        floating point number to compute the annuity value through to
        the specified percentile of life expectancy, or None to
        compute the total annuity value.

        'date_str' is an ISO format date specifying the date for which
        to compute the annuity's value. The default is to use the same
        date as the yield curve.

        'schedule' is either an optional function of one parameter,
        the time offset from the date used to compute the annuity's
        value specified in years, or an array indexed by the time
        offset in years divided by 'frequency'. It should yield a
        multiplicative factor to be applied to each payout.

        'calcs' indicates whether to make a record of the
        calculations performed.

        '''

        self.yield_curve = yield_curve
        self.payout_delay = payout_delay
        self.tax = tax
        self.life_table1 = life_table1
        self.life_table2 = life_table2
        self.joint_payout_fraction = joint_payout_fraction
        self.joint_contingent = joint_contingent
        self.period_certain = period_certain
        self.frequency = frequency  # Setting this to 1 increases the MWR by 10% at age 90.
        self.cpi_adjust = cpi_adjust
        assert cpi_adjust in ('all', 'payout', 'calendar')
        self.percentile = percentile
        self.date = date_str
        self.schedule = schedule

        self.calcs = None
        self.current_age1 = None
        self.set_age(self.life_table1.age, calcs = calcs)

    def _compute_vital_stats(self, current_age1):

        offset = current_age1 - self.life_table1.age
        current_age2 = self.life_table2.age + offset if self.life_table2 else None
        starting_date = self.date if self.date else self.yield_curve.date
        start_year, m, d = starting_date.split('-')
        start_year = int(start_year)
        start_month = int(m) - 1 + (float(d) - 1) / monthrange(start_year, int(m))[1]
        start = start_year + start_month / 12 + offset
        alive1 = 1.0
        alive2 = 1.0
        alive1_array = [1.0]
        alive2_array = [0.0]
        i = 0
        while True:
            y = float(i)
            q1 = self.life_table1.q(age = current_age1 + y, year = start + y, contract_age = y)
            q2 = 1 if current_age2 is None else self.life_table2.q(age = current_age2 + y, year = start + y, contract_age = y)
            if q1 == q2 == 1:
                break
            for _ in range(self.frequency):
                alive1 *= (1 - q1) ** (1.0 / self.frequency)
                alive2 *= (1 - q2) ** (1.0 / self.frequency)
                alive1_array.append(alive1)
                alive2_array.append(alive2)
            i += 1

        alive1_array.append(0)
        alive2_array.append(0)

        return start, tuple(alive1_array), tuple(alive2_array)

    def set_age(self, age, *, calcs = False):
        '''Recompute income annuity prices.

        'age' as the age of the first annuitant.

        'calcs': whether to store the calculations in
        self.calcs. Setting calcs to true will slow the computations
        down.

        '''

        if self.current_age1 == None:
            recompute = True
        else:
            index_offset = (age - self.current_age1) * self.frequency
            recompute = index_offset < 0 or index_offset % 1 != 0

        if self.life_table1.table == 'iam2012-basic' and self.life_table1.ae != 'none' or \
            self.life_table2 != None and self.life_table2.table == 'iam2012-basic' and self.life_table2.ae != 'none':
            recompute = True

        if recompute:
            self.start, self.alive1_array, self.alive2_array = self._compute_vital_stats(age)
            self.current_age1 = age
            index_offset = 0
        else:
            index_offset = int(index_offset)

        offset = index_offset / self.frequency

        price = 0
        duration = 0
        annual_return = 0
        total_payout = 0
        if calcs:
            calculations = []
        if self.percentile == None:
            target_combined = -1
        else:
            assert self.schedule == None
            target_combined = 1 - self.percentile / 100.0
        try:
            alive1_init = self.alive1_array[index_offset]
            alive2_init = self.alive2_array[index_offset]
        except IndexError:
            alive1_init = 0
            alive2_init = 0
        if alive1_init == 0:
            alive1_init = 1 # Prevent divide by zero later on.
        if alive2_init == 0:
            alive2_init = 1
        i = 0
        prev_combined = 1.0
        delay = self.payout_delay / 12.0
        first_payout = self.start + offset + delay + 1e-9
            # 1e-9: avoid floating point rounding problems when payout_delay computed for the next modal period.
        months_since_adjust = 0 if self.cpi_adjust == 'payout' else (first_payout % 1) * 12
        spot = self.yield_curve.spot(delay)
        y_eff = delay
        while True:
            period = i / self.frequency
            y = delay + period
            index = index_offset + y * self.frequency
            fract = index % 1
            index = int(index)
            if index + 1 >= len(self.alive1_array) or prev_combined < target_combined:
                break
            if self.schedule:
                try:
                    schedule = self.schedule[int(y * self.frequency + 0.5)]
                except TypeError:
                    schedule = self.schedule(y)
                if schedule == 0:
                    i += 1
                    continue
            else:
                schedule = 1
            if period >= self.period_certain:
                if self.life_table2 == None:
                    alive = self.alive1_array[index] / alive1_init
                    if fract != 0:
                        alive1 = self.alive1_array[index + 1] / alive1_init
                        alive = (1 - fract) * alive + fract * alive1
                    joint = 0
                else:
                    alive1 = self.alive1_array[index] / alive1_init
                    alive2 = self.alive2_array[index] / alive2_init
                    alive = alive1 * alive2
                    joint = alive1 + alive2 - 2 * alive
                    if fract != 0:
                        alive1 = self.alive1_array[index + 1] / alive1_init
                        alive2 = self.alive2_array[index + 1] / alive2_init
                        alive_both = alive1 * alive2
                        alive = (1 - fract) * alive + fract * alive_both
                        joint = (1 - fract) * joint + fract * (alive1 + alive2 - 2 * alive_both)
            else:
                alive = 1
                joint = 0
            combined = alive + self.joint_payout_fraction * joint
            if self.yield_curve.interest_rate != 'real' or self.cpi_adjust == 'all':
                spot = self.yield_curve.spot(y)
                y_eff = y
            else:
                if months_since_adjust >= 12:
                    spot = self.yield_curve.spot(y)
                    y_eff = y
                    months_since_adjust -= 12
                months_since_adjust += 12.0 / self.frequency
            if self.percentile is None:
                if i == 0 and self.yield_curve.interest_rate == 'le':
                    payout_fraction = 0  # No credit for first payout.
                else:
                    payout_fraction = combined
            else:
                if combined >= target_combined:
                    payout_fraction = 1.0
                else:
                    payout_fraction = (prev_combined - target_combined) / (prev_combined - combined)
            payout_amount = payout_fraction * schedule
            payout_value = payout_amount / math.exp(spot * y_eff)
            price += payout_value
            duration += y * payout_value
            annual_return += payout_amount * spot
            total_payout += payout_amount
            if calcs:
                r = math.exp(spot)
                calc = {'i': i, 'y': y, 'alive': alive, 'joint': joint, 'combined': combined, 'payout_fraction': payout_fraction, 'interest_rate': r, 'fair_price': payout_value}
                calculations.append(calc)
            i += 1
            prev_combined = combined

        if self.yield_curve.interest_rate == 'le' and self.percentile is None:
            assert not self.schedule
            payout_fraction = 0.5  # Half credit after last payout.
            payout_amount = payout_fraction
            payout_value = payout_amount / math.exp(spot * y_eff)
            price += payout_value
            duration += y * payout_value
            annual_return += payout_amount * spot
            total_payout += payout_amount
            if calcs:
                r = math.exp(spot)
                calc = {'i': i, 'y': y, 'alive': 0.0, 'joint': 0.0, 'combined': 0.0, 'payout_fraction': payout_fraction, 'interest_rate': r, 'fair_price': payout_value}
                calculations.append(calc)

        try:
            self._duration = duration / price
        except ZeroDivisionError:
            assert(duration == 0)
            self._duration = 0
        try:
            self._annual_return = math.exp(annual_return / total_payout) - 1
        except ZeroDivisionError:
            self._annual_return = 0
        try:
            self._unit_price = price / (1 - self.tax)
        except ZeroDivisionError:
            self._unit_price = float('inf')
        self.calcs = calculations if calcs else None

    @property
    def duration(self):
        '''Duration of the bonds backing the annuity in years.'''
        return self._duration

    @property
    def annual_return(self):
        '''An estimate of the life expectancy weighted average annual return
        of the annuity.

        '''
        return self._annual_return

    def premium(self, payout, mwr = 1):
        '''The price paid to recieve periodic payout 'payout' when the Money's
        Worth Ratio is 'mwr'.

        '''
        return self._unit_price * payout / mwr

    def payout(self, premium, mwr = 1):
        '''The periodic payout received for the single premium amount
        'premium' when the Money's Worth Ratio is 'mwr'.

        '''
        try:
            return premium * mwr / self._unit_price
        except ZeroDivisionError:
            return float('inf')

    def mwr(self, premium, payout):
        '''The Money's Worth Ratio for premium 'premium' and payout 'payout'.'''
        try:
            return self._unit_price * payout / premium
        except ZeroDivisonError:
            return float('inf')

        # MWR decreases 2% at age 50 and 5% at age 90 when cross from one age nearest birthday to the next.

class Scenario(IncomeAnnuity):

    def __init__(self, yield_curve, payout_delay, premium, payout, tax, life_table1, *, mwr = 1, comment = '', **kwargs):

        '''Initialize an object representing an observed SPIA for which two of
        premium, payout, and mwr are known are we are interested in
        the third. Also used by legagy AACalc web code to initialize a
        SPIA object.

        '''

        super().__init__(yield_curve, life_table1, payout_delay = payout_delay, tax = tax, **kwargs)
        self.scenario_premium = premium
        self.scenario_payout = payout
        self.scenario_mwr = mwr
        self.comment = comment

    def price(self):
        '''Legagy function.'''
        return self._unit_price / (self.frequency * self.scenario_mwr)
