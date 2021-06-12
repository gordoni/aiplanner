# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from gym_fin.ou_process cimport OUProcess

cdef class BondsBase:

    cdef str _interest_rate
    cdef double e

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cpdef object step(self)
        # cpdef so Inflation can super(Inflation, self).step(), and so we can declare the fin.py self._bonds_stepper as type Bonds.

    cdef object observe(self)

cdef class Bonds(BondsBase):

    cdef double a
    cdef double sigma
    cdef object yield_curve
    cdef str r0_type
    cdef double r0
    cdef double standard_error
    cdef bint static_bonds
    cdef double time_period

    cdef double mean_short_interest_rate
    cdef dict _sr_cache

    cdef double adjust
    cdef double sir_init
    cdef double sir0
    cdef double t
    cdef OUProcess oup
    cdef bint _lpv_cache_valid
    cdef double _lpv_cache
    cdef dict _discount_cache

    cdef object _short_interest_rate(self, bint next = ?)

    cdef object _log_present_value(self, double t, bint next = ?)

    cdef object sample(self, double duration)

    cpdef object step(self)

cdef class RealBonds(Bonds):

    cdef object _short_interest_rate(self, bint next = ?)

    cdef object observe(self)

cdef class YieldCurveSum:

    cdef object yield_curve1
    cdef object yield_curve2
    cdef double weight
    cdef double offset

    cdef str _interest_rate
    cdef str _date
    cdef str _date_low
    cdef double exp_offset

cdef class Inflation(Bonds):

    cdef double inflation_a
    cdef double inflation_sigma
    cdef double bond_a
    cdef double bond_sigma
    cdef object nominal_yield_curve
    cdef double inflation_risk_premium
    cdef double real_liquidity_premium
    cdef bint model_bond_volatility

    cdef double nominal_premium
    cdef dict _sir_cache

    cdef OUProcess inflation_oup

    cdef object _sir_no_adjust(self, double t, double a, double sigma)

    cdef object _short_interest_rate(self, bint next = ?)

    cdef object _model_short_interest_rate(self)

    cdef object inflation(self)

    cdef object sample(self, double duration)

    cpdef object step(self)

cdef class NominalBonds(Bonds):

    cdef RealBonds real_bonds
    cdef Inflation inflation
    cdef double real_bonds_adjust
    cdef double nominal_bonds_adjust

    cdef object sample(self, double duration)

    cpdef object step(self)

cdef class CorporateBonds(BondsBase):

    cdef NominalBonds nominal_bonds
    cdef double corporate_nominal_spread

    cdef double exp_spread

cdef class BondsSet:

    cdef double fixed_real_bonds_rate
    cdef double fixed_nominal_bonds_rate
    cdef double time_period
    cdef RealBonds real
    cdef NominalBonds nominal
    cdef CorporateBonds corporate
    cdef Inflation inflation
