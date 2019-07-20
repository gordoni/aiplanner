#!/usr/bin/env python3

# SPIA - Income annuity (SPIA and DIA) price calculator.
# Copyright (C) 2014-2019 Gordon Irlam
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

    def __init__(self, yield_curve, life_table1, *, life_table2 = None, payout_delay = 0, payout_end = None, tax = 0,
        payout_fraction = 1, joint = True, contingent2 = False, period_certain = 0, adjust = 0, frequency = 12, price_adjust = 'calendar',
        percentile = None, date_str = None, schedule = 1, delay_calcs = False, calcs = False,
        joint_payout_fraction = None, joint_contingent = None, cpi_adjust = None):
        '''Initialize an object representing a Single Premium Immediate
        Annuity or a Deferred Income Annuity.

        'yield_curve' is a YieldCurve object representing the interest
        rates.

        'life_table1' is a LifeTable object for the first annuitant.

        'life_table2' is a LifeTable object for any second annuitant.

        'payout_delay' is the delay in receiving the first payout in
        months.

        'payout_end' is the integer offset of the last payout in
        periods from 'payout_delay'. None for no end to the payout
        stream.

        'tax' is the annuity guarantee association tax rate to apply.

        'payout_fraction' applies to a joint or contingent annuity and
        is the fraction of payout when either annuitant or the owner
        is dead.

        'joint' is True for a joint annuity. Payout is reduced on the
        death of either annuitant. False for a contingent
        annuity. Payout is reduced only on the death of the owner.

        'contingent2' applies to a contingent annuity and is True if
        the owner is the second annuitant.  False if the owner is the
        first annuitant.

        'period_certain' is the period for which payment is guaranteed
        after 'payout_delay' has past irrespective of the annuitants
        being alive, and is expressed in years.

        'adjust' is the annual increase factor less one for the payout
        relative to the first payout occuring at 'payout_delay'.

        'frequency' is the number of payouts per year.

        'price_adjust' specifies when any price or real interest rate
        adjustments takes place. It must be one of:

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
        the time offset from the current age of hte first annuitant
        specified in years, an array indexed by the time offset from
        the current age in years less the 'payout_delay' multiplied by
        'frequency', or a numeric value. It should yield a
        multiplicative factor to be applied to each payout.

        'delay_calcs' specifies whether to delay computation of the
        annuity's value. This enables complex payout schedules to be
        built up using add_schedule(..., delay_calcs = True), and then
        a single final add_schedule() call performed to compute the
        annuity's value.

        'calcs' specifies whether to store the calculations in
        self.calcs. Setting calcs to true will slow the computations
        down.

        This method is able to compute annuity prices rapidly when
        'yield_curve' 'interest_rate' is "fixed" and either
        'price_adjust' is "all" or 1 / 'frequency' is an integral
        value.

        '''

        # Legacy parameter names.
        if joint_payout_fraction != None:
            payout_fraction = joint_payout_fraction
        if joint_contingent != None:
            joint = joint_contingent
        if cpi_adjust != None:
            price_adust = cpi_adjust

        self.yield_curve = yield_curve
        self.payout_delay = payout_delay
        self.payout_end = payout_end
        self.tax = tax
        self.life_table1 = life_table1
        self.life_table2 = life_table2
        self.payout_fraction = payout_fraction
        self.joint = joint
        self.contingent2 = contingent2
        self.period_certain = period_certain
        self.adjust = adjust
        self.frequency = frequency  # Setting this to 1 increases the MWR by 10% at age 90.
        self.price_adjust = price_adjust
        assert price_adjust in ('all', 'payout', 'calendar')
        self.percentile = percentile
        self.date = date_str
        self.schedule = schedule
        self.delay_calcs = delay_calcs
        self.calculate = calcs

        self.cacheable_payout = self.yield_curve.interest_rate == 'fixed' and (self.price_adjust == 'all' or 1 / self.frequency % 1 == 0) \
            and self.period_certain == 0 and self.percentile == None
        self.calcs = None
        self.start_age1 = None
        self.set_age(self.life_table1.age)

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
        alive1_array = []
        alive2_array = [] if self.life_table2 else None
        remaining = 0
        p = 0
        q_y = -1
        a_p = 0
        while True:
            if p >= a_p:
                alive1_array.append(alive1)
                if self.life_table2:
                    alive2_array.append(alive2)
                a_p += 1
            if remaining <= 0:
                q_y += 1
                q1 = self.life_table1.q(age = current_age1 + q_y, year = start + q_y, contract_age = q_y)
                q2 = self.life_table2.q(age = current_age2 + q_y, year = start + q_y, contract_age = q_y) if self.life_table2 else 1
                if q1 == q2 == 1:
                    break
                remaining = self.frequency
            append_time = a_p - p
            fract = min(remaining, append_time)
            alive1 *= (1 - q1) ** (fract / self.frequency)
            if self.life_table2:
                alive2 *= (1 - q2) ** (fract / self.frequency)
            remaining -= fract
            p += fract

        delay = self.payout_delay * self.frequency / 12
        fract = delay % 1
        if fract == 0:
            delay = int(delay)
            alive1_delay_array = tuple(alive1_array[delay:])
            if self.life_table2:
                alive2_delay_array = tuple(alive2_array[delay:])
            else:
                alive2_delay_array = None
        else:
            alive1_array.append(0)
            alive1_delay_array = tuple(alive1_array[i] * (1 - fract) + alive1_array[i + 1] * fract for i in range(int(delay), len(alive1_array) - 1))
            if self.life_table2:
                alive2_array.append(0)
                alive2_delay_array = tuple(alive2_array[i] * (1 - fract) + alive2_array[i + 1] * fract for i in range(int(delay), len(alive2_array) - 1))
            else:
                alive2_delay_array = None

        return start, alive1_array, alive2_array, alive1_delay_array, alive2_delay_array

    def set_age(self, age, alive = True, alive2 = True):

        '''Recompute income annuity prices at a particular age.

        'age' is the age of the first annuitant in years. Must be
        greater or equal to the initial age by a multiple of 1 /
        'frequency'.

        'alive' specifies whether the first individual is alive.

        'alive2' specifies whether any second individual is alive.

        This method is able to compute annuity prices rapidly when
        'yield_curve' 'interest_rate' is "fixed" and either
        'price_adjust' is "all" or 1 / 'frequency' is an integral
        value.

        '''

        self.alive = alive
        self.alive2 = alive2

        first_time = self.start_age1 == None
        if first_time:
            self.start_age1 = age
        else:
            index_offset = (age - self.start_age1) * self.frequency
            index_mismatch = index_offset < 0 or (index_offset % 1 > 1e-12 and index_offset % 1 < 1 - 1e-12)
            assert not index_mismatch
            index_offset = round(index_offset)

        compute_vital_stats = first_time or self.life_table1.table == 'iam2012-basic' and self.life_table1.ae != 'none' or \
            self.life_table2 != None and self.life_table2.table == 'iam2012-basic' and self.life_table2.ae != 'none'
        if compute_vital_stats:
            self.start, self.alive1_array, self.alive2_array, self.alive1_delay_array, self.alive2_delay_array = self._compute_vital_stats(age)
            self.alive_offset = 0
        else:
            self.alive_offset = index_offset

        if first_time:
            self.sched_alive = [0] * len(self.alive1_delay_array)
            if self.life_table2:
                self.sched_alive1_only = [0] * len(self.alive1_delay_array)
                self.sched_alive2_only = [0] * len(self.alive1_delay_array)
            self.sched_offset = 0
            self.add_schedule(end = self.payout_end, schedule = self.schedule, payout_fraction = self.payout_fraction, joint = self.joint,
                contingent2 = self.contingent2, adjust = self.adjust, price_adjust = self.price_adjust, delay_calcs = self.delay_calcs)
        else:
            self.sched_offset = index_offset
            self._compute_price(self.cacheable_payout and not compute_vital_stats)

    def add_schedule(self, start = 0, end = None, schedule = 0, payout_fraction = 1, joint = True, contingent2 = False, adjust = 0, price_adjust = 'calendar',
        delay_calcs = False):
        '''Add a constant or an increasing/decreasing payout amount to the
        income annuity.

        'start' is the integer offset of the first payout in periods
        from the current age of the first annuitant plus the
        'payout_delay'.

        'end' is the integer offset of the last payout in periods from
        the currentage of the first annuitant plus the
        'payout_delay'. None for no end to the payout stream.

        'schedule' is either an optional function of one parameter,
        the time offset from the current age of the first annuitant
        specified in years, an array indexed by the time offset from
        the current age in years less the 'payout_delay' multiplied by
        'frequency' less 'start', or a numeric value. It should yield
        a multiplicative factor to be applied to each payout.

        'payout_fraction' applies to a joint or contingent annuity and
        is the fraction of payout when either annuitant or the owner
        is dead.

        'joint' is True for a joint annuity. Payout is reduced on the
        death of either annuitant. False for a contingent
        annuity. Payout is reduced only on the death of the owner.

        'contingent2' applies to a contingent annuity and is True if
        the owner is the second annuitant.  False if the owner is the
        first annuitant.

        'adjust' is the annual increase factor less one for the payout
        relative to the payout occuring at 'start'.

        'price_adjust' specifies when any price adjustments takes
        place. It must be one of:

            'all': At every payout.

            'payout': On the anniversary of the first payout.

            'calendar': On January 1st.

        'delay_calcs' specifies whether to delay computation of the
        annuity's value. This enables complex payout schedules to be
        built up using add_schedule(..., delay_calcs = True), and then
        a single final add_schedule() call performed to compute the
        annuity's value.

        '''

        if schedule != 0:

            if end == None:
                end = len(self.sched_alive)
            end = min(end, len(self.sched_alive) - 1 - self.sched_offset)

            first_payout = self.start + start / self.frequency + self.payout_delay / 12 + 1e-9
            months_since_adjust = 0 if price_adjust == 'payout' else (first_payout % 1) * 12
            adjustment = 1
            for i in range(start, end + 1):
                try:
                    payout = schedule[i]
                except TypeError:
                    try:
                        payout = schedule(self.payout_delay / 12 + i / self.frequency)
                    except TypeError:
                        payout = schedule
                if payout == 0:
                    continue
                if price_adjust == 'all':
                    adjustment = (1 + adjust) ** ((i - start) / self.frequency)
                else:
                    if months_since_adjust >= 12:
                        adjustment = (1 + adjust) ** ((i - start) / self.frequency)
                        months_since_adjust %= 12
                    months_since_adjust += 12 / self.frequency
                self.sched_alive[i + self.sched_offset] += payout * adjustment
                if self.life_table2:
                    fraction = payout_fraction if joint or contingent2 else 1
                    self.sched_alive1_only[i + self.sched_offset] += payout * fraction * adjustment
                    fraction = payout_fraction if joint or not contingent2 else 1
                    self.sched_alive2_only[i + self.sched_offset] += payout * fraction * adjustment

        if not delay_calcs:
            self._compute_price(False)

    def _compute_price(self, use_cache):

        if use_cache:

            try:
                if self.life_table2:
                    alive1 = self.alive1_array[self.alive_offset]
                    alive2 = self.alive2_array[self.alive_offset]
                    price = int(self.alive) * int(self.alive2) * self._prices[self.sched_offset] / (alive1 * alive2) \
                        + int(self.alive) * self._prices1[self.sched_offset] / alive1 + int(self.alive2) * self._prices2[self.sched_offset] / alive2
                else:
                    price = int(self.alive) * self._prices[self.sched_offset] / self.alive1_array[self.alive_offset]
            except IndexError:
                price = 0
            y = self.sched_offset / self.frequency
            price *= self.yield_curve.discount_rate(y) ** y

        else:

            if self.cacheable_payout:
                payout_values = []
                payout_values1 = []
                payout_values2 = []

            offset = self.alive_offset / self.frequency

            price = 0
            duration = 0
            annual_return = 0
            total_payout = 0
            if self.calculate:
                self.calcs = []
            if self.percentile == None:
                target_combined = -1
            else:
                assert self.schedule == 1
                target_combined = 1 - self.percentile / 100
            try:
                alive1_init = self.alive1_array[self.alive_offset]
                alive2_init = self.alive2_array[self.alive_offset] if self.life_table2 else 0
            except IndexError:
                alive1_init = 0
                alive2_init = 0
            if alive1_init == 0:
                alive1_init = 1 # Prevent divide by zero later on.
            if alive2_init == 0:
                alive2_init = 1
            i = 0
            prev_combined = 1
            delay = self.payout_delay / 12
            first_payout = self.start + offset + delay + 1e-9
                # 1e-9: avoid floating point rounding problems when payout_delay computed for the next modal period.
            months_since_adjust = 0 if self.price_adjust == 'payout' else (first_payout % 1) * 12
            spot = self.yield_curve.spot(delay)
            y_eff = delay
            while True:
                period = i / self.frequency
                y = delay + period
                if i + self.alive_offset >= len(self.alive1_delay_array) or prev_combined < target_combined:
                    break
                if period >= self.period_certain:
                    if self.life_table2 == None:
                        alive = int(self.alive) * self.alive1_delay_array[i + self.alive_offset] / alive1_init
                        joint = 0
                    else:
                        alive1 = int(self.alive) * self.alive1_delay_array[i + self.alive_offset] / alive1_init
                        alive2 = int(self.alive2) * self.alive2_delay_array[i + self.alive_offset] / alive2_init
                        alive = alive1 * alive2 if self.joint else (alive2 if self.contingent2 else alive1)
                        joint = 0
                        if self.joint or not self.contingent2:
                            joint += alive2 * (1 - alive1)
                        if self.joint or self.contingent2:
                            joint += alive1 * (1 - alive2)
                else:
                    alive = alive1 = alive2 = 1
                    joint = 0
                combined = alive + self.payout_fraction * joint
                if self.life_table2 == None:
                    payout = alive * self.sched_alive[i + self.sched_offset]
                else:
                    payout = alive1 * alive2 * (self.sched_alive[i + self.sched_offset] \
                        - self.sched_alive1_only[i + self.sched_offset] - self.sched_alive2_only[i + self.sched_offset])
                    payout1 = alive1 * self.sched_alive1_only[i + self.sched_offset]
                    payout2 = alive2 * self.sched_alive2_only[i + self.sched_offset]
                if self.yield_curve.interest_rate != 'real' or self.price_adjust == 'all':
                    spot = self.yield_curve.spot(y)
                    y_eff = y
                else:
                    if months_since_adjust >= 12:
                        spot = self.yield_curve.spot(y)
                        y_eff = y
                        months_since_adjust %= 12
                    months_since_adjust += 12 / self.frequency
                if self.percentile == None:
                    if i == 0 and self.yield_curve.interest_rate == 'le':
                        assert self.schedule == 1
                        payout_fraction = 0.5  # Half credit after last payout recorded at start.
                    else:
                        payout_fraction = payout
                        if self.life_table2:
                            payout_fraction += payout1 + payout2
                else:
                    if combined >= target_combined:
                        payout_fraction = 1
                    else:
                        payout_fraction = (prev_combined - target_combined) / (prev_combined - combined)
                payout_amount = payout_fraction
                discount = math.exp(spot * y_eff)
                payout_value = payout_amount / discount
                price += payout_value
                if self.cacheable_payout:
                    payout_values.append(payout / discount)
                    if self.life_table2:
                        payout_values1.append(payout1 / discount)
                        payout_values2.append(payout2 / discount)
                duration += y * payout_value
                annual_return += payout_amount * spot
                total_payout += payout_amount
                if self.calculate and payout_fraction != 0:
                    r = math.exp(spot)
                    calc = {'i': i, 'y': y, 'alive': alive, 'joint': joint, 'combined': combined,
                        'payout_fraction': payout_fraction, 'interest_rate': r, 'fair_price': payout_value}
                    self.calcs.append(calc)
                i += 1
                prev_combined = combined

            def sum_from_end(l):
                prices = []
                partial_price = 0
                for i in range(len(l) - 1, -1, -1):
                    partial_price += l[i]
                    prices.insert(0, partial_price)
                return prices

            if self.cacheable_payout:
                self._prices = sum_from_end(payout_values)
                if self.life_table2:
                    self._prices1 = sum_from_end(payout_values1)
                    self._prices2 = sum_from_end(payout_values2)

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

    def schedule_payout(self, alive = None, alive2 = None, offset = 0):
        '''Return the sum of schedule values for a particular payout period.

        'alive' specifies whether the first individual is alive. None
        to use the status from the current set_age().

        'alive2' specifies whether any second individual is
        alive. None to use the status from the current set_age().

        'offset' is the integer offset of the payout period from the
        current age of the first individual plus 'payout_delay'
        payout.

        '''

        if alive == None:
            alive = self.alive
        if alive2 == None:
            alive2 = self.alive2

        try:
            if alive and (self.life_table2 == None or alive2):
                return self.sched_alive[self.sched_offset + offset]
            if alive:
                return self.sched_alive1_only[self.sched_offset + offset]
            if alive2 and self.life_table2:
                return self.sched_alive2_only[self.sched_offset + offset]
        except IndexError:
            pass
        return 0

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

    def premium(self, payout = 1, mwr = 1):
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
