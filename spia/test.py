#!/usr/bin/env python3

# SPIA - Income annuity (SPIA and DIA) price calculator
# Copyright (C) 2014-2019 Gordon Irlam
#
# This program may be licensed by you (at your option) under an Open
# Source, Free for Non-Commercial Use, or Commercial Use License.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is free for non-commercial use: you can use and modify it
# under the terms of the Creative Commons
# Attribution-NonCommercial-ShareAlike 4.0 International Public License
# (https://creativecommons.org/licenses/by-nc-sa/4.0/).
#
# A Commercial Use License is available in exchange for agreed
# remuneration.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

try:
    import cython
except ImportError:
    class cython:
        def cclass(x):
            return x
        def locals(**kwargs):
            return lambda x: x
        def bint():
            pass
        def int():
            pass
        def double():
            pass

from . import LifeTable, YieldCurve
from .factory import make_income_annuity

@cython.cclass
class Test:

  def test(self):

        yield_curve_nominal = YieldCurve('nominal', '2017-06-10')
        yield_curve_real = YieldCurve('real', '2017-06-10')
        yield_curve_corporate = YieldCurve('corporate', '2017-06-10')
        yield_curve_zero = YieldCurve('fixed', '2017-06-10')
        yield_curve_fixed = YieldCurve('fixed', '2017-06-10', adjust = 0.02)
        yield_curve_le = YieldCurve('le', '2017-06-10')

        life_table_iam = LifeTable('iam2012-basic', 'male', ae = 'aer2005_08-summary')
        life_table_ssa = LifeTable('ssa-cohort', 'male')
        life_table2_ssa = LifeTable('ssa-cohort', 'female')

        def p(x):
            print(round(x, 9))

        print('Basic tests:')
        income_annuity: IncomeAnnuity
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_iam, age = 65, payout_delay = 1.5)
        payout = income_annuity.payout(100000, mwr = 1)
        p(payout)
        premium = income_annuity.premium(payout, mwr = 1)
        print(abs(premium - 100000) < 1e-6)
        mwr = income_annuity.mwr(premium, payout)
        print(abs(mwr - 1) < 1e-9)

        print('Life expectancy:')
        income_annuity = make_income_annuity(yield_curve_le, life_table_ssa, age = 65)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_le, life_table_ssa, age = 65, percentile = 0.95)
        p(income_annuity.premium())

        print('Single:')
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 0, adjust = 0.02, price_adjust = 'all')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 0, adjust = 0.02, price_adjust = 'payout')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 0, adjust = 0.02, price_adjust = 'calendar')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 1.5, adjust = 0.02, price_adjust = 'all')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 1.5, adjust = 0.02, price_adjust = 'payout')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 1.5, adjust = 0.02, price_adjust = 'calendar')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 18, adjust = 0.02, price_adjust = 'all')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 18, adjust = 0.02, price_adjust = 'payout')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 18, adjust = 0.02, price_adjust = 'calendar')
        p(income_annuity.premium())

        print('Couple:')
        income_annuity = make_income_annuity(yield_curve_real, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 0, payout_fraction = 0.6)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_real, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 1.5, payout_fraction = 0.6)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_real, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 18, payout_fraction = 0.6)
        p(income_annuity.premium())

        print('Income annuity parameters:')
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, payout_delay = 1.5)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, payout_delay = 1.5, payout_end = 120)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 1.5, payout_fraction = 0.6, joint = True, price_adjust = 'all')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 1.5, payout_fraction = 0.6, joint = False, contingent2 = False, price_adjust = 'all')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 1.5, payout_fraction = 0.6, joint = False, contingent2 = True, price_adjust = 'all')
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, payout_delay = 1.5, period_certain = 10)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, payout_delay = 1.5, frequency = 1)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, payout_delay = 1.5, frequency = 0.5)
        p(income_annuity.premium())
        income_annuity = make_income_annuity(yield_curve_corporate, life_table_ssa, age = 65, payout_delay = 1.5, frequency = 0.6)
        p(income_annuity.premium())

        print('Fixed interest rate:')
        ia: IncomeAnnuity; ia2: IncomeAnnuity
        ia = make_income_annuity(yield_curve_zero, life_table_ssa, age = 65, payout_delay = 6, adjust = 1 / (1 + 0.02) - 1, price_adjust = 'all')
        premium1 = ia.premium()
        p(premium1)
        ia2 = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 65, payout_delay = 6, price_adjust = 'all')
        premium2 = ia2.premium()
        p(premium2)
        print(abs(premium1 - premium2 * (1 + 0.02) ** 0.5) < 1e-9)

        print('Regular set age / add schedule:')
        ia = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 65, payout_delay = 1.5)
        premium1 = ia.premium()
        p(premium1)
        ia.set_age(70)
        premium2 = ia.premium()
        p(premium2)
        ia.add_schedule(schedule = 2)
        premium3 = ia.premium()
        p(premium3)
        print(abs(3 * premium2 - premium3) < 1e-9)
        print(ia.schedule_payout() == 3)
        ia = make_income_annuity(yield_curve_nominal, life_table_ssa, age = 70, payout_delay = 1.5, date_str = '2022-06-10', delay_calcs = True)
        ia.add_schedule(schedule = 2, delay_calcs = True)
        ia.add_schedule(schedule = 0)
        premium4 = ia.premium()
        p(premium4)
        print(abs(premium4 - premium3) < 1e-9)

        print('Cacheable set age / add schedule single:')
        ia = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 65, payout_delay = 1.5, price_adjust = 'all')
        premium1 = ia.premium()
        p(premium1)
        ia.add_schedule(schedule = 2, price_adjust = 'all')
        premium2 = ia.premium()
        p(premium2)
        print(abs(3 * premium1 - premium2) < 1e-9)
        ia.set_age(70)
        premium3 = ia.premium()
        p(premium3)
        ia2 = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 70, payout_delay = 1.5, price_adjust = 'all', date_str = '2022-06-10', schedule = lambda y: 3)
        premium4 = ia2.premium()
        p(premium4)
        print(abs(premium4 - premium3) < 1e-9)
        print(ia.schedule_payout() == 3)
        ia.add_schedule(schedule = -2, price_adjust = 'all')
        premium5 = ia.premium()
        p(premium5)
        ia.set_age(70)
        premium6 = ia.premium()
        p(premium6)
        print(abs(premium6 - premium5) < 1e-9)
        ia2 = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 70, payout_delay = 1.5, price_adjust = 'all', date_str = '2022-06-10')
        premium7 = ia2.premium()
        p(premium7)
        print(abs(premium7 - premium6) < 1e-9)

        print('Cacheable set age / add schedule couple:')
        ia = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 1.5, payout_fraction = 0.5, price_adjust = 'all')
        premium1 = ia.premium()
        p(premium1)
        ia.add_schedule(schedule = 2, payout_fraction = 0.5, price_adjust = 'all')
        premium2 = ia.premium()
        p(premium2)
        print(abs(3 * premium1 - premium2) < 1e-9)
        ia.set_age(70, alive = True, alive2 = False)
        print(ia.schedule_payout() == 1.5)
        premium3 = ia.premium()
        p(premium3)
        ia.set_age(70, alive = False, alive2 = True)
        print(ia.schedule_payout() == 1.5)
        premium4 = ia.premium()
        p(premium4)
        ia.set_age(70)
        print(ia.schedule_payout() == 3)
        premium5 = ia.premium()
        p(premium5)
        print(abs(premium5 - (premium3 + premium4)) < 1e-9)
        ia.add_schedule(schedule = 1, payout_fraction = 0.5, price_adjust = 'all')
        premium6 = ia.premium()
        p(premium6)
        ia.set_age(70)
        premium7 = ia.premium()
        p(premium7)
        print(abs(premium7 - premium6) < 1e-9)
        ia2 = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 70, life_table2 = life_table2_ssa, age2 = 65, payout_delay = 1.5, payout_fraction = 0.5, price_adjust = 'all', date_str = '2022-06-10', schedule = lambda y: 4)
        premium8 = ia2.premium()
        p(premium8)
        print(abs(premium8 - premium7) < 1e-9)
        print(ia.schedule_payout() == 4)
        print(ia.schedule_payout(True, False) == 2)
        print(ia.schedule_payout(False, True) == 2)
        print(ia.schedule_payout(False, False) == 0)

        print('Shared vital stats:')
        ia = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 65, life_table2 = life_table2_ssa, age2 = 60, payout_delay = 1.5, payout_fraction = 0.5, price_adjust = 'all')
        ia.set_age(70)
        ia2 = make_income_annuity(yield_curve_fixed, None, vital_stats = ia.vital_stats, payout_delay = 1.5, payout_fraction = 0.5, price_adjust = 'all')
        ia.set_age(80)
        premium1 = ia.premium()
        p(premium1)
        ia2.set_age(80)
        premium2 = ia2.premium()
        p(premium2)
        print(abs(premium2 - premium1) < 1e-9)

        print('Payout start:')
        schedule = lambda y: 0 if y < 10 else 1
        ia = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 65, payout_delay = 0, frequency = 1, price_adjust = 'all', schedule = schedule)
        ia2 = make_income_annuity(yield_curve_fixed, life_table_ssa, age = 65, payout_delay = 0, payout_start = 10, frequency = 1, price_adjust = 'all')
        print(ia.schedule_payout() == 0)
        print(ia2.schedule_payout() == 0)
        premium1 = ia.premium()
        p(premium1)
        premium2 = ia2.premium()
        p(premium2)
        print(abs(premium2 - premium1) < 1e-9)
        ia.set_age(70)
        ia2.set_age(70)
        print(ia.schedule_payout() == 0)
        print(ia2.schedule_payout() == 0)
        premium3 = ia.premium()
        p(premium3)
        premium4 = ia2.premium()
        p(premium4)
        print(abs(premium4 - premium3) < 1e-9)
        ia.set_age(80)
        ia2.set_age(80)
        print(ia.schedule_payout() == 1)
        print(ia2.schedule_payout() == 1)
        premium5 = ia.premium()
        p(premium5)
        premium6 = ia2.premium()
        p(premium6)
        print(abs(premium6 - premium5) < 1e-9)
        ia.add_schedule(schedule = 1)
        ia2.add_schedule(schedule = 1)
        print(ia.schedule_payout() == 2)
        print(ia2.schedule_payout() == 2)
        premium7 = ia.premium()
        p(premium7)
        premium8 = ia2.premium()
        p(premium8)
        print(abs(premium8 - premium7) < 1e-9)

Test().test()
