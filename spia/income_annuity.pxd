# SPIA - Income annuity (SPIA and DIA) price calculator
# Copyright (C) 2021 Gordon Irlam
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

from .life_table cimport LifeTable

cdef class IncomeAnnuity:

    cdef object yield_curve
        # Don't change this to YieldCurve.
        # Want to be able to substitute in any object that provides the properties interest_rate, date, date_low, and discount_rate().
        # Such as ai/gym_fin/bonds.py.
    cdef double age
    cdef double age2
    cdef double payout_delay
    cdef int payout_start
    cdef object payout_end
    cdef double tax
    cdef LifeTable life_table1
    cdef LifeTable life_table2
    cdef IncomeAnnuity vital_stats_arg
    cdef double payout_fraction
    cdef bint joint
    cdef bint contingent2
    cdef double period_certain
    cdef double adjust
    cdef double frequency
    cdef str price_adjust
    cdef object percentile
    cdef str date
    cdef object schedule
    cdef bint delay_calcs
    cdef bint calculate

    cdef bint alive
    cdef bint alive2
    cdef double current_age

    cdef bint recompute_vital_stats
    cdef bint cacheable_payout
    cdef list calcs

    cdef IncomeAnnuity _vital_stats

    cdef double start
    cdef list alive1_array
    cdef list alive2_array
    cdef list alive1_delay_array
    cdef list alive2_delay_array
    cdef int alive_offset
    cdef list sched_alive
    cdef list sched_alive1_only
    cdef list sched_alive2_only
    cdef int sched_offset
    cdef double _sched_offset_discount

    cdef list _prices
    cdef list _prices1
    cdef list _prices2

    cdef double _duration
    cdef double _annual_return
    cdef double _unit_price

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object set_age(self, double age, bint alive = ?, bint alive2 = ?, bint delay_calcs = ?)

    cdef object _compute_price(self, bint use_cache)

    cdef object schedule_payout(self, object alive = ?, object alive2 = ?, int offset = ?)

    cdef object premium(self, double payout = ?, double mwr = ?)
