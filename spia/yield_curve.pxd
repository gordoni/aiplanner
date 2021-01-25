# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

cdef class YieldCurve:

    cdef str _interest_rate
    cdef str _date
    cdef str _date_low
    cdef double adjust
    cdef bint permit_stale_days
    cdef bint cache

    cdef bint _interest_rate_fixed
    cdef bint _interest_rate_le
    cdef double _log_1_plus_adjust
    cdef dict _spot_cache
    cdef str yield_curve_date
    cdef str _datadir
    cdef object monotone_convex

    # Worthwhile cpdef'ing _q_int() and q() because they are called so frequently, looking up their attributes would slow things down.
