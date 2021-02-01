# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from spia.income_annuity cimport IncomeAnnuity

from gym_fin.bonds cimport BondsSet
from gym_fin.fin cimport Fin
from gym_fin.fin_params cimport FinParams

cdef class DefinedBenefit:

    cdef Fin env
    cdef FinParams params
    cdef bint real
    cdef str type_of_funds
    cdef IncomeAnnuity spia_preretirement
    cdef IncomeAnnuity spia_retired

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object payout(self, double cpi)

    cdef object step(self, double age, bint retired, bint alive, bint alive2)

    #cdef object pv(self, double cpi, bint preretirement = ?, bint retired = ?)
        # No cdef due to optional arguments.
