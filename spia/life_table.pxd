# SPIA - Income annuity (SPIA and DIA) price calculator
# Copyright (C) 2021 Gordon Irlam
#
# This program may be licensed by you (at your option) under an Open
# Source, Free for Non-Commercial Use, or Commercial Use License.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is free for non-commercial use: you can use and modify it
# under the terms of the Creative Commons
# Attribution-NonCommercial-ShareAlike 4.0 International Public License
# (https://creativecommons.org/licenses/by-nc-sa/4.0/).
#
# A Commercial Use License is available in exchange for agreed
# remuneration.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from spia.income_annuity cimport IncomeAnnuity

cdef class LifeTable:

    cdef str table
    cdef str sex
    cdef object age
    cdef double death_age
    cdef str ae
    cdef object le_set
    cdef double le_add
    cdef str date_str
    cdef double _age_add
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

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object _q_int(self, double year, int age, double contract_age)

    cdef object q(self, double age, double year = ?, double contract_age = ?)
