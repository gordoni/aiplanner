#!/usr/bin/env python3

# SPIA - Income annuity (SPIA and DIA) price calculator.
# Copyright (C) 2014-2018 Gordon Irlam
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from . import IncomeAnnuity, LifeTable, YieldCurve

if __name__ == '__main__':

    yield_curve = YieldCurve('nominal', '2018-01-01')
    life_table = LifeTable('iam2012-basic', 'male', 65)
    income_annuity = IncomeAnnuity(yield_curve, life_table, payout_delay = 1.5)
    payout = income_annuity.payout(100000, mwr = 1)
    print('Monthly payout for a $100,000 premium:', payout)
    premium = income_annuity.premium(payout, mwr = 1)
    assert abs(premium - 100000) < 1e-6
    mwr = income_annuity.mwr(premium, payout)
    assert abs(mwr - 1) < 1e-9
