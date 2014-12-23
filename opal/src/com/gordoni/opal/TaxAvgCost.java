/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2015 Gordon Irlam
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

package com.gordoni.opal;

import java.util.Arrays;

class TaxAvgCost extends Tax
{
        private double cpi;
        private double[] basis;
        private double[] value;
        private double[] prev_aa;

        void initial(double p, double[] aa)
        {
                if (p < 0)
                        p = 0;
                cpi = 1;
                basis = new double[scenario.normal_assets];
                value = new double[scenario.normal_assets];
                for (int i = 0; i < basis.length; i++)
                {
                        basis[i] = aa[i] * p;
                        value[i] = aa[i] * p;
                }
                prev_aa = aa;
                cg_carry = 0;
        }

        private double try_tax(double p, double p_preinvest, double[] aa, double[] returns, boolean do_it)
        {
                if (p < 0)
                        p = 0;
                if (p_preinvest < 0)
                        p_preinvest = 0;
                double cpi_delta = 1 + returns[scenario.cpi_index];
                double new_cpi = cpi * cpi_delta;
                double income = 0;
                for (int i = 0; i < value.length; i++)
                {
                        double ret = 1 + returns[i];
                        double base = basis[i];
                        double val = value[i];
                        double alloc = aa[i];
                        assert(aa[i] >= 0);
                        double target = alloc * p;
                        double invest_start = prev_aa[i] * p_preinvest;
                        double invest_final = invest_start * ret;
                        double buy_sell_0 = invest_start - val;
                        if (buy_sell_0 < 0)
                        {
                                double gain = - buy_sell_0 * (val - base) / val;
                                income += gain / cpi_delta;
                                double target_fract_0 = invest_start / val;
                                base *= target_fract_0;
                                // Sanity check code commented out.
                                // val *= target_fract_0;
                        }
                        else
                        {
                                base += buy_sell_0;
                                // val += buy_sell_0;
                        }
                        base /= cpi_delta;
                        // val *= ret;
                        double dividend = dividend_tax(i, invest_final);
                        income += dividend;
                        // val -= dividend;
                        double buy_sell_1 = target - invest_final + dividend;  // Reinvest dividend.
                        if (buy_sell_1 < 0)
                        {
                                double start_1 = target - buy_sell_1;
                                double gain = - buy_sell_1 * (start_1 - base) / start_1;
                                income += gain;
                                double target_fract_1 = target / start_1;
                                base *= target_fract_1;
                                // val *= target_fract_1;
                        }
                        else
                        {
                                base += buy_sell_1;
                                // val += buy_sell_1;
                        }
                        if (do_it)
                        {
                                basis[i] = base;
                                assert(basis[i] >= 0);
                                value[i] = target;
                                // assert(-1e-6 * scenario.consume_max_estimate < val - value[i] && val - value[i] < 1e-6 * scenario.consume_max_estimate);
                                assert(value[i] >= 0);
                        }
                }
                double tax = total_tax(income, cpi_delta, do_it);
                if (do_it)
                {
                        cpi = new_cpi;
                        prev_aa = aa;
                }
                return tax;
        }

        double total_pending(double p, double p_preinvest, double[] aa, double[] returns)
        {
                return try_tax(0, p_preinvest, aa, returns, false);
        }

        double tax(double p, double p_preinvest, double[] aa, double[] returns)
        {
                 return try_tax(p, p_preinvest, aa, returns, true);
        }

        public TaxAvgCost(Scenario scenario)
        {
                super(scenario);
        }

        public String toString()
        {
            return "cpi: " + cpi + "\nbasis: " + Utils.sum(basis) + " " + Arrays.toString(basis) + "\nvalue: " + Utils.sum(value) + " " + Arrays.toString(value) + "\ncarry forward: " + cg_carry + "\n";
        }
}
