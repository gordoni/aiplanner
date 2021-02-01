# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

cdef class Utility:

    cdef double gamma
    cdef double consume_charitable
    cdef double consume_charitable_utility_factor
    cdef double consume_charitable_gamma
    cdef double consume_charitable_discount_rate

    cdef double utility_scale
    cdef double crra_utility_base
    cdef double crra_utility_charitable
    cdef double marginal_utility_factor

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object crra_utility(self, double gamma, double c)

    cpdef object utility(self, double c, double t = ?)
        # cpdef as currently needs to be accessible to cPython common/evaluator.py.
