# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from gym_fin.fin_params cimport FinParams

cdef class Returns:

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object sample(self)

    cdef object observe(self)

cdef class ReturnsIID(Returns):

    cdef double ret
    cdef double vol
    cdef double standard_error
    cdef double time_period

    cdef double mu
    cdef double sigma
    cdef double period_mu
    cdef double period_sigma

    cdef object sample(self)

    cdef object observe(self)

cdef tuple z_hist
cdef tuple sigma_hist
cdef double sigma_average

cdef class ReturnsEquity(Returns):

    cdef FinParams params
    cdef bint bootstrap
    cdef double bootstrap_years
    cdef double sigma_max
    cdef double mu
    cdef double sigma
    cdef double alpha
    cdef double gamma
    cdef double beta
    cdef double price_exaggeration
    cdef double price_low
    cdef double price_high
    cdef double price_noise_sigma
    cdef double mean_reversion_rate
    cdef double standard_error
    cdef double time_period

    cdef double e

    cdef double periods_per_year
    cdef double sigma_period
    cdef double omega
    cdef int block_size
    cdef int last_randint
    cdef list randints
    cdef int last_randnorm
    cdef list randnorm
    cdef double sigma_t

    cdef double period_mu
    cdef double period_mean_reversion_rate
    cdef double log_price_noise
    cdef double log_above_trend
    cdef int t

    cdef object sample(self)

    cdef object observe(self)
