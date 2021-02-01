# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

cdef class OUProcess:

    cdef double time_period
    cdef double _rev
    cdef double _sigma
    cdef double _mu

    cdef double _e
    cdef int _last_randnorm
    cdef list _randnorm
    cdef double x
    cdef double next_x
    cdef double norm

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object step(self, object norm = ?)
