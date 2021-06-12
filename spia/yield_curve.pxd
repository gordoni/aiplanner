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

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

#cdef object discount_rate(self, double y)
        # No cdef because we want an attribute to be defined as income_annuity.pxd uses an object rather than a YieldCurve for the yield curve.
        # Don't use cpdef to get around this as the resulting code would call a stub which would then call the function slowing things down.