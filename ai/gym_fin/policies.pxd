# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from gym_fin.fin cimport Fin
from gym_fin.fin_params cimport FinParams

cdef class Policy:
    cdef Fin env
    cdef FinParams params
    cdef double consume_rate_initial
    cdef double p_initial
    cdef double consume_prev

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object policy(self, tuple action)
