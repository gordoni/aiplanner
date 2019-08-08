# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import floor

from spia import IncomeAnnuity, LifeTable

class DefinedBenefit:

    def __init__(self, env, type = 'Income Annuity', real = True, type_of_funds = 'tax_deferred'):

        self.env = env
        self.type = type
        self.real = real
        self.type_of_funds = type_of_funds

        # Separate pre-retirement and retired SPIAs so can compute present values separately.
        life_table = self.env.life_table_preretirement
        life_table2 = self.env.life_table2_preretirement if self.env.sex2 else None
        self.spia_preretirement = self.create(life_table, life_table2 = life_table2)
        life_table = self.env.life_table
        life_table2 = self.env.life_table2 if self.env.sex2 else None
        self.spia_retired = self.create(life_table, life_table2 = life_table2)

    def create(self, life_table, life_table2 = None):

        bonds = self.env.bonds_zero if self.real else self.env.bonds_constant_inflation

        payout_delay = 0
        spia = IncomeAnnuity(bonds, life_table, life_table2 = life_table2, payout_delay = 12 * payout_delay, frequency = round(1 / self.env.params.time_period),
            price_adjust = 'all', date_str = self.env.date.isoformat(), schedule = 0, delay_calcs = True)

        return spia

    def add(self, owner = 'self', start = None, end = None, premium = None, payout = None, adjustment = 0,
            joint = False, payout_fraction = 0, exclusion_period = 0, exclusion_amount = 0, delay_calcs = False):

        assert (premium == None) != (payout == None)
        if end == None:
            end = float('inf')

        owner_age = self.env.age if owner == 'self' else self.env.age2
        if start == None:
            start = self.env.preretirement_years
        else:
            start = start - owner_age
        if premium != None:
            mwr = self.env.params.real_spias_mwr if self.real else self.env.params.nominal_spias_mwr
            start = max(start, self.env.preretirement_years)
            payout = self._spia_payout(start, adjustment, payout_fraction, premium, mwr)
        else:
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
            if premium != None:
                while exclusion_amount > original_payout:
                    exclusion_period += 1
                    if adjustment == 0:
                        exclusion_amount = premium / exclusion_period
                    else:
                        exclusion_amount = premium * adjustment / ((1 + adjustment) ** exclusion_period - 1)
            exclusion_amount *= self.env.cpi
            end = start + exclusion_period
            db = self.env.get_db(self.type, False, 'taxable')
            db._add_sched(owner, start, end, - exclusion_amount, joint, payout_fraction, adjustment, delay_calcs)
            db = self.env.get_db(self.type, False, 'tax_free')
            db._add_sched(owner, start, end, exclusion_amount, joint, payout_fraction, adjustment, delay_calcs)

    def force_calcs(self):

        self.spia_preretirement.add_schedule()
        self.spia_retired.add_schedule()

    def _spia_payout(self, payout_delay, adjustment, payout_fraction, premium, mwr):

        bonds = self.env.bonds.real if self.real else self.env.bonds.nominal
        life_table, life_table2 = self.env.spia_life_tables(self.env.age, self.env.age2)

        spia = IncomeAnnuity(bonds, life_table, life_table2 = life_table2, payout_delay = 12 * payout_delay, joint = True,
            payout_fraction = payout_fraction, adjust = adjustment, frequency = 1 / self.env.params.time_period, price_adjust = 'all',
            date_str = self.env.date.isoformat())

        payout = spia.payout(premium, mwr = mwr) / self.env.params.time_period

        return payout

    def _add_sched(self, owner, start, end, payout, joint, payout_fraction, adjustment, delay_calcs):

        #print('_add_sched:', owner, start, end, payout, joint, payout_fraction, adjustment)

        start = max(floor(start / self.env.params.time_period + 0.5), 0)
        end = floor(end / self.env.params.time_period + 0.5) - 1 if end != float('inf') else int(1e10)
        payout /= self.env.params.time_period

        contingent2 = owner == 'spouse'
        retirement = round(self.env.preretirement_years / self.env.params.time_period)

        self.spia_preretirement.add_schedule(start = start, end = min(end, retirement - 1), schedule = payout,
            payout_fraction = payout_fraction, joint = joint, contingent2 = contingent2, adjust = adjustment, price_adjust = 'all', delay_calcs = delay_calcs)

        payout *= (1 + adjustment) ** (max(retirement - start, 0) * self.env.params.time_period)
        self.spia_retired.add_schedule(start = max(start, retirement), end = end, schedule = payout,
            payout_fraction = payout_fraction, joint = joint, contingent2 = contingent2, adjust = adjustment, price_adjust = 'all', delay_calcs = delay_calcs)

    def payout(self):

        if self.env.preretirement_years > 0:
            payout = self.spia_preretirement.schedule_payout()
        else:
            payout = self.spia_retired.schedule_payout()
        if not self.real:
            payout /= self.env.cpi

        return payout

    def step(self, steps):

        age = self.env.age
        alive = self.env.couple or not self.env.only_alive2
        alive2 = self.env.couple or self.env.only_alive2
        if self.env.preretirement_years > 0:
            self.spia_preretirement.set_age(age, alive, alive2)
        self.spia_retired.set_age(age, alive, alive2)

    def render(self):

        payout = self.payout()
        pv = self.pv()
        if not self.real:
            payout /= self.env.cpi

        print('    ', self.type_of_funds, payout, 'real' if self.real else 'nominal', pv)

    def pv(self, preretirement = True, retired = True):

        pv = 0
        if preretirement and self.env.preretirement_years > 0:
            pv += self.spia_preretirement.premium()
        if retired:
            pv += self.spia_retired.premium()
        if not self.real:
            pv /= self.env.cpi

        return pv
