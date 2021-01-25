# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

cdef class LifeTable:

    cdef str table
    cdef str sex
    cdef double age
    cdef double death_age
    cdef str ae
    cdef object le_set
    cdef double le_add
    cdef str date_str
    cdef bint interpolate_q
    cdef double alpha
    cdef double m
    cdef double b

    cdef dict table_ssa_cohort
    cdef tuple table_iam2012_basic
    cdef bint gompertz_makeham
    cdef bint fixed
    cdef tuple aer_years
    cdef dict table_ae
    cdef tuple table_ae_summary
    cdef dict table_ae_full
    cdef tuple projection_scale

    cdef double age_add

    # Worthwhile cpdef'ing a few methods because they are called so frequently, looking up their attributes would slow things down.
    # Return object so that exceptions can propagate.

    cpdef object _q_int(self, double year, int age, double contract_age)

    cpdef object q(self, double age, double year = ?, double contract_age = ?)
