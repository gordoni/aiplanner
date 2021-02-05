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
from spia.life_table cimport LifeTable
from spia.yield_curve cimport YieldCurve

from gym_fin.asset_allocation cimport AssetAllocation
from gym_fin.bonds cimport Bonds, BondsSet, Inflation
from gym_fin.defined_benefit cimport DefinedBenefit
from gym_fin.fin_params cimport FinParams
from gym_fin.policies cimport Policy
from gym_fin.returns_equity cimport Returns
from gym_fin.taxes cimport Taxes
from gym_fin.utility cimport Utility

cdef int STOCKS
cdef int REAL_BONDS
cdef int NOMINAL_BONDS
cdef int IID_BONDS

cdef class Fin:

    cdef double _age
    cdef double _age2
    cdef double _age_retirement
    cdef double _age_start
    cdef list _alive_both
    cdef list _alive_count
    cdef list _alive_one
    cdef list _alive_single
    cdef int _anticipated_episode_length
    cdef BondsSet _bonds
    cdef YieldCurve _bonds_constant_inflation
    cdef Bonds _bonds_stepper
    cdef YieldCurve _bonds_zero
    cdef double _ce_estimate_individual
    cdef double _consume_charitable
    cdef double _consume_fraction_estimate
    cdef double _consume_preretirement
    cdef double _consume_scale
    cdef bint _couple
    cdef double _couple_weight
    cdef double _cpi
    cdef str _date
    cdef object _date_start
    cdef double _death_age
    cdef dict _defined_benefits
    cdef bint _direct_action
    cdef double e
    cdef int _env_timesteps
    cdef int _episode_length
    cdef double _gamma
    cdef double _gi_regular
    cdef double _gi_social_security
    cdef double _gi_total
    cdef bint _have_401k
    cdef bint _have_401k2
    cdef bint _init_done
    cdef Returns _iid_bonds
    cdef double _income_preretirement
    cdef double _income_preretirement2
    cdef double _income_preretirement_years
    cdef double _income_preretirement_years2
    cdef bint _info_rewards
    cdef bint _info_rollouts
    cdef bint _info_strategy
    cdef list _life_expectancy_both
    cdef list _life_expectancy_one
    cdef list _life_percentile
    cdef LifeTable _life_table
    cdef LifeTable _life_table2
    cdef LifeTable _life_table2_preretirement
    cdef LifeTable _life_table_le_hi
    cdef LifeTable _life_table_preretirement
    cdef double _net_gi
    cdef double _net_wealth
    cdef double _net_wealth_pretax
    cdef list _observation_space_extreme_range
    cdef list _observation_space_high
    cdef object _observation_space_high_np
    cdef list _observation_space_items
    cdef list _observation_space_low
    cdef object _observation_space_low_np
    cdef list _observation_space_range_exceeded
    cdef list _observation_space_scale
    cdef list _observation_space_shift
    cdef bint _only_alive2
    cdef double _p_fraction
    cdef double _p_plus_income
    cdef double _p_sum
    cdef double _p_tax_deferred
    cdef double _p_tax_free
    cdef double _p_taxable
    cdef double _p_wealth
    cdef double _p_wealth_pretax
    cdef FinParams _params
    cdef dict _params_dict
    cdef Policy _policy
    cdef double _preretirement_fraction
    cdef double _preretirement_income_wealth
    cdef double _preretirement_years
    cdef AssetAllocation _prev_asset_allocation
    cdef double _prev_consume_rate
    cdef double _prev_inflation
    cdef double _prev_nominal_spias_purchase
    cdef double _prev_real_spias_purchase
    cdef double _prev_ret
    cdef double _prev_reward
    cdef AssetAllocation _prev_taxable_assets
    cdef list _pv_preretirement_income
    cdef list _pv_retired_income
    cdef double _pv_social_security
    cdef double _pv_taxes
    cdef double _raw_preretirement_income_wealth
    cdef double _regular_tax_rate
    cdef double _retired_income_wealth
    cdef double _retired_income_wealth_pretax
    cdef list _retirement_expectancy_both
    cdef list _retirement_expectancy_one
    cdef list _retirement_expectancy_single
    cdef double _reward_scale
    cdef double _rough_ce_estimate_individual
    cdef str _sex2
    cdef bint _spias
    cdef bint _spias_ever
    cdef bint _spias_required
    cdef double _start_income_preretirement
    cdef double _start_income_preretirement2
    cdef Returns _stocks
    cdef AssetAllocation _tax_deferred_assets
    cdef AssetAllocation _tax_free_assets
    cdef AssetAllocation _taxable_assets
    cdef Taxes _taxes
    cdef double _taxes_due
    cdef double _taxes_paid
    cdef Utility _utility
    cdef dict _warnings
    cdef double _wealth_tax_deferred
    cdef double _wealth_tax_free
    cdef double _wealth_taxable
    cdef double _years_retired

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object _gi_sum(self)

    cdef object _decode_action(self, object action_or_list, AssetAllocation spare_asset_allocation)

    cdef object _raw_reward(self, double consume_rate)

    cdef object _spend(self, double consume_fraction, double real_spias_fraction, double nominal_spias_fraction)

    cdef object _allocate_aa(self, double p_tax_free, double p_tax_deferred, double p_taxable, AssetAllocation target_asset_allocation)

    cpdef object step(self, object action)
        # cpdef as needs to be accessible to cPython.

    cdef object _step(self, int steps = ?, bint force_family_unit = ?, bint forced_family_unit_couple = ?)

    cdef object _pre_calculate_wealth(self, double growth_rate = ?)

    cdef object _pre_calculate(self)

    cdef object _observe(self)
