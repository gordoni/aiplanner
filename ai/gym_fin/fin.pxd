cdef class Fin:
    cdef readonly bint only_alive2
    cdef object alive_single
    cdef readonly object alive_count
    cdef object life_expectancy_both
    cdef object life_expectancy_one
    cdef object life_percentile
    cdef object retirement_expectancy_both
    cdef object retirement_expectancy_one
    cdef object retirement_expectancy_single
    cdef bint direct_action
    cdef readonly object params
    cdef object action_space
    cdef object observation_space_items
    cdef object observation_space
    cdef object observation_space_range
    cdef object observation_space_scale
    cdef object observation_space_shift
    cdef object observation_space_extreme_range
    cdef object observation_space_range_exceeded
    cdef long long env_timesteps
    cdef long long env_couple_timesteps
    cdef long long env_single_timesteps
    cdef bint _init_done
    cdef object _cvs_key
    cdef double life_table_age
    cdef double life_table2_age
    cdef double age_start
    cdef double death_age
    cdef object life_table_le_hi
    cdef object stocks
    cdef object iid_bonds
    cdef object bills
    cdef object bonds
    cdef object bonds_stepper
    cdef readonly object bonds_zero
    cdef readonly object bonds_constant_inflation
    cdef object defined_benefits
    cdef readonly object sex2
    cdef readonly double age
    cdef readonly double age2
    cdef double age_retirement
    cdef readonly object life_table
    cdef double life_table_le_add
    cdef readonly object life_table2
    cdef double life_table_le_add2
    cdef readonly double preretirement_years
    cdef readonly object life_table_preretirement
    cdef readonly object life_table2_preretirement
    cdef readonly bint couple
    cdef bint have_401k
    cdef bint have_401k2
    cdef double taxes_due
    cdef double gamma
    cdef object date_start
    cdef readonly object date
    cdef readonly double cpi
    cdef readonly long episode_length
    cdef double start_income_preretirement
    cdef double start_income_preretirement2
    cdef readonly double income_preretirement_years
    cdef readonly double income_preretirement_years2
    cdef double income_preretirement
    cdef double income_preretirement2
    cdef double consume_preretirement
    cdef double p_tax_free
    cdef double p_tax_deferred
    cdef double p_taxable
    cdef object taxes
    cdef object prev_asset_allocation
    cdef object prev_taxable_assets
    cdef object prev_real_spias_rate
    cdef object prev_nominal_spias_rate
    cdef object prev_consume_rate
    cdef object prev_reward
    cdef double consume_scale
    cdef readonly object utility
    cdef double reward_scale
    cdef readonly double reward_weight
    cdef readonly double reward_consume
    cdef readonly double reward_value
    cdef readonly double estate_weight
    cdef readonly double estate_value
    cdef double prev_ret
    cdef double prev_inflation
    cdef object pv_preretirement_income
    cdef object pv_retired_income
    cdef double pv_social_security
    cdef double retired_income_wealth_pretax
    cdef double years_retired
    cdef double couple_weight
    cdef double wealth_tax_free
    cdef double wealth_tax_deferred
    cdef double wealth_taxable
    cdef readonly double p_wealth
    cdef double raw_preretirement_income_wealth
    cdef double net_wealth_pretax
    cdef double rough_ce_estimate_individual
    cdef double taxable_basis
    cdef readonly double pv_taxes
    cdef double regular_tax_rate
    cdef readonly double preretirement_income_wealth
    cdef double net_wealth
    cdef readonly double retired_income_wealth
    cdef double ce_estimate_individual
    cdef double consume_net_wealth_estimate
    cdef double p_fraction
    cdef double preretirement_fraction
    cdef double wealth_ratio
    cdef double taxes_paid
    cdef double p_plus_income
    cdef bint spias_ever
    cdef bint spias_required
    cdef object spias
