/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2017 Gordon Irlam
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
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

import org.apache.commons.math3.distribution.LogNormalDistribution;

public class Returns implements Cloneable
{
        private Scenario scenario;
        private Config config;

        public List<double[]> data;
        public List<double[]> original_data;
        public double[][] returns_unshuffled;
        public double[] returns_unshuffled_probability;
        private double[][][][] returns_cache;

        public double[] pessimal;
        public double[] optimal;

        private Random random;
        private int ret_seed;

        private double[] shuffle_adjust;

        public double time_periods;
        public String ret_shuffle;
        public boolean reshuffle;
        public String draw;
        public int block_size;
        public boolean pair;
        public boolean short_block;

        public double[] gm;
        public double[] am;
        public double[] sd;
        private double[][] corr;
        private double[][] cholesky;

        public double[] dividend_fract;

        private List<Double> adjust_returns(List<Double> l, double adjust_arith, double ret_adjust, double vol_adjust)
        {
                double[] a = Utils.DoubleTodouble(l);
                double mean = Utils.mean(a);
                if (vol_adjust != 1)
                {
                        // Binary search on volatility adjustment.
                        double vol_a = Utils.standard_deviation(a);
                        double[] b = new double[a.length];
                        double low_init = vol_adjust / ret_adjust / 2;
                        double high_init = vol_adjust / ret_adjust * 2;
                        double low = low_init;
                        double high = high_init;
                        while (high - low > 0.001)
                        {
                                double mid = (low + high) / 2;
                                for (int i = 0; i < a.length; i++)
                                        b[i] = Math.pow(1 + a[i], mid) - 1;
                                double new_mean = Utils.mean(b);
                                double geo_adjust = ret_adjust;
                                double arith_adjust = adjust_arith + mean - new_mean;
                                for (int i = 0; i < b.length; i++)
                                        b[i] = (1 + b[i]) * geo_adjust + arith_adjust - 1;
                                double vol = Utils.standard_deviation(b);
                                if (vol < vol_adjust * vol_a)
                                        low = mid;
                                else
                                        high = mid;
                        }
                        assert(low != low_init);
                        assert(high != high_init);
                        a = b;
                }
                else
                {
                        for (int i = 0; i < a.length; i++)
                                a[i] = (1 + a[i]) * ret_adjust + adjust_arith - 1;
                }

                List<Double> res = new ArrayList<Double>();
                for (int i = 0; i < a.length; i++)
                {
                    res.add(a[i]);
                }
                return res;
        }

        public Returns(Scenario scenario, HistReturns hist, Config config, int ret_seed, boolean cache_returns, int start_year, Integer end_year, Integer num_sequences, double time_periods, Double ret_equity, Double ret_bonds, double ret_risk_free, Double ret_inflation, double management_expense, String ret_shuffle, boolean reshuffle, String draw, int bootstrap_block_size, boolean pair, boolean short_block, double all_adjust, double equity_vol_adjust)
        {
                this.scenario = scenario;
                this.config = config;

                this.ret_seed = ret_seed;
                this.time_periods = time_periods;
                this.ret_shuffle = ret_shuffle;
                this.reshuffle = reshuffle;
                this.draw = draw;
                this.block_size = (bootstrap_block_size == 0 ? 1 : (int) Math.round(bootstrap_block_size * time_periods));
                assert(time_periods >= 1 || bootstrap_block_size == 0 || Math.round(1.0 / time_periods) * this.block_size == bootstrap_block_size);
                this.pair = pair;
                this.short_block = short_block;

                random = new Random(ret_seed);

                double adjust_management_expense = Math.pow(1.0 - management_expense, 1.0 / time_periods);
                double adjust_all = Math.pow(1 + all_adjust, 1.0 / time_periods);
                double adjust_equity_vol = equity_vol_adjust;

                int start = (int) Math.round((start_year - hist.initial_year) * 12);
                int month_count = (end_year == null) ? (hist.stock.size() - start) : (int) ((end_year - start_year + 1) * 12);
                assert(month_count % Math.round(12 / time_periods) == 0);
                int count = month_count / (int) Math.round(12 / time_periods);
                assert(start + month_count <= hist.stock.size());

                double cash_mean = -1;
                List<Double> t1_returns = null;
                if (scenario.asset_classes.contains("cash") || scenario.compute_risk_premium || (scenario.equity_premium != null) || (config.ret_cash_arith != null))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.t1_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.t1.size());
                        t1_returns = hist.t1.subList(offset, offset + count);
                        cash_mean = Utils.mean(t1_returns);
                }

                List<Double> stock_returns = null;
                double stock_mean = 0;
                double stock_geomean = 1;
                if (start >= 0)
                {
                        stock_returns = reduce_returns(hist.stock.subList(start, start + month_count), (int) Math.round(12 / time_periods));
                        stock_mean = Utils.mean(stock_returns);
                        stock_geomean = Utils.plus_1_geomean(stock_returns);
                }
                else
                        System.out.println("Warning: stock/bond/cpi returns unavailable.");
                double equity_adjust_arith = 0.0;
                double equity_adjust = 1.0;
                if (scenario.equity_premium != null)
                {
                        assert(ret_equity == null);
                        double cash_arith = ((config.ret_cash_arith == null) ? cash_mean : config.ret_cash_arith);
                        equity_adjust_arith = scenario.equity_premium + cash_arith - stock_mean;
                }
                if (ret_equity != null)
                {
                        assert((scenario.equity_premium == null) && (config.ret_equity_adjust == null));
                        equity_adjust = Math.pow(1 + ret_equity, 1 / time_periods) / stock_geomean;
                }
                if (config.ret_equity_adjust != null)
                {
                        assert(ret_equity == null);
                        equity_adjust = Math.pow(1.0 + config.ret_equity_adjust, 1.0 / time_periods);
                }
                List<Double> equity_returns = null;
                if (scenario.asset_classes.contains("stocks"))
                       equity_returns = adjust_returns(stock_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);

                List<Double> bond_returns = null;
                if (start >= 0)
                        bond_returns = reduce_returns(hist.bond.subList(start, start + month_count), (int) Math.round(12 / time_periods));
                double bond_geomean = 1;
                if (start >= 0)
                        Utils.plus_1_geomean(bond_returns);
                double gs10_to_bonds_adjust_arith = config.ret_gs10_to_bonds_arith / time_periods;
                double fixed_income_adjust_arith = 0.0;
                double fixed_income_adjust = 1.0;
                if (config.ret_cash_arith != null)
                {
                        assert(ret_bonds == null);
                        fixed_income_adjust_arith = config.ret_cash_arith - cash_mean;
                }
                if (ret_bonds != null)
                {
                        assert((config.ret_cash_arith == null) && (config.ret_bonds_adjust == null));
                        fixed_income_adjust_arith -= gs10_to_bonds_adjust_arith;
                        fixed_income_adjust = Math.pow((1 + ret_bonds), 1 / time_periods) / bond_geomean;
                }
                if (config.ret_bonds_adjust != null)
                {
                        assert(ret_bonds == null);
                        fixed_income_adjust = Math.pow(1.0 + config.ret_bonds_adjust, 1.0 / time_periods);
                }
                List<Double> fixed_income_returns = null;
                if (scenario.asset_classes.contains("bonds"))
                {
                        fixed_income_returns = adjust_returns(bond_returns, fixed_income_adjust_arith + gs10_to_bonds_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, config.ret_gs10_to_bonds_vol_adjust);
                }
                if (scenario.asset_classes.contains("cash") || scenario.compute_risk_premium)
                {
                        t1_returns = adjust_returns(t1_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
                }
                List<Double> gs10_returns = null;
                if (scenario.asset_classes.contains("gs10"))
                        gs10_returns = adjust_returns(bond_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, 1);

                List<Double> eafe_returns = null;
                if (scenario.asset_classes.contains("eafe"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.eafe_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.eafe.size());
                        eafe_returns = hist.eafe.subList(offset, offset + count);
                        eafe_returns = adjust_returns(eafe_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                }

                List<Double> ff_bl_returns = null;
                List<Double> ff_bm_returns = null;
                List<Double> ff_bh_returns = null;
                List<Double> ff_sl_returns = null;
                List<Double> ff_sm_returns = null;
                List<Double> ff_sh_returns = null;
                if (scenario.asset_classes.contains("bl") || scenario.asset_classes.contains("bm") || scenario.asset_classes.contains("bh") || scenario.asset_classes.contains("sl") || scenario.asset_classes.contains("sm") || scenario.asset_classes.contains("sh"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.ff_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.ff_bl.size());
                        ff_bl_returns = hist.ff_bl.subList(offset, offset + count);
                        ff_bl_returns = adjust_returns(ff_bl_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                        ff_bm_returns = hist.ff_bm.subList(offset, offset + count);
                        ff_bm_returns = adjust_returns(ff_bm_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                        ff_bh_returns = hist.ff_bh.subList(offset, offset + count);
                        ff_bh_returns = adjust_returns(ff_bh_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                        ff_sl_returns = hist.ff_sl.subList(offset, offset + count);
                        ff_sl_returns = adjust_returns(ff_sl_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                        ff_sm_returns = hist.ff_sm.subList(offset, offset + count);
                        ff_sm_returns = adjust_returns(ff_sm_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                        ff_sh_returns = hist.ff_sh.subList(offset, offset + count);
                        double adjust_sh = Math.pow(1 + config.ret_sh_adjust, 1.0 / time_periods);
                        ff_sh_returns = adjust_returns(ff_sh_returns, equity_adjust_arith, equity_adjust * adjust_sh * adjust_management_expense * adjust_all, adjust_equity_vol);
                }

                List<Double> nasdaq_returns = null;
                if (scenario.asset_classes.contains("nasdaq"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.nasdaq_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.nasdaq.size());
                        nasdaq_returns = hist.nasdaq.subList(offset, offset + count);
                        nasdaq_returns = adjust_returns(nasdaq_returns, equity_adjust_arith + config.ret_nasdaq_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                }

                List<Double> reits_equity_returns = null;
                if (scenario.asset_classes.contains("equity_reits"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.reit_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.reits_equity.size());
                        reits_equity_returns = hist.reits_equity.subList(offset, offset + count);
                        reits_equity_returns = adjust_returns(reits_equity_returns, equity_adjust_arith, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                }

                List<Double> reits_mortgage_returns = null;
                if (scenario.asset_classes.contains("mortgage_reits"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.reit_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.reits_mortgage.size());
                        reits_mortgage_returns = hist.reits_mortgage.subList(offset, offset + count);
                        reits_mortgage_returns = adjust_returns(reits_mortgage_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
                }

                List<Double> gs1_returns = null;
                if (scenario.asset_classes.contains("gs1"))
                {
                        int offset = (int) Math.round((start_year - hist.gs1_initial) * 12);
                        assert(offset >= 0);
                        assert(offset + month_count <= hist.gs1.size());
                        gs1_returns = reduce_returns(hist.gs1.subList(offset, offset + month_count), (int) Math.round(12 / time_periods));
                        gs1_returns = adjust_returns(gs1_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
                }

                List<Double> tips10_returns = null;
                if (scenario.asset_classes.contains("tips"))
                {
                        int offset = (int) Math.round((start_year - hist.tips10_initial) * 12);
                        assert(offset >= 0);
                        assert(offset + month_count <= hist.tips10.size());
                        tips10_returns = reduce_returns(hist.tips10.subList(offset, offset + month_count), (int) Math.round(12 / time_periods));
                        double adjust_tips = Math.pow(1 + config.ret_tips_adjust, 1.0 / time_periods);
                        tips10_returns = adjust_returns(tips10_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_tips * adjust_management_expense * adjust_all, config.ret_tips_vol_adjust);
                }

                List<Double> aaa_returns = null;
                if (scenario.asset_classes.contains("aaa"))
                {
                        int offset = (int) Math.round((start_year - hist.aaa_initial) * 12);
                        assert(offset >= 0);
                        assert(offset + month_count <= hist.aaa.size());
                        aaa_returns = reduce_returns(hist.aaa.subList(offset, offset + month_count), (int) Math.round(12 / time_periods));
                        aaa_returns = adjust_returns(aaa_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
                }

                List<Double> baa_returns = null;
                if (scenario.asset_classes.contains("baa"))
                {
                        int offset = (int) Math.round((start_year - hist.baa_initial) * 12);
                        assert(offset >= 0);
                        assert(offset + month_count <= hist.baa.size());
                        baa_returns = reduce_returns(hist.baa.subList(offset, offset + month_count), (int) Math.round(12 / time_periods));
                        baa_returns = adjust_returns(baa_returns, fixed_income_adjust_arith, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
                }

                List<Double> gold_returns = null;
                if (scenario.asset_classes.contains("gold"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.gold_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.gold.size());
                        gold_returns = hist.gold.subList(offset, offset + count);
                        gold_returns = adjust_returns(gold_returns, 0, adjust_management_expense * adjust_all, 1);
                }

                List<Double> margin_returns = null;
                if (scenario.asset_classes.contains("margin"))
                {
                        assert(time_periods == 1);
                        int offset = (int) Math.round((start_year - hist.t1_initial) * time_periods);
                        assert(offset >= 0);
                        assert(offset + count <= hist.t1.size());
                        List<Double> margin = new ArrayList<Double>();
                        for (double ret : hist.t1)
                                margin.add(ret + config.margin_premium);
                        margin_returns = margin.subList(offset, offset + count);
                        margin_returns = adjust_returns(margin_returns, 0, adjust_all, 1);
                }

                List<Double> risk_free_returns = new ArrayList<Double>();
                double risk_free_return = (Math.pow(1.0 + ret_risk_free, 1.0 / time_periods) - 1.0);
                double perturb = 1e-5;  // Prevent MVO dying on risk free asset class.
                for (int i = 0; i < count; i++)
                {
                        risk_free_returns.add(risk_free_return + perturb);
                        perturb = - perturb;
                }
                risk_free_returns = adjust_returns(risk_free_returns, 0, adjust_management_expense * adjust_all, 1);

                List<Double> risk_free2_returns = new ArrayList<Double>();
                double risk_free2_return = (Math.pow(1.0 + config.ret_risk_free2, 1.0 / time_periods) - 1.0);
                for (int i = 0; i < count; i++)
                {
                        risk_free2_returns.add(risk_free2_return);
                }
                risk_free2_returns = adjust_returns(risk_free2_returns, 0, adjust_management_expense * adjust_all, 1);

                List<Double> synthetic_returns = new ArrayList<Double>();
                synthetic_returns = log_normal_ppf(count, config.synthetic_ret, config.synthetic_vol);

                List<Double> lm_bonds_returns = new ArrayList<Double>();
                for (int i = 0; i < count; i++)
                {
                        lm_bonds_returns.add(Double.NaN);
                }

                List<Double> cpi_returns = null;
                if (start >= 0)
                {
                        cpi_returns = new ArrayList<Double>();
                        for (int year = start_year; year <= ((end_year == null) ? hist.initial_year + count - 1 : end_year); year++)
                        {
                                int i = (year - hist.initial_year) * 12 + 12;
                                double cpi_d = hist.cpi_index.get(i) / hist.cpi_index.get(i - 12);
                                cpi_returns.add(cpi_d - 1.0);
                        }
                        double cpi_geomean = Utils.plus_1_geomean(cpi_returns);
                        double cpi_adjust = (ret_inflation == null) ? 1 : (Math.pow(1.0 + ret_inflation, 1.0 / time_periods) / cpi_geomean);
                        cpi_returns = adjust_returns(cpi_returns, 0, cpi_adjust, 1);
                }

                List<double[]> returns = new ArrayList<double[]>();
                dividend_fract = new double[scenario.asset_classes.size()];
                for (int a = 0; a < dividend_fract.length; a++)
                {
                        String asset_class = scenario.asset_classes.get(a);

                        List<Double> rets = null;
                        double divf = Double.NaN;

                        if ("stocks".equals(asset_class))
                        {
                                rets = equity_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("bonds".equals(asset_class))
                        {
                                rets = fixed_income_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("gs10".equals(asset_class))
                        {
                                rets = gs10_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("eafe".equals(asset_class))
                        {
                                rets = eafe_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("bl".equals(asset_class))
                        {
                                rets = ff_bl_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("bm".equals(asset_class))
                        {
                                rets = ff_bm_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("bh".equals(asset_class))
                        {
                                rets = ff_bh_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("sl".equals(asset_class))
                        {
                                rets = ff_sl_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("sm".equals(asset_class))
                        {
                                rets = ff_sm_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("sh".equals(asset_class))
                        {
                                rets = ff_sh_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("nasdaq".equals(asset_class))
                        {
                                rets = nasdaq_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("equity_reits".equals(asset_class))
                        {
                                rets = reits_equity_returns;
                                divf = config.dividend_fract_equity;
                        }
                        else if ("mortgage_reits".equals(asset_class))
                        {
                                rets = reits_mortgage_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("gs1".equals(asset_class))
                        {
                                rets = gs1_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("tips".equals(asset_class))
                        {
                                rets = tips10_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("aaa".equals(asset_class))
                        {
                                rets = aaa_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("baa".equals(asset_class))
                        {
                                rets = baa_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("cash".equals(asset_class))
                        {
                                rets = t1_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("margin".equals(asset_class))
                        {
                                rets = margin_returns;
                                divf = 0.0;
                        }
                        else if ("risk_free".equals(asset_class))
                        {
                                rets = risk_free_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("risk_free2".equals(asset_class))
                        {
                                rets = risk_free2_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("synthetic".equals(asset_class))
                        {
                                rets = synthetic_returns;
                                divf = 0;
                        }
                        else if ("lm_bonds".equals(asset_class))
                        {
                                rets = lm_bonds_returns;
                                divf = config.dividend_fract_fixed_income;
                        }
                        else if ("gold".equals(asset_class))
                        {
                                rets = gold_returns;
                                divf = 0.0;
                        }
                        else if ("[cpi]".equals(asset_class))
                        {
                                rets = cpi_returns;
                        }
                        else if (Arrays.asList("[consume]", "[ria]", "[nia]", "[ef_index]").contains(asset_class))
                        {
                                continue;
                        }

                        double[] r = Utils.DoubleTodouble(rets);
                        if (scenario.compute_risk_premium)
                        {
                                for (int i = 0; i < r.length; i++)
                                        r[i] -= t1_returns.get(i);
                        }
                        else if (!config.inflation_adjust_returns)
                        {
                                for (int i = 0; i < r.length; i++)
                                    r[i] = (1 + r[i]) * (1 + cpi_returns.get(i)) - 1;
                        }
                        returns.add(r);
                        dividend_fract[a] = divf;
                }

                double[][] array_returns = new double[returns.size()][];
                gm = new double[returns.size()];
                am = new double[returns.size()];
                sd = new double[returns.size()];
                for (int a = 0; a < returns.size(); a++)
                {
                        double[] rets = returns.get(a);
                        array_returns[a] = rets;
                        gm[a] = Utils.plus_1_geomean(rets);
                        am[a] = Utils.mean(rets);
                        sd[a] = Utils.standard_deviation(rets);
                }
                if (!ret_shuffle.equals("none"))
                {
                        corr = Utils.correlation_returns(array_returns);
                        cholesky = Utils.cholesky_decompose(corr);
                }

                returns = Utils.zipDoubleArray(returns);
                this.original_data = returns;

                if (num_sequences == null)
                        num_sequences = 1;

                this.data = returns;
                if (config.map_headroom != null)
                        compute_pessimal_returns(returns);
                shuffle_adjust = new double[scenario.normal_assets];
                for (int a = 0; a < shuffle_adjust.length; a++)
                        shuffle_adjust[a] = 1;
                if (!ret_shuffle.equals("none") && !draw.equals("bootstrap") && !draw.equals("shuffle") && !draw.equals("log_normal_ppf") && config.ret_geomean_keep)
                {
                        // Calculate scaling necessary to preserve geometric mean; it might get messed up by the draw.
                        // The draw concerns itself with preserving the arithmetic mean (which matters less), the standard deviation, and the correlations.
                        double[][] geomean_samples = new double[scenario.normal_assets][config.ret_geomean_keep_count];
                        for (int i = 0; i < config.ret_geomean_keep_count; i++)
                        {
                                List<double[]> sample = Utils.zipDoubleArray(Arrays.asList(shuffle_returns(returns.size())));
                                for (int a = 0; a < shuffle_adjust.length; a++)
                                        geomean_samples[a][i] = Utils.plus_1_geomean(sample.get(a)) - 1;
                        }
                        for (int a = 0; a < scenario.normal_assets; a++)
                        {
                                shuffle_adjust[a] = gm[a] / Utils.plus_1_geomean(geomean_samples[a]);
                        }
                }
                if (ret_shuffle.equals("once"))
                {
                        List<double[]> new_data = new ArrayList<double[]>();
                        for (int i = 0; i < num_sequences; i++)
                                new_data.addAll(Arrays.asList(shuffle_returns(this.data.size())));
                        this.data = new_data;
                }
                else if (cache_returns && ret_shuffle.equals("all") && !reshuffle)
                {
                        // Do this here. Don't fill cache when accessed or random number generator will get out of sync.
                        returns_cache = new double[config.returns_cache_size][config.path_metrics_bucket_size][][];
                        int total_periods = (int) Math.round(scenario.ss.max_years * time_periods);
                        for (int bucket = 0; bucket < config.returns_cache_size; bucket++)
                                for (int s = 0; s < config.path_metrics_bucket_size; s++)
                                        returns_cache[bucket][s] = shuffle_returns(total_periods);
                }
                random = null;

                this.returns_unshuffled = this.data.toArray(new double[0][]);

                this.returns_unshuffled_probability = new double[returns_unshuffled.length];
                for (int i = 0; i < returns_unshuffled_probability.length; i++)
                        returns_unshuffled_probability[i] = (short_block ? 1 : Math.min(Math.min(block_size, i + 1), returns_unshuffled.length - i));
                double sum = Utils.sum(returns_unshuffled_probability);
                for (int i = 0; i < returns_unshuffled_probability.length; i++)
                        returns_unshuffled_probability[i] /= sum;
        }

        public Returns clone()
        {
                assert(random == null);

                Returns returns = null;
                try
                {
                        returns = (Returns) super.clone();
                }
                catch (CloneNotSupportedException e)
                {
                        assert(false);
                }

                returns.random = new Random(ret_seed);

                return returns;
        }

        public void setSeed(long i)
        {
                random.setSeed(i);
        }

        private List<Double> log_normal_ppf(int len, double am, double sd)
        {
                am += 1;
                double gm = am / Math.sqrt(1 + Math.pow(sd / am, 2));
                double mu = Math.log(gm);
                double sigma = Math.sqrt(Math.log(1 + Math.pow(sd / am, 2)));
                gm = Math.pow(gm, 1 / this.time_periods);
                mu /= this.time_periods;
                sigma /= Math.sqrt(this.time_periods);
                LogNormalDistribution distrib = null;
                if (sigma != 0)
                        distrib = new LogNormalDistribution(mu, sigma);
                List<Double> rets = new ArrayList<Double>();
                for (int i = 0; i < len; i++)
                {
                        if (sigma == 0)
                                rets.add(gm - 1);
                        else
                                rets.add(distrib.inverseCumulativeProbability((i + 0.5) / len) - 1);
                }

                Collections.shuffle(rets, random);
                return rets;
        }

        private void compute_pessimal_returns(List<double[]> data)
        {
                List<double[]> returns = Utils.zipDoubleArray(data);

                pessimal = new double[returns.size()];
                optimal = new double[returns.size()];
                for (int i = 0; i < returns.size(); i++)
                {
                        if (!scenario.asset_classes.get(i).equals("lm_bonds"))
                        {
                                double[] rets = returns.get(i);
                                double am = Utils.mean(rets);
                                double sd = Utils.standard_deviation(rets);
                                am += 1;
                                double gm = am / Math.sqrt(1 + Math.pow(sd / am, 2));
                                double mu = Math.log(gm);
                                double sigma = Math.sqrt(Math.log(1 + Math.pow(sd / am, 2)));
                                if (sigma == 0)
                                {
                                        pessimal[i] = gm - 1;
                                        optimal[i] = gm - 1;
                                }
                                else
                                {
                                        LogNormalDistribution distrib = new LogNormalDistribution(mu, sigma);
                                        pessimal[i] = distrib.inverseCumulativeProbability(config.map_headroom) - 1;
                                        optimal[i] = distrib.inverseCumulativeProbability(1 - config.map_headroom) - 1;
                                        assert(pessimal[i] != -1); // Insufficient fp precisiion.
                                }
                        }
                }
        }

        private int shuffle_count = 0;
        private double[] sample_mean;
        private double[] sample_std_dev;
        private double[][] sample_chol;

        public double[][] shuffle_returns(int length)
        {
                List<double[]> returns = this.data;

                int len_returns = returns.size();

                double new_returns[][] = null;
                if (draw.equals("bootstrap"))
                {
                        new_returns = new double[length][];

                        int len_available;
                        int bs1;
                        if (short_block)
                        {
                                len_available = len_returns;
                                bs1 = block_size - 1;
                        }
                        else
                        {
                                len_available = len_returns - block_size + 1;
                                bs1 = 0;
                        }

                        if (pair)
                        {
                                int offset = short_block ? random.nextInt(block_size) : 0;
                                int index = random.nextInt(len_available);
                                for (int y = 0; y < length; y++)
                                {
                                        if ((y + offset) % block_size == 0 || index == len_returns)
                                        {
                                                index = random.nextInt(len_available + bs1) - bs1;
                                                if (index < 0)
                                                {
                                                        offset = - index - y;
                                                        index = 0;
                                                }
                                                else
                                                        offset = - y;
                                        }
                                        new_returns[y] = returns.get(index);
                                        index++;
                                }
                        }
                        else
                        {
                                int ret0Len = scenario.asset_classes.size();
                                int ret0NoEfIndex = scenario.normal_assets; // Prevent randomness change due to presence of ef index.
                                int offset[] = new int[ret0NoEfIndex];
                                int index[] = new int[ret0NoEfIndex];
                                for (int i = 0; i < ret0NoEfIndex; i++)
                                {
                                        offset[i] = short_block ? random.nextInt(block_size) : 0;
                                        index[i] = random.nextInt(len_available);
                                }
                                for (int y = 0; y < length; y++)
                                {
                                        for (int i = 0; i < ret0NoEfIndex; i++)
                                        {
                                                if ((y + offset[i]) % block_size == 0 || index[i] == len_returns)
                                                {
                                                        index[i] = random.nextInt(len_available + bs1) - bs1;
                                                        if (index[i] < 0)
                                                        {
                                                                offset[i] = - index[i] - y;
                                                                index[i] = 0;
                                                        }
                                                        else
                                                                offset[i] = - y;
                                                }
                                        }
                                        double[] new_return = new double[ret0Len];
                                        for (int i = 0; i < ret0NoEfIndex; i++)
                                        {
                                                new_return[i] = returns.get(index[i])[i];
                                        }
                                        new_returns[y] = new_return;
                                        for (int i = 0; i < ret0NoEfIndex; i++)
                                        {
                                                index[i] = (i + 1) % len_returns;
                                        }
                                }
                        }
                }
                else if (draw.equals("shuffle"))
                {
                        assert(length <= len_returns);

                        new_returns = new double[length][];

                        if (pair)
                        {
                                List<double[]> shuffle_returns = new ArrayList<double[]>();
                                shuffle_returns.addAll(returns);
                                Collections.shuffle(shuffle_returns, random);
                                shuffle_returns = shuffle_returns.subList(0, length);
                                new_returns = shuffle_returns.toArray(new double[length][]);
                        }
                        else
                        {
                                @SuppressWarnings("unchecked")
                                List<double[]> asset_class_returns = Utils.zipDoubleArray(returns);
                                List<double[]> new_asset_class_returns = new ArrayList<double[]>();
                                for (double[] asset_class_return : asset_class_returns)
                                {
                                        List<Double> new_asset_class_return = new ArrayList<Double>();
                                        for (double ret : asset_class_return)
                                                new_asset_class_return.add(ret);
                                        Collections.shuffle(new_asset_class_return, random);
                                        double[] shuffle_asset_class_return = Utils.DoubleTodouble(new_asset_class_return);
                                        new_asset_class_returns.add(shuffle_asset_class_return);
                                }
                                List<double[]> shuffle_returns = Utils.zipDoubleArray(new_asset_class_returns);
                                new_returns = shuffle_returns.toArray(new double[length][]);
                        }
                }
                else if (draw.equals("normal") || draw.equals("log_normal") || draw.equals("skew_normal"))
                {
                        if (config.ret_resample == null)
                                new_returns = draw_returns(am, sd, cholesky, length);
                        else
                        {
                                if (shuffle_count % config.ret_resample == 0)
                                {
                                        double[][] sample = draw_returns(am, sd, cholesky, len_returns);
                                        sample_mean = new double[scenario.stochastic_classes];
                                        sample_std_dev = new double[scenario.stochastic_classes];
                                        for (int a = 0; a < scenario.stochastic_classes; a++)
                                        {
                                                double sum = 0;
                                                double sum_squares = 0;
                                                for (int y = 0; y < sample.length; y++)
                                                {
                                                        sum += sample[y][a];
                                                        sum_squares += sample[y][a] * sample[y][a];
                                                }
                                                sample_mean[a] = sum / sample.length;
                                                sample_std_dev[a] = Math.sqrt(sum_squares / sample.length - sample_mean[a] * sample_mean[a]);
                                        }
                                        if (config.skip_sample_cholesky)
                                                sample_chol = cholesky; // Major performance savings, little metrics impact (around 0.05% change in metrics).
                                        else
                                        {
                                                double[][] zip_sample = Utils.zipDoubleArrayArray(sample);
                                                double[][] sample_corr = Utils.correlation_returns(zip_sample);
                                                sample_chol = Utils.cholesky_decompose(sample_corr);
                                        }
                                }
                                new_returns = draw_returns(sample_mean, sample_std_dev, sample_chol, length);
                        }

                        for (int y = 0; y < new_returns.length; y++)
                                for (int a = 0; a < scenario.normal_assets; a++)
                                        new_returns[y][a] = (1 + new_returns[y][a]) * shuffle_adjust[a] - 1;
                }
                else if (draw.equals("log_normal_ppf"))
                {
                        // Could drastically cut down number of samples required if could use weights, but don't know how to combine weights with multiple asset classes.
                        List<double[]> asset_class_returns = Utils.zipDoubleArray(returns);
                        for (int asset_class = 0; asset_class < asset_class_returns.size(); asset_class++)
                        {
                                double[] rets = asset_class_returns.get(asset_class);
                                double am = Utils.mean(rets);
                                double sd = Utils.standard_deviation(rets);
                                List<Double> lognormal_rets = log_normal_ppf(rets.length, am, sd);
                                asset_class_returns.set(asset_class, Utils.DoubleTodouble(lognormal_rets));
                        }
                        List<double[]> log_normal_returns = Utils.zipDoubleArray(asset_class_returns);
                        new_returns = log_normal_returns.toArray(new double[log_normal_returns.size()][]);
                }
                else
                        assert(false);

                shuffle_count++;

                return new_returns;
        }

        private double[][] draw_returns(double[] mean, double[] std_dev, double[][] chol, int length)
        {
                int aa_len = scenario.stochastic_classes;
                int aa_valid = scenario.stochastic_classes; // Prevent randomness change due to presence of ef index.

                double[][] new_returns = new double[length][];

                double[] log_normal_mean = new double[aa_valid];
                double[] log_normal_std_dev = new double[aa_valid];
                for (int a = 0; a < aa_valid; a++)
                {
                        log_normal_mean[a] = Math.exp(mean[a] + std_dev[a] * std_dev[a] / 2);
                        log_normal_std_dev[a] = Math.sqrt(Math.exp(std_dev[a] * std_dev[a]) - 1) * log_normal_mean[a];
                }

                boolean log_normal = draw.equals("log_normal");
                boolean skew_normal = draw.equals("skew_normal");

                if (pair)
                {
                        // Generation of correlated non-autocorrelated returns using Cholesky decomposition.
                        // Cholesky produces returns that are normally distributed.
                        double[] aa = new double[aa_len];
                        for (int y = 0; y < length; y++)
                        {
                                for (int a = 0; a < aa_valid; a++)
                                        aa[a] = random.nextGaussian();
                                double[] result = Utils.matrix_vector_product(chol, aa);
                                for (int a = 0; a < aa_valid; a++)
                                {
                                        result[a] = mean[a] + std_dev[a] * result[a];
                                        if (log_normal) {
                                                if (std_dev[a] > 0)
                                                        result[a] = mean[a] + (Math.exp(result[a]) - log_normal_mean[a]) / log_normal_std_dev[a] * std_dev[a];
                                                else
                                                        result[a] = mean[a];
                                        }
                                        else if (skew_normal)
                                                if (new_returns[y][a] < 0)
                                                        result[a] = 1 / (1 - result[a]) - 1;
                                }
                                new_returns[y] = result;
                        }
                }
                else
                {
                        // Generation of non-correlated returns using normal distribution.
                        for (int y = 0; y < length; y++)
                        {
                                double[] aa = new double[aa_len];
                                for (int a = 0; a < aa_valid; a++)
                                {
                                        aa[a] = mean[a] + std_dev[a] * random.nextGaussian();
                                        if (log_normal)
                                                aa[a] = mean[a] + (Math.exp(aa[a]) - log_normal_mean[a]) / log_normal_std_dev[a] * std_dev[a];
                                        else if (skew_normal)
                                                if (aa[a] < 0)
                                                        aa[a] = 1 / (1 - aa[a]) - 1;
                                }
                                new_returns[y] = aa;
                        }
                }

                return new_returns;
        }

        public double[][] shuffle_returns_cached(int bucket, int s, int length)
        {
            double[][] returns_array;
            if (returns_cache != null && bucket < returns_cache.length)
                    returns_array = returns_cache[bucket][s];
            else
                    returns_array = shuffle_returns(length);

            assert(returns_array.length >= length);

            return returns_array;
        }

        private List<Double> reduce_returns(List<Double> l, int size)
        {
                List<Double> r = new ArrayList<Double>();
                int i = 0;
                while (i < l.size())
                {
                        Double ret = 1.0;
                        for (int j = 0; j < size; j++)
                        {
                                ret *= 1.0 + l.get(i);
                                i++;
                        }
                        r.add(ret - 1.0);
                }
                return r;
        }
}
