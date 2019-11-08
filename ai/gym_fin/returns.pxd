# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

cdef class Returns:
    cdef double ret
    cdef double vol
    cdef double standard_error
    cdef double time_period

    cdef double mu
    cdef double sigma
    cdef double period_mu
    cdef double period_sigma
