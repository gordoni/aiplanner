/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2016 Gordon Irlam
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

class TaxHifo extends Tax
{
        private final boolean avgcost = false; // Make hifo module behave like average cost. For debugging.

        private boolean fifo; // Make hifo module behave like fifo (assuming avgcost isn't set).

        private double cpi;
        private double[] total_shares;
        private double[] curr_prices;
        private double[][] shares;
        private double[][] prices;
        private int[] nexts;
        private double[] prev_aa;

        void initial(double p, double[] aa)
        {
                if (p < 0)
                        p = 0;
                total_shares = new double[scenario.normal_assets];
                curr_prices = new double[scenario.normal_assets];
                shares = new double[scenario.normal_assets][2 * (int) (scenario.ss.max_years * config.generate_time_periods) + 1];
                prices = new double[scenario.normal_assets][2 * (int) (scenario.ss.max_years * config.generate_time_periods) + 1];
                nexts = new int[scenario.normal_assets];
                cpi = 1;
                for (int a = 0; a < scenario.normal_assets; a++)
                {
                        total_shares[a] = aa[a] * p / scenario.consume_max_estimate; // Normalize shares so we can recognize rounding errors independent of scale.
                        curr_prices[a] = scenario.consume_max_estimate; // Although, at present we let rounding errors rest.
                        shares[a][0] = aa[a] * p / scenario.consume_max_estimate;
                        prices[a][0] = scenario.consume_max_estimate;
                        nexts[a] = 1;
                }
                prev_aa = aa;
                cg_carry = 0;
        }

        private void buy(int a, double share, double price, boolean do_it)
        {
                if (!do_it)
                        return;

                if (share == 0)
                        return;

                if (avgcost)
                {
                        total_shares[a] += share;
                        if (shares[a][0] + share != 0)
                                prices[a][0] = (prices[a][0] * shares[a][0] + price * share) / (shares[a][0] + share);
                        shares[a][0] += share;
                }
                else
                {
                        int next;
                        for (next = nexts[a]; next > 0 && (fifo || price < prices[a][next - 1]); next--)
                        {
                                shares[a][next] = shares[a][next - 1];
                                prices[a][next] = prices[a][next - 1];
                        }
                        total_shares[a] += share;
                        shares[a][next] = share;
                        prices[a][next] = price;
                        nexts[a]++;
                }
        }

        private double sell(int a, double share, double price, boolean do_it)
        {
                double cg = 0;

                if (avgcost)
                {
                        cg = (price - prices[a][0]) * share;
                        if (do_it)
                        {
                                total_shares[a] -= share;
                                shares[a][0] -= share;
                        }
                }
                else
                {
                        int next;
                        double to_go = share;
                        for (next = nexts[a]; next > 0; next--)
                        {
                                double lot = Math.min(to_go, shares[a][next - 1]);
                                cg += (price - prices[a][next - 1]) * lot;
                                if (do_it)
                                        shares[a][next - 1] -= lot;
                                to_go -= lot;
                                if (to_go == 0 && shares[a][next - 1] != 0)
                                        break;
                        }
                        if (do_it)
                        {
                                nexts[a] = next;
                                total_shares[a] -= share;
                        }
                }

                return cg;
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
                for (int a = 0; a < shares.length; a++)
                {
                        double curr_price = curr_prices[a];
                        double ret = 1 + returns[a];
                        double val = total_shares[a] * curr_price;
                        double alloc = aa[a];
                        assert(aa[a] >= 0);
                        double target = alloc * p;
                        double invest_start = prev_aa[a] * p_preinvest;
                        double invest_final = invest_start * ret;
                        double buy_sell_0 = (invest_start - val) / curr_price;
                        double price = curr_price * cpi;
                        if (buy_sell_0 >= 0)
                                buy(a, buy_sell_0, price, do_it);
                        else
                        {
                                double nominal_gain = sell(a, - buy_sell_0, price, do_it);
                                income += nominal_gain / new_cpi;
                        }
                        double dividend = dividend_tax(a, invest_start, invest_final, cpi_delta);
                        income += dividend;
                        double price_reduction;
                        if (invest_final == 0)
                                price_reduction = 1;
                        else
                                price_reduction = (invest_final - dividend) / invest_final;
                        double new_price = curr_price * ret * price_reduction;
                        double buy_sell_1 = (target - invest_final + dividend) / new_price;
                        price = new_price * new_cpi;
                        if (buy_sell_1 >= 0)
                                buy(a, buy_sell_1, price, do_it);
                        else
                        {
                                double nominal_gain = sell(a, - buy_sell_1, price, do_it);
                                income += nominal_gain / new_cpi;
                        }
                        if (do_it)
                                curr_prices[a] = new_price;
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

        public TaxHifo(Scenario scenario, boolean fifo)
        {
                super(scenario);

                this.fifo = fifo;
        }

        public String toString()
        {
                StringBuilder sb = new StringBuilder("cpi: " + cpi + "\n");
                for (int a = 0; a < scenario.normal_assets; a++)
                {
                        sb.append(scenario.asset_classes.get(a) + ": " + total_shares[a] + " @ " + curr_prices[a] + " (real)\n");
                        for (int i = 0; i < nexts[a]; i++)
                                sb.append("    " + shares[a][i] + " @ " + prices[a][i] + "\n");
                }
                sb.append("carry forward: " + cg_carry + "\n");
                return sb.toString();
        }
}
