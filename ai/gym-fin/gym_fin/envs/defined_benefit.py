# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import ceil, floor

from spia import IncomeAnnuity, LifeTable

class DefinedBenefit:

    def __init__(self, env, type = 'Income Annuity', owner = 'self', real = True, joint = False, payout_fraction = 0, type_of_funds = 'tax_deferred'):

        assert owner in ('self', 'spouse')

        self.env = env
        self.type = type
        self.owner = owner
        self.real = real
        self.joint = joint
        self.payout_fraction = payout_fraction
        self.type_of_funds = type_of_funds

        self.owner_single = 'spouse' if self.env.only_alive2 else 'self'

        younger = self.env.age if self.env.params.sex2 == None else min(self.env.age, self.env.age2)
        episodes = ceil((self.env.params.age_end - younger) / self.env.params.time_period)

        bonds = self.env.bonds_zero if self.real else self.env.bonds.inflation
        if self.env.couple:
            life_table = self.env.life_table if owner == 'self' else self.env.life_table2
            life_table2 = self.env.life_table2 if owner == 'self' else self.env.life_table
        else:
            life_table = self.env.life_table2 if self.env.only_alive2 else self.env.life_table
            life_table2 = None
        payout_delay = 0
        schedule = [0] * episodes
        self.sched = schedule
        self.spia = IncomeAnnuity(bonds, life_table, life_table2 = life_table2, payout_delay = 12 * payout_delay, joint_contingent = joint,
            joint_payout_fraction = payout_fraction, frequency = round(1 / self.env.params.time_period),
            cpi_adjust = 'all', date_str = self.env.date.isoformat(), schedule = schedule)

        if self.env.couple:

            life_table = self.env.life_table2 if self.env.only_alive2 else self.env.life_table
            schedule = [0] * episodes
            self.sched_single = schedule
            self.spia_single = IncomeAnnuity(bonds, life_table, payout_delay = 12 * payout_delay,
                frequency = round(1 / self.env.params.time_period), cpi_adjust = 'all', date_str = self.env.date.isoformat(), schedule = schedule)
            self.sched_single_zero = True

        else:

            self.spia_single = None

    def add(self, age = None, premium = None, payout = None, adjustment = 0, joint = False, payout_fraction = 0, exclusion_period = 0, exclusion_amount = 0):

        assert (premium == None) != (payout == None)

        if premium != None:
            assert joint
            mwr = self.env.params.real_spias_mwr if self.real else self.env.params.nominal_spias_mwr
            start = max(1, self.env.preretirement_years)
            payout = self._spia_payout(start, adjustment, payout_fraction, premium, mwr)
        else:
            try:
                payout_low, payout_high = payout
            except TypeError:
                pass
            else:
                payout = self.env.log_uniform(payout_low, payout_high)
            if age == None:
                start = self.env.preretirement_years
            else:
                owner_age = self.env.age if self.owner == 'self' else self.env.age2
                start = age - owner_age

        if not self.real:
            payout *= self.env.cpi
            exclusion_amount *= self.env.cpi

        if joint or ((self.owner == 'self') == self.env.only_alive2):
            actual_payout_fraction = self.payout_fraction
        else:
            actual_payout_fraction = 1

        self._add_sched(start, float('inf'), payout, actual_payout_fraction, adjustment)

        if self.type_of_funds == 'taxable' and exclusion_period > 0:

            # Shift nominal exclusion amount from taxable to tax free income.
            if premium != None:
                while exclusion_amount > payout:
                    exclusion_period += 1
                    if adjustment == 0:
                        exclusion_amount = premium / exclusion_period
                    else:
                        exclusion_amount = premium * adjustment / ((1 + adjustment) ** exclusion_period - 1)
                    exclusion_amount *= self.env.cpi
            end = start + exclusion_period
            db = self.env.get_db(self.type, self.owner, 0, self.joint, self.payout_fraction, 'taxable')
            db._add_sched(start, end, - exclusion_amount, actual_payout_fraction, adjustment)
            db = self.env.get_db(self.type, self.owner, 0, self.joint, self.payout_fraction, 'tax_free')
            db._add_sched(start, end, exclusion_amount, actual_payout_fraction, adjustment)

    def _spia_payout(self, payout_delay, adjustment, payout_fraction, premium, mwr):

        bonds = self.env.bonds.real if self.real else self.env.bonds.nominal
        life_table, life_table2 = self.env.spia_life_tables(self.env.age, self.env.age2)
        schedule = lambda y: (1 + adjustment) ** y

        spia = IncomeAnnuity(bonds, life_table, life_table2 = life_table2, payout_delay = 12 * payout_delay, joint_contingent = True,
            joint_payout_fraction = payout_fraction, frequency = round(1 / self.env.params.time_period), cpi_adjust = 'all', date_str = self.env.date.isoformat(),
            schedule = schedule)

        payout = spia.payout(premium, mwr = mwr) / self.env.params.time_period

        return payout

    def _add_sched(self, start, end, payout, payout_fraction, adjustment):

        #print('_add_sched:', start, end, payout, payout_fraction, adjustment)

        payout /= self.env.params.time_period
        for e in range(ceil(max(start / self.env.params.time_period, 0)), floor(min(end / self.env.params.time_period + 1, len(self.sched)))):
            adjust = (1 + adjustment) ** e
            self.sched[e] += payout * adjust
            if self.spia_single:
                self.sched_single[e] += payout * payout_fraction * adjust

        if self.spia_single and payout_fraction > 0:
            self.sched_single_zero = False

    def payout(self):

        payout = self.sched[0]
        if not self.real:
            payout /= self.env.cpi

        return payout

    def couple_became_single(self):

        self.spia = self.spia_single
        self.sched = self.sched_single
        self.owner = self.owner_single
        self.spia_single = None

    def step(self, steps):

        del self.sched[:steps]
        if self.spia_single:
            del self.sched_single[:steps]

        self.spia.set_age(self.env.age if self.owner == 'self' else self.env.age2)

    def render(self):

        try:
            payout = self.sched[0]
        except IndexError:
            payout = 0
        pv = self.pv()
        if not self.real:
            payout /= self.env.cpi

        print('    ', self.type_of_funds, payout, self.real, pv)

    def pv(self):

        pv = self.spia.premium(1)
        if not self.real:
            pv /= self.env.cpi

        return pv
