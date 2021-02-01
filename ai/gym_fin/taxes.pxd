# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from gym_fin.asset_allocation cimport AssetAllocation
from gym_fin.fin_params cimport FinParams

cdef class Taxes:

    cdef FinParams params
    cdef AssetAllocation value
    cdef AssetAllocation basis
    cdef double cpi
    cdef double cg_carry
    cdef double capital_gains
    cdef double qualified_dividends
    cdef double non_qualified_dividends
    cdef double charitable_contributions_carry

    cdef double federal_standard_deduction_single
    cdef double federal_standard_deduction_joint

    cdef tuple federal_table_single

    cdef tuple federal_table_joint

    cdef tuple federal_long_term_gains_single

    cdef tuple federal_long_term_gains_joint

    cdef double contribution_limit_401k
    cdef double contribution_limit_401k_catchup
    cdef double contribution_limit_ira
    cdef double contribution_limit_ira_catchup

    cdef double federal_max_capital_loss

    cdef tuple ss_taxable_single

    cdef tuple ss_taxable_couple

    cdef double niit_threshold_single
    cdef double niit_threshold_couple
    cdef double niit_rate

    cdef double charitable_deduction_limit

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object buy_sell(self, int ac, double amount, double new_value, double ret, double dividend_yield, double qualified)

    cdef object _tax_table(self, tuple table, double income, double start)

    cdef object _marginal_rate(self, tuple table, double income)

    cdef object calculate_taxes(self, double regular_income, double social_security, double capital_gains, double nii, double charitable_contributions, bint single)

    cdef object tax(self, double regular_income, double social_security, double charitable_contributions, bint single, double inflation)

    cdef object observe(self)

