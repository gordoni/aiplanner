# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import floor

import cython

from ai.gym_fin.factory_spia import make_income_annuity

@cython.cclass
class DefinedBenefit:

    def __init__(self, env, params, *, real = True, type_of_funds = 'tax_deferred'):

        self.env = env
        self.params = params
        self.real = real
        self.type_of_funds = type_of_funds

        self.spia_preretirement = None
        self.spia_retired = None

    def _create(self, *, preretirement):

        bonds = self.env.bonds_zero if self.real else self.env.bonds_constant_inflation

        vital_stats = None
        db: DefinedBenefit
        for db in self.env.defined_benefits.values():
            if preretirement:
                if db.spia_preretirement is not None:
                    vital_stats = db.spia_preretirement.vital_stats
                    break
            else:
                if db.spia_retired is not None:
                    vital_stats = db.spia_retired.vital_stats
                    break

        if vital_stats is not None:
            life_table = None
            life_table2 = None
            age = None
            age2 = None
            date_str = None
        else:
            if preretirement:
                life_table = self.env.life_table_preretirement
                life_table2 = self.env.life_table2_preretirement
            else:
                life_table = self.env.life_table
                life_table2 = self.env.life_table2
            age = self.env.age
            age2 = self.env.age2
            date_str = self.env.date
            vital_stats = None

        payout_delay = 0
        payout_start = 0 if preretirement else round(self.env.preretirement_years / self.params.time_period)
        spia = make_income_annuity(bonds, life_table, life_table2 = life_table2, vital_stats = vital_stats, age = age, age2 = age2,
            payout_delay = 12 * payout_delay, payout_start = payout_start,
            frequency = round(1 / self.params.time_period), price_adjust = 'all', date_str = date_str, schedule = 0, delay_calcs = True)

        return spia

    def add(self, type = 'income_annuity', owner = 'self', start = None, end = None, payout = None, adjustment = 0,
            joint = False, payout_fraction = 0, exclusion_period = 0, exclusion_amount = 0, delay_calcs = False):

        if end is None:
            end = float('inf')

        owner_age = self.env.age if owner == 'self' else self.env.age2
        if start is None:
            start = self.env.preretirement_years
        else:
            start = start - owner_age
        try:
            payout_low, payout_high = payout
        except TypeError:
            pass
        else:
            payout = self.env.log_uniform(payout_low, payout_high)
        end -= owner_age

        original_payout = payout
        if not self.real:
            payout *= self.env.cpi

        self._add_sched(owner, start, end, payout, joint, payout_fraction, adjustment, delay_calcs)

        if self.type_of_funds == 'taxable' and exclusion_period > 0:

            # Shift nominal exclusion amount from taxable to tax free income.
            exclusion_amount *= self.env.cpi
            end = start + exclusion_period
            db = self.env.get_db(type, False, 'taxable')
            db._add_sched(owner, start, end, - exclusion_amount, joint, payout_fraction, adjustment, delay_calcs)
            db = self.env.get_db(type, False, 'tax_free')
            db._add_sched(owner, start, end, exclusion_amount, joint, payout_fraction, adjustment, delay_calcs)

    def force_calcs(self):

        if self.spia_preretirement is not None:
            self.spia_preretirement.add_schedule(schedule = 0)
        if self.spia_retired is not None:
            self.spia_retired.add_schedule(schedule = 0)

    def _add_sched(self, owner, start, end, payout, joint, payout_fraction, adjustment, delay_calcs):

        #print('_add_sched:', self.type_of_funds, 'real' if self.real else 'nominal', owner, start, end, payout, joint, payout_fraction, adjustment, delay_calcs)

        start = max(floor(start / self.params.time_period + 0.5), 0)
        end = floor(end / self.params.time_period + 0.5) - 1 if end != float('inf') else int(1e9)
        payout *= self.params.time_period

        contingent2 = owner == 'spouse'
        retirement = round(self.env.preretirement_years / self.params.time_period)

        # Separate pre-retirement and retired SPIAs so can compute present values separately.

        end_preretirement = min(end, retirement - 1)
        if start <= end_preretirement:
            if self.spia_preretirement is None:
                self.spia_preretirement = self._create(preretirement = True)
            self.spia_preretirement.add_schedule(start = start, end = end_preretirement, schedule = payout,
                payout_fraction = payout_fraction, joint = joint, contingent2 = contingent2, adjust = adjustment, price_adjust = 'all', delay_calcs = delay_calcs)

        start_retired = max(start, retirement)
        if start_retired <= end:
            if self.spia_retired is None:
                self.spia_retired = self._create(preretirement = False)
            payout *= (1 + adjustment) ** (max(retirement - start, 0) * self.params.time_period)
            self.spia_retired.add_schedule(start = start_retired, end = end, schedule = payout,
                payout_fraction = payout_fraction, joint = joint, contingent2 = contingent2, adjust = adjustment, price_adjust = 'all', delay_calcs = delay_calcs)

    @cython.locals(cpi = cython.double)
    def payout(self, cpi):

        payout: cython.double
        if self.spia_preretirement is not None:
            payout = self.spia_preretirement.schedule_payout()
        elif self.spia_retired is not None:
            payout = self.spia_retired.schedule_payout()
        else:
            payout = 0
        if not self.real:
            payout /= cpi

        return payout

    @cython.locals(age = cython.double, retired = cython.bint, alive = cython.bint, alive2 = cython.bint)
    def step(self, age, retired, alive, alive2):

        if self.spia_preretirement is not None:
            if retired:
                self.spia_preretirement = None
            else:
                self.spia_preretirement.set_age(age, alive, alive2)
        if self.spia_retired is not None:
            self.spia_retired.set_age(age, alive, alive2)

    def render(self, cpi):

        payout = self.payout(cpi)
        pv = self.pv(cpi, preretirement = True, retired = True)

        print('    ', self.type_of_funds, payout, 'real' if self.real else 'nominal', pv)

    @cython.locals(cpi = cython.double, preretirement = cython.bint, retired = cython.bint)
    def pv(self, cpi, preretirement = False, retired = False):

        pv: cython.double
        pv = 0
        if preretirement and (self.spia_preretirement is not None):
            pv += float(self.spia_preretirement.premium())
        if retired and (self.spia_retired is not None):
            pv += float(self.spia_retired.premium())
        if not self.real:
            pv /= cpi

        return pv
