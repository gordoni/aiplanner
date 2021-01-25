# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from .life_table cimport LifeTable

cdef class IncomeAnnuity:

    cdef object yield_curve
        # Don't change this to YieldCurve.
        # Want to be able to substitute in any object that provides the properties interest_rate, date, date_low, and discount_rate().
        # Such as ai/gym_fin/bonds.py.
    cdef double payout_delay
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

    cdef bint recompute_vital_stats
    cdef bint cacheable_payout
    cdef list calcs
    cdef double start_age1

    cdef IncomeAnnuity _vital_stats

    cdef bint alive
    cdef bint alive2
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
