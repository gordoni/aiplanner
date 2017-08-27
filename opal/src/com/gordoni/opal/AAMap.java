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

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.Random;

class AAMap
{
        protected Scenario scenario;
        protected Config config;

        protected AAMap aamap1;
        protected AAMap aamap2;

        private VitalStats generate_stats;
        private VitalStats validate_stats;

        public Utility uc_time;
        public Utility uc_risk;

        protected double guaranteed_income;

        public MapPeriod[] map;

        // We interpolate metrics when generating.
        // Prior to doing this we ran into artifacts.
        // For instance if we withdraw 100,000 per year, and have a bucket pf appear at 100,015 then the submetrics for
        // that bucket are associated with 15.  Unfortunately 15 is much smaller than the zero bucket size, and so all
        // asset allocations/contributions look the same.  This would cause always donate to get set on low p sizes.
        // Fixing this has allowed us to increase the zero bucket size by a factor of 50.

        public MapElement lookup_interpolate(double[] p, int period)
        {
                double[] aa = new double[scenario.all_alloc];
                Metrics metrics = new Metrics();
                SimulateResult results = new SimulateResult(metrics, Double.NaN, Double.NaN, Double.NaN, null, null);
                MapElement li_me = new MapElement(null, aa, results, null, null);

                return map[period].lookup_interpolate(p, false, false, li_me);
        }

        private void aa_offset(double[] aa)
        {
                if (config.aa_offset == null)
                        return;

                double new_sum = 0;
                for (int a = 0; a < scenario.normal_assets; a++)
                {
                        double alloc = aa[a];
                        alloc += config.aa_offset[a];
                        alloc = Math.max(alloc, config.min_aa);
                        alloc = Math.min(alloc, config.max_aa);
                        aa[a] = alloc;
                        new_sum += alloc;
                }
                assert(new_sum > 1e-6);
                for (int a = 0; a < scenario.normal_assets; a++)
                        aa[a] /= new_sum;
        }

        // Simulation core.
        @SuppressWarnings("unchecked")
        protected SimulateResult simulate(double[] initial_aa, double[] bucket_p, int period, Integer num_sequences, int num_paths_record, boolean generate, boolean pessimal, Returns returns, int bucket)
        {
                final int book_post = (config.book_post ? 1 : 0);
                final boolean cost_basis_method_immediate = config.cost_basis_method.equals("immediate");
                final boolean variable_withdrawals = !scenario.vw_strategy.equals("amount") && !scenario.vw_strategy.equals("retirement_amount");
                final VitalStats original_vital_stats = generate ? generate_stats : validate_stats;
                final AnnuityStats annuity_stats = generate ? scenario.ss.generate_annuity_stats : scenario.ss.validate_annuity_stats;
                final boolean monte_carlo_validate = config.sex2 != null && !config.couple_unit;
                final int total_periods = (int) (scenario.ss.max_years * returns.time_periods);
                final int max_periods = total_periods - period;

                int step_periods;
                if (generate)
                        step_periods = 1;
                else
                        step_periods = max_periods;

                int return_periods;
                if (generate)
                        return_periods = total_periods;
                else
                        return_periods = step_periods;

                int len_available;
                if (pessimal)
                        len_available = 1;
                else if (returns.short_block)
                        len_available = returns.data.size();
                else
                        len_available = returns.data.size() - step_periods + 1;

                int num_paths;
                if (num_sequences != null && !generate)
                        num_paths = num_sequences;
                else
                        num_paths = len_available;
                assert (num_paths >= 0);

                if (Arrays.asList("none", "once").contains(returns.ret_shuffle))
                        assert(num_paths <= len_available);

                boolean[] special_aa = new boolean[scenario.normal_assets];
                boolean has_special = false;
                for (int i = 0; i < scenario.normal_assets; i++)
                {
                        special_aa[i] = scenario.asset_classes.get(i).equals("lm_bonds");
                        if (special_aa[i])
                                has_special = true;
                }

                double[] start_aa;
                if (initial_aa == null)
                {
                        MapElement res = lookup_interpolate(bucket_p, period);
                        start_aa = res.aa;
                }
                else
                {
                        start_aa = initial_aa.clone();
                }
                if (!generate)
                        aa_offset(start_aa);

                double[] aa1 = new double[scenario.all_alloc]; // Avoid object creation in main loop; slow.
                double[] aa2 = new double[scenario.all_alloc];

                double[] li_p = new double[scenario.start_p.length];
                double[] li_p1 = new double[scenario.start_p.length];
                double[] li_p2 = new double[scenario.start_p.length];
                double[] li_aa = new double[scenario.all_alloc];
                Metrics li_metrics = new Metrics();
                SimulateResult li_results = new SimulateResult(li_metrics, Double.NaN, Double.NaN, Double.NaN, null, null);
                SimulateResult li_results1 = new SimulateResult(null, Double.NaN, Double.NaN, Double.NaN, null, null);
                SimulateResult li_results2 = new SimulateResult(null, Double.NaN, Double.NaN, Double.NaN, null, null);
                MapElement li_me = new MapElement(null, li_aa, li_results, null, null);
                MapElement li_me1 = new MapElement(null, null, li_results1, null, null);
                MapElement li_me2 = new MapElement(null, null, li_results2, null, null);

                int len_returns = 0;
                double operating_expense_step = Math.pow(1 - config.operating_expense, 1.0 / returns.time_periods);
                double rcr_step = Math.pow(config.accumulation_ramp, 1.0 / returns.time_periods);
                double initial_rcr = config.accumulation_rate * Math.pow(rcr_step, period);
                double tw_goal = 0.0;
                double ntw_goal = 0.0;
                double floor_goal = 0.0;
                double upside_goal = 0.0;
                double consume_goal = 0.0;
                double combined_goal = 0.0;
                double inherit_goal = 0.0;
                double tax_goal = 0.0;
                double wer = 0.0; // Blanchett Withdrawal Efficiency Rate, not time discounted.
                double cost = 0.0;
                double consume_alive_discount = Double.NaN;
                Metrics metrics = new Metrics();
                List<List<PathElement>> paths = null;
                if (!generate)
                        paths = new ArrayList<List<PathElement>>();
                double[][] returns_array = null;
                double[] rets = new double[scenario.stochastic_classes];
                double[] tax_annuity_credit_expire = new double[total_periods]; // Nominal amount.
                Tax tax = null;
                if (generate && !config.cost_basis_method.equals("immediate"))
                        tax = new TaxImmediate(scenario, config.tax_immediate_adjust);
                else
                        tax = Tax.taxFactory(scenario, config.cost_basis_method);
                double spend_annual = Double.NaN; // Amount spent on consumption and purchasing annuities.
                double consume_annual = Double.NaN;
                double first_payout = Double.NaN;
                double consume_annual_key = Double.NaN;  // Cache provides 25% speedup for generate.
                double uct_u_ujp = uc_time.utility(config.utility_join_required);
                double floor_utility = Double.NaN;
                double upside_utility = Double.NaN;
                //double consume_utility = 0.0;
                double divisor_saa = 0;
                double divisor_bsaa = 0;
                double divisor_bsaua = 0;
                double divisor_ra = 0;
                double divisor_a = 0;

                Random random = null;
                if (!generate && monte_carlo_validate)
                {
                        random = new Random(config.vital_stats_seed);
                        random = new Random(random.nextInt() + bucket);
                }

                double first_payout_fract = 1 / returns.time_periods - config.annuity_payout_delay / 12;
                assert(first_payout_fract >= 0 || (scenario.ria_index == null && scenario.nia_index == null));

                for (int s = 0; s < num_paths; s++)
                {
                        double p = (scenario.tp_index == null ? 0 : bucket_p[scenario.tp_index]);
                        double ria = (scenario.ria_index == null ? 0 : bucket_p[scenario.ria_index]); // Payout is after tax amount.
                        double nia = (scenario.nia_index == null ? 0 : bucket_p[scenario.nia_index]);
                        double hci = (scenario.hci_index == null ? 0 : bucket_p[scenario.hci_index]);
                        double[] aa = aa1;
                        double[] free_aa = aa2;
                        System.arraycopy(start_aa, 0, aa, 0, scenario.all_alloc);
                        boolean retire = false;
                        double spend_retirement = Double.NaN;
                        double cpi = 1;
                        if (scenario.do_tax)
                        {
                                if (config.tax_rate_annuity != 0)
                                        Arrays.fill(tax_annuity_credit_expire, 0);
                                tax.initial(p, aa);
                        }
                        double ssr_terms = 0;
                        double all_return = 1;
                        double returns_probability = 0.0;
                        boolean feasible = true;
                        double p_post_inc_neg = p;
                        double solvent_always = 1;
                        double tw_goal_path = 0.0;
                        double ntw_goal_path = 0.0;
                        double floor_goal_path = 0.0;
                        double upside_goal_path = 0.0;
                        double consume_goal_path = 0.0;
                        double combined_goal_path = 0.0;
                        double inherit_goal_path = 0.0;
                        double tax_goal_path = 0.0;
                        double wer_path = 0.0;
                        double cost_path = 0.0;
                        List<PathElement> path = null;
                        if (s < num_paths_record)
                                path = new ArrayList<PathElement>();
                        int index;
                        if (!generate && returns.ret_shuffle.equals("all"))
                        {
                                if (returns.reshuffle)
                                        returns_array = returns.shuffle_returns(return_periods);
                                else
                                        returns_array = returns.shuffle_returns_cached(bucket, s, return_periods);
                                len_returns = return_periods;
                                index = 0;
                                returns_probability = 1.0 / num_paths;
                        }
                        else
                        {
                                returns_array = returns.returns_unshuffled;
                                len_returns = returns_array.length;
                                index = s % len_returns;
                                returns_probability = returns.returns_unshuffled_probability[index];
                        }
                        AAMap aamap = this;
                        VitalStats couple_vital_stats;
                        if (!generate && monte_carlo_validate)
                                couple_vital_stats = original_vital_stats.joint_generate(random);
                        else
                                couple_vital_stats = original_vital_stats;
                        VitalStats vital_stats = couple_vital_stats;
                        int fperiod = -1;
                        MapElement me = null;
                        double rcr = initial_rcr / returns.time_periods;
                        double raw_alive = Double.NaN;
                        int y = 0;
                        while (y < step_periods)
                        {
                                double utility_weight = 1;
                                if (!generate && monte_carlo_validate)
                                {
                                        boolean dead1 = couple_vital_stats.vital_stats1.alive[period + y] == 0;
                                        boolean dead2 = couple_vital_stats.vital_stats2.alive[period + y] == 0;
                                        if (dead1 || dead2)
                                        {
                                                aamap = dead1 ? aamap2 : aamap1;
                                                vital_stats = dead1 ? couple_vital_stats.vital_stats2 : couple_vital_stats.vital_stats1;
                                                utility_weight = dead1 ? (dead2 ? 0 : 1 - config.couple_weight1) : config.couple_weight1;
                                                consume_annual_key = Double.NaN;
                                        }

                                        uct_u_ujp = aamap.uc_time.utility(config.utility_join_required);
                                }
                                double current_guaranteed_income = aamap.guaranteed_income;

                                double raw_dying = vital_stats.raw_dying[period + y];
                                raw_alive = vital_stats.raw_alive[period + y + 1];
                                double prev_alive = vital_stats.alive[period + y];
                                double alive = vital_stats.alive[period + y + 1];
                                double dying = vital_stats.dying[period + y];

                                double amount;
                                double retire_in_periods = (config.retirement_age - config.start_age) * returns.time_periods - (period + y);
                                boolean retired = (retire_in_periods <= 0);
                                boolean retire_next = (0 < retire_in_periods) && (retire_in_periods <= 1);
                                boolean hci1 = (config.hci_income2_age - config.start_age) * returns.time_periods > (period + y);
                                boolean compute_utility = !config.utility_retire || retired;

                                double p_prev_inc_neg = p;
                                double p_prev_exc_neg = p;
                                if (p_prev_exc_neg < 0)
                                        p_prev_exc_neg = 0;
                                double ria_prev = ria;
                                double nia_prev = nia;
                                double hci_prev = hci;

                                double income = ria + nia;
                                if (period + y < config.cw_schedule.length)
                                        income += config.cw_schedule[period + y];
                                if (retired)
                                {
                                        income += current_guaranteed_income / returns.time_periods;
                                }
                                else
                                {
                                        income += rcr;
                                        rcr *= rcr_step;
                                }
                                income += hci;

                                spend_annual = p + income;
                                if (retired && !retire)
                                {
                                        spend_retirement = scenario.vw_strategy.equals("amount") ? config.withdrawal : income + scenario.vw_percent * p_prev_exc_neg;
                                        retire = true;
                                }
                                if (retired || config.spend_pre_retirement)
                                {
                                        if (variable_withdrawals)
                                                // Full investment portfolio amount subject to variable spending choice.
                                                consume_annual = spend_annual;
                                        else if (config.spend_pre_retirement && !retired)
                                                consume_annual = config.withdrawal;
                                        else
                                                consume_annual = spend_retirement;
                                        amount = income - consume_annual;
                                }
                                else
                                {
                                        consume_annual = config.floor;
                                        amount = income;
                                        rcr *= rcr_step;
                                }
                                spend_annual *= returns.time_periods;
                                consume_annual *= returns.time_periods;

                                first_payout = 0;
                                double real_annuitize = 0;
                                if (scenario.ria_index != null)
                                {
                                        real_annuitize = consume_annual * aa[scenario.ria_aa_index];
                                        consume_annual -= real_annuitize;
                                        double ria_purchase = real_annuitize * (1 - config.tax_rate_annuity) / annuity_stats.real_annuity_price[period + y];
                                        ria += ria_purchase;
                                        first_payout += first_payout_fract * ria_purchase;
                                }
                                double nominal_annuitize = 0;
                                if (scenario.nia_index != null)
                                {
                                        nominal_annuitize = consume_annual * aa[scenario.nia_aa_index];
                                        consume_annual -= nominal_annuitize;
                                        double nia_purchase = nominal_annuitize * (1 - config.tax_rate_annuity) / annuity_stats.nominal_annuity_price[period + y];
                                        nia += nia_purchase;
                                        first_payout += first_payout_fract * nia_purchase;
                                }
                                double annuitize = real_annuitize + nominal_annuitize;
                                if ((scenario.ria_index != null || scenario.nia_index != null) && config.tax_rate_annuity != 0)
                                {
                                        assert(!(generate && scenario.nia_index == null)); // Require nia if SPIA taxation.
                                        double nia_tax_credit = annuitize * config.tax_rate_annuity / annuity_stats.annuity_le[period + y];
                                        nia += nia_tax_credit;
                                        first_payout += first_payout_fract * nia_tax_credit;
                                        if (!generate && config.tax_annuity_credit_expire) // Can't simulate expiration of tax credit when generate.
                                        {
                                                int expire = period + y + annuity_stats.annuity_le[period + y];
                                                if (expire < tax_annuity_credit_expire.length)
                                                        tax_annuity_credit_expire[expire] += cpi * nia_tax_credit;
                                                nia -= tax_annuity_credit_expire[period + y] / cpi;
                                        }
                                }

                                if ((retired || config.spend_pre_retirement) && variable_withdrawals)
                                {
                                        consume_annual += first_payout;
                                        double not_consumed;
                                        if (config.annuity_partial || (ria == 0 && nia == 0))
                                                not_consumed = consume_annual - aa[scenario.consume_index];
                                        else
                                                not_consumed = 0;
                                        consume_annual -= not_consumed;
                                        amount += not_consumed * returns.time_periods;
                                }
                                else
                                        amount += first_payout * returns.time_periods;

                                // Recieve income before investing.
                                p += amount;

                                if (!generate && variable_withdrawals)
                                {
                                        // Consume/unconsume any rounding errors from interpolation.
                                        // Small positive values are treated as rounding errors too; in the event of leverage they might become negative.
                                        if ((!config.negative_p && p < config.tp_zero_factor * scenario.consume_max_estimate) || (y == max_periods - 1))
                                        {
                                                // Rounding errors can be large as a result of the very large asset allocations when allocatable assets is close to zero.
                                                if (Math.abs(consume_annual + p * returns.time_periods) > 1e-15 * consume_annual)
                                                // Avoid making consume negative due to an fp precision error.
                                                {
                                                        consume_annual += p * returns.time_periods;
                                                        amount -= p;
                                                }
                                                p = 0;
                                        }
                                }

                                // Invest after computing consumption, so that the reported consumption amount is a constant.
                                double p_pre_invest = p;

                                if (pessimal)
                                {
                                        for (int i = 0; i < scenario.normal_assets; i++)
                                        {
                                            if ((aa[i] >= 0) == (p >= 0))
                                                    rets[i] = returns.pessimal[i];
                                            else
                                                    rets[i] = returns.optimal[i];
                                        }
                                }
                                else if (has_special)
                                {
                                        System.arraycopy(returns_array[index], 0, rets, 0, scenario.stochastic_classes);
                                        for (int i = 0; i < scenario.normal_assets; i++)
                                        {
                                                if (special_aa[i])
                                                        rets[i] = scenario.lm_bonds_returns[period + y];
                                        }
                                }
                                else
                                        rets = returns_array[index];

                                double tot_return = 0.0;
                                for (int i = 0; i < scenario.normal_assets; i++)
                                {
                                        tot_return += aa[i] * (1 + rets[i]);
                                }
                                ssr_terms += 1 / all_return;
                                all_return *= tot_return;

                                if (scenario.hci_index != null)
                                {
                                        if (!retired)
                                        {
                                                if (retire_next)
                                                        hci = Math.min(config.hci_retirement + config.hci_retirement_fract * hci, config.hci_retirement_max);
                                                else if (hci1)
                                                        hci += hci * rets[scenario.hci1_aa_index];
                                                else
                                                        hci += hci * rets[scenario.hci2_aa_index];
                                        }
                                }

                                p *= tot_return * operating_expense_step;
                                double p_post_invest = p;

                                p_post_inc_neg = p;

                                int new_period = period + y + 1;
                                if ((scenario.ria_index != null && config.tax_rate_annuity != 0) || scenario.nia_index != null)
                                {
                                        double cpi_delta = rets[scenario.cpi_index];
                                        assert(1 + cpi_delta >= 0);
                                        cpi *= 1 + cpi_delta;
                                        nia /= 1 + cpi_delta;
                                }

                                boolean tax_time = scenario.do_tax && (returns.time_periods < 1 || new_period % Math.round(returns.time_periods) == 0);
                                double total_tax_pending = 0;
                                double tax_amount = 0;
                                if (scenario.do_tax)
                                {
                                        // Tax depends on our new asset allocation which depends on our portfolio size which depends on how much tax we pay.
                                        // We perform a first order estimate.
                                        total_tax_pending = tax.total_pending(p_post_invest, p_pre_invest, aa, rets);
                                        // It may be worth performing a second order estimate when generating.
                                        // Empirically though this hasn't been found to make any difference.
                                        //
                                        // if (!generate)
                                        // {
                                        //         res = lookup_bucket(null, p - total_tax_pending, new_period, generate, rets);
                                        //         total_tax_pending = tax.total_pending(p_post_invest, p_pre_invest, res.aa, rets);
                                        // }
                                }

                                // Get aa recommendation.
                                double[] aa_prev = aa;
                                if (y + 1 < max_periods)
                                {
                                        if (returns.time_periods == config.generate_time_periods)
                                                fperiod = new_period;
                                        else
                                                fperiod = (int) (new_period * config.generate_time_periods / returns.time_periods);
                                        if (scenario.tp_index != null)
                                                li_p[scenario.tp_index] = p - total_tax_pending;
                                        if (scenario.ria_index != null)
                                                li_p[scenario.ria_index] = ria;
                                        if (scenario.nia_index != null)
                                                li_p[scenario.nia_index] = nia;
                                        if (scenario.hci_index != null)
                                                li_p[scenario.hci_index] = hci;

                                        li_me.aa = free_aa;
                                        me = aamap.map[fperiod].lookup_interpolate(li_p, true, generate, li_me);

                                        if (!generate)
                                        {
                                                // Rebalance.
                                                if (config.aa_offset != null)
                                                        aa_offset(me.aa);
                                                boolean rebalance_period = new_period % Math.round(returns.time_periods / config.rebalance_time_periods) == 0;
                                                if (!rebalance_period || config.rebalance_band_hw > 0)
                                                {
                                                        double[] new_aa = aa.clone(); // Tangency not well defined.
                                                        double new_aa_sum = 0.0;
                                                        for (int a = 0; a < scenario.normal_assets; a++)
                                                        {
                                                                double alloc = aa[a] * (1 + rets[a]);
                                                                new_aa[a] = alloc;
                                                                new_aa_sum += alloc;
                                                        }
                                                        for (int a = 0; a < scenario.normal_assets; a++)
                                                                new_aa[a] /= new_aa_sum;
                                                        aa = new_aa;
                                                        if (rebalance_period)
                                                        {
                                                                for (int a = 0; a < scenario.normal_assets; a++)
                                                                {
                                                                        if (Math.abs(aa[a] - me.aa[a]) >= config.rebalance_band_hw)
                                                                        {
                                                                                aa = me.aa;
                                                                                break;
                                                                        }
                                                                }
                                                        }
                                                }
                                                else
                                                {
                                                        aa = me.aa;
                                                }
                                                if (tax_time)
                                                {
                                                        tax_amount = tax.tax(p_post_invest, p_pre_invest, aa, rets);
                                                        if (cost_basis_method_immediate)
                                                                tax_amount = total_tax_pending; // Ensure generated and simulated metrics match for immediate.
                                                        p -= tax_amount;
                                                }
                                        }
                                }
                                else
                                {
                                        aa = null;
                                }

                                // Record solvency.
                                // Consumption might have been reduced to prevent p falling below 0.  Interpolate based on where it would have fallen.
                                double solvent;
                                if (scenario.success_mode_enum == MetricsEnum.TW || scenario.success_mode_enum == MetricsEnum.NTW)
                                {
                                        assert(config.floor == 0);
                                        // Get artifacts if not smooth. AA plot contains horizontal lines at low RPS in retirement.
                                        if (p_post_inc_neg >= config.tp_floor && p_prev_inc_neg >= config.tp_floor)
                                        {
                                                solvent = 1.0;
                                        }
                                        else if (p_prev_inc_neg >= config.tp_floor)
                                        {
                                                // Interpolate solvency in year of bankruptcy.
                                                solvent = (p_prev_inc_neg - config.tp_floor) / (p_prev_inc_neg - p_post_inc_neg);
                                        }
                                        else if (p_post_inc_neg >= config.tp_floor)
                                        {
                                                // Contribution brought us out of insolvency.
                                                solvent = (p_post_inc_neg - config.tp_floor) / (p_post_inc_neg - p_prev_inc_neg);
                                        }
                                        else
                                        {
                                                solvent = 0.0;
                                        }
                                }
                                else
                                {
                                        solvent = (consume_annual > config.floor ? 1 : 0); // No easy way to smooth.
                                }
                                if (solvent < 1)
                                        solvent_always = 0;
                                double floor_path_utility = 0.0;
                                double upside_path_utility = 0.0;
                                if ((consume_annual >= 0) && ((p_post_inc_neg >= 0) || (config.negative_p) && (y + 1 < max_periods)))
                                {
                                        // Avoid recomputing utility when generate.
                                        if (consume_annual != consume_annual_key)
                                        {
                                                consume_annual_key = consume_annual;
                                                double floor;
                                                double upside;
                                                if (config.utility_join)
                                                {
                                                        floor = Math.min(consume_annual_key, config.utility_join_required);
                                                        upside = consume_annual_key - floor;
                                                }
                                                else
                                                {
                                                        floor = consume_annual_key;
                                                        upside = 0;
                                                }
                                                floor_utility = aamap.uc_time.utility(floor);
                                                if (upside == 0)
                                                        upside_utility = uct_u_ujp;
                                                else
                                                        upside_utility = aamap.uc_time.utility(config.utility_join_required + upside);
                                        }
                                }
                                else
                                {
                                        floor_utility = Double.NEGATIVE_INFINITY; // Infeasible. Will propagate through the system.
                                        upside_utility = uct_u_ujp;
                                }
                                floor_path_utility += floor_utility;
                                upside_path_utility += upside_utility;
                                double consume_path_utility = floor_path_utility;
                                if (config.utility_join)
                                        consume_path_utility += upside_path_utility - uct_u_ujp;
                                double upside_alive_discount;
                                if (generate && aamap1 != null)
                                {
                                        consume_alive_discount = config.couple_weight1 * vital_stats.vital_stats1.alive[period + y + book_post] + (1 - config.couple_weight1) * vital_stats.vital_stats2.alive[period + y + book_post];
                                        upside_alive_discount = config.couple_weight1 * vital_stats.vital_stats1.upside_alive[period + y + book_post] + (1 - config.couple_weight1) * vital_stats.vital_stats2.upside_alive[period + y + book_post];
                                }
                                else
                                {
                                        consume_alive_discount = utility_weight * vital_stats.alive[period + y + book_post];
                                        upside_alive_discount = utility_weight * vital_stats.upside_alive[period + y + book_post];
                                }
                                double path_element_weight = consume_alive_discount;
                                if (!compute_utility)
                                {
                                        consume_alive_discount = 0;
                                        upside_alive_discount = 0;
                                }
                                double floor_goal_path_elem = consume_alive_discount * floor_path_utility;
                                // Avoid 0 * Inf = NaN.
                                if (consume_alive_discount == 0)
                                        floor_goal_path_elem = 0;
                                double upside_goal_path_elem = upside_alive_discount * upside_path_utility;
                                double join_elem = upside_alive_discount * uct_u_ujp / returns.time_periods;
                                double consume_goal_path_elem = floor_goal_path_elem;
                                if (config.utility_join)
                                        consume_goal_path_elem += upside_goal_path_elem - join_elem;
                                floor_goal_path += floor_goal_path_elem;
                                upside_goal_path += upside_goal_path_elem;
                                consume_goal_path += consume_goal_path_elem;
                                combined_goal_path += consume_goal_path_elem;
                                if (config.utility_dead_limit != 0.0 && compute_utility)
                                {
                                        // We ignore any taxes that may be pending at death.
                                        double inherit_utility = scenario.utility_inherit.utility(p_prev_exc_neg);
                                        // We now use p_prev_inc_amount in place of inherit_p in the utility function above.
                                        // Effectively death occurs at the start of the cycle.
                                        // donate_above makes an estimate of where donation utility exceeds aggregate utility that would
                                        // otherwise be experienced. Unfortunately, in the presence of high death probabilities, the aggregate
                                        // utility might do best just below this point on account of the additional utility from the use of inherit_p.
                                        // As consumption increases, inherit utility falls, but by too much because inherit_p is typically larger
                                        // than p_prev_inc_amount. For higher initial p utility is reduced more.
                                        // This reduces the true location of donate above, and so the calculated donate above is irrelevant.
                                        // A lower non-donating consumption will be selected.
                                        // In practical terms, when we used inherit_p, we found no donations occuring for ages 100-119.
                                        inherit_goal_path += dying * inherit_utility;

                                        // Feel like we should be able to do:
                                        //     double combined_goal_path += inherit_goal;
                                        // but can't since utility is not additive/power and exponential utility have a maximum asymptote which we could exceed.
                                        // Instead we pro-rate the distance to the asymptote.
                                        double inherit_proportion = (inherit_utility - scenario.utility_inherit.u_0) / (scenario.utility_inherit.u_inf - scenario.utility_inherit.u_0);
                                        double combined_inherit_utility;
                                        if (consume_path_utility == Double.NEGATIVE_INFINITY || aamap.uc_time.u_inf == Double.POSITIVE_INFINITY)
                                                combined_inherit_utility = 0;
                                        else
                                                combined_inherit_utility = inherit_proportion * (aamap.uc_time.u_inf - consume_path_utility);
                                        assert(consume_path_utility + combined_inherit_utility <= aamap.uc_time.u_inf);
                                        combined_goal_path += consume_alive_discount * config.utility_dead_limit * combined_inherit_utility / returns.time_periods;
                                                // Multiply by consume_alive_discount not dying because well-being is derived from being able to bequest,
                                                // not the actual bequest.
                                }
                                tax_goal_path += consume_alive_discount * tax_amount * returns.time_periods;
                                if (!config.skip_metric_wer && !generate)
                                {
                                        assert(retired);
                                        assert(!monte_carlo_validate);
                                        double sum_alive = vital_stats.bounded_sum_avg_alive[period];
                                        sum_alive -= vital_stats.bounded_sum_avg_alive[period + y + 1];
                                        double cew = uc_time.inverse_utility(combined_goal_path / sum_alive) - current_guaranteed_income;
                                        double ssr = bucket_p[scenario.tp_index] / ssr_terms;
                                        wer_path += raw_dying * cew / ssr;
                                }
                                if (scenario.success_mode_enum == MetricsEnum.COST)
                                {
                                        // Expensive.
                                        cost_path += amount * Math.pow(1.0 + config.ret_borrow, - (period + y) / returns.time_periods);
                                }
                                tw_goal_path += alive * solvent;
                                ntw_goal_path += raw_dying * solvent_always;

                                if (!generate && monte_carlo_validate)
                                {
                                        divisor_saa += alive * returns_probability;
                                        divisor_bsaa += consume_alive_discount * returns_probability;
                                        divisor_bsaua += upside_alive_discount * returns_probability;
                                }

                                // Record path.
                                if (s < num_paths_record)
                                {
                                        path.add(new PathElement(aa_prev, p_prev_inc_neg, consume_annual, ria_prev, nia_prev, hci_prev, real_annuitize, nominal_annuitize, tax_amount, path_element_weight));
                                }
                                free_aa = aa_prev;

                                // Next iteration.
                                y += 1;
                                index = (index + 1) % len_returns;
                        }

                        // Record solvency.
                        if (!generate || period == total_periods - 1)
                        {
                                ntw_goal_path += raw_alive * solvent_always;
                        }

                        // Add individual path metrics to overall metrics.
                        tw_goal += tw_goal_path * returns_probability;
                        ntw_goal += ntw_goal_path * returns_probability;
                        floor_goal += floor_goal_path * returns_probability;
                        upside_goal += upside_goal_path * returns_probability;
                        consume_goal += consume_goal_path * returns_probability;
                        combined_goal += combined_goal_path * returns_probability;
                        inherit_goal += inherit_goal_path * returns_probability;
                        tax_goal += tax_goal_path * returns_probability;
                        wer += wer_path * returns_probability;
                        cost += cost_path * returns_probability;

                        // The following code is performance critical.
                        if (generate && max_periods > 1)
                        {
                                if (!monte_carlo_validate || aamap1 == null)
                                {
                                        final boolean maintain_all = generate && !config.skip_dump_log && !config.conserve_ram;
                                        if (maintain_all)
                                        {
                                                for (MetricsEnum m : MetricsEnum.values())
                                                {
                                                        metrics.set(m, metrics.get(m) + me.results.metrics.get(m) * returns_probability);
                                                }
                                        }
                                        else
                                        {
                                                // Get and set are slow; access fields directly.
                                                metrics.metrics[scenario.success_mode_enum.ordinal()] += me.metric_sm * returns_probability;
                                                // Other metric values invalid.
                                        }
                                }
                                else
                                {
                                        System.arraycopy(li_p, 0, li_p1, 0, li_p.length);
                                        System.arraycopy(li_p, 0, li_p2, 0, li_p.length);
                                        if (scenario.ria_index != null)
                                        {
                                                li_p1[scenario.ria_index] *= config.couple_annuity1;
                                                li_p2[scenario.ria_index] *= 1 - config.couple_annuity1;
                                        }
                                        if (scenario.nia_index != null)
                                        {
                                                li_p1[scenario.nia_index] *= config.couple_annuity1;
                                                li_p2[scenario.nia_index] *= 1 - config.couple_annuity1;
                                        }
                                        MapElement me1 = aamap1.map[fperiod].lookup_interpolate(li_p1, true, generate, li_me1);
                                        MapElement me2 = aamap2.map[fperiod].lookup_interpolate(li_p2, true, generate, li_me2);

                                        double alive1 = vital_stats.vital_stats1.raw_alive[period + 1] == 0 ? 0 : vital_stats.vital_stats1.raw_alive[period + 1] / vital_stats.vital_stats1.raw_alive[period];
                                        double alive2 = vital_stats.vital_stats2.raw_alive[period + 1] == 0 ? 0 : vital_stats.vital_stats2.raw_alive[period + 1] / vital_stats.vital_stats2.raw_alive[period];
                                        // This doesn't mesh perfectly with couple_unit=true because
                                        // here we take advantage of knowledge of when one member is dead.
                                        double m_sm = alive1 * alive2 * me.metric_sm;
                                        m_sm += config.couple_weight1 * alive1 * (1 - alive2) * me1.metric_sm;
                                                // No need for:
                                                //         uc_time.utility(aamap1.uc_time.inverse_utility(me1.metric_sm))
                                                // because aamap1.uc_time is a simple scaling of uc_time.
                                        m_sm += (1 - config.couple_weight1) * (1 - alive1) * alive2 * me2.metric_sm;
                                        m_sm /= alive1 * alive2 + config.couple_weight1 * alive1 * (1 - alive2) + (1 - config.couple_weight1) * (1 - alive1) * alive2;
                                        metrics.set(scenario.success_mode_enum, metrics.get(scenario.success_mode_enum) + m_sm * returns_probability);
                                }
                        }

                        // Record path.
                        if (s < num_paths_record)
                        {
                                // 8% speedup by not recording path if know it is not needed
                                path.add(new PathElement(null, p, Double.NaN, ria, nia, hci, Double.NaN, Double.NaN, Double.NaN, 0));
                                        // Ignore any pending taxes associated with p, mainly because they are difficult to compute.
                                paths.add(path);
                        }
                }

                if (generate && max_periods > 1)
                {
                        tw_goal += metrics.get(MetricsEnum.TW) * generate_stats.sum_avg_alive[period + 2];
                        ntw_goal += metrics.get(MetricsEnum.NTW) * generate_stats.raw_alive[period + 1];
                        floor_goal += metrics.get(MetricsEnum.FLOOR) * generate_stats.bounded_sum_avg_alive[period + 1 + book_post];
                        upside_goal += metrics.get(MetricsEnum.UPSIDE) * generate_stats.bounded_sum_avg_upside_alive[period + 1 + book_post];
                        consume_goal += metrics.get(MetricsEnum.CONSUME) * generate_stats.bounded_sum_avg_alive[period + 1 + book_post];
                        if (config.utility_epstein_zin)
                        {
                                assert(!monte_carlo_validate);
                                double divisor = generate_stats.bounded_sum_avg_alive[period];
                                double future_utility_risk = metrics.get(MetricsEnum.COMBINED);
                                double future_utility_time = uc_time.utility(uc_risk.inverse_utility(future_utility_risk));
                                combined_goal = (combined_goal + (divisor - consume_alive_discount) * future_utility_time) / divisor;
                        }
                        else
                        {
                                if (aamap1 == null)
                                        combined_goal += metrics.get(MetricsEnum.COMBINED) * generate_stats.bounded_sum_avg_alive[period + 1 + book_post];
                                else
                                        combined_goal += metrics.get(MetricsEnum.COMBINED) * (config.couple_weight1 * generate_stats.vital_stats1.bounded_sum_avg_alive[period + 1 + book_post] + (1 - config.couple_weight1) * generate_stats.vital_stats2.bounded_sum_avg_alive[period + 1 + book_post]);
                        }
                        tax_goal += metrics.get(MetricsEnum.TAX) * generate_stats.bounded_sum_avg_alive[period + 1 + book_post];
                        cost += metrics.get(MetricsEnum.COST);
                }

                if (generate || !monte_carlo_validate)
                {
                        divisor_saa = original_vital_stats.sum_avg_alive[period + 1];
                        if (aamap1 == null)
                        {
                                divisor_bsaa = original_vital_stats.bounded_sum_avg_alive[period + book_post];
                                divisor_bsaua = original_vital_stats.bounded_sum_avg_upside_alive[period + book_post];
                        }
                        else
                        {
                                divisor_bsaa = config.couple_weight1 * original_vital_stats.vital_stats1.bounded_sum_avg_alive[period + book_post] + (1 - config.couple_weight1) * original_vital_stats.vital_stats2.bounded_sum_avg_alive[period + book_post];
                                divisor_bsaua = config.couple_weight1 * original_vital_stats.vital_stats1.bounded_sum_avg_upside_alive[period + book_post] + (1 - config.couple_weight1) * original_vital_stats.vital_stats2.bounded_sum_avg_upside_alive[period + book_post];
                        }
                }
                divisor_ra = original_vital_stats.raw_alive[period];
                divisor_a = original_vital_stats.alive[period];

                if (generate && scenario.vw_strategy.equals("retirement_amount") && !(config.start_tp == 0 && config.accumulation_rate == 0))
                {
                        // This is a run time strategy. The withdrawal amount will vary depending on the run not the map, and so generated metrics are invalid.
                        // As a special exception we allow start_tp=0 && accumulation_rate=0 so we can use retirement_amount to validate guaranteed income.
                        floor_goal = 0;
                        upside_goal = 0;
                        consume_goal = 0;
                        inherit_goal = 0;
                        combined_goal = 0;
                        tax_goal = 0;
                        wer = 0;
                        cost = 0;
                }
                else if (config.utility_epstein_zin)
                {
                        if (generate)
                                combined_goal = uc_risk.utility(uc_time.inverse_utility(combined_goal));
                        else
                                combined_goal = 0; // Epstein-Zin utility can't be estimated by simulating paths.
                }
                else
                {
                        if (divisor_bsaa == 0)
                                assert(combined_goal == 0);
                        else
                                combined_goal /= divisor_bsaa;
                }
                if (config.retirement_age > config.start_age)
                        wer = 0;

                // For reporting and success map display purposes keep goals normalized across ages.
                if (divisor_saa == 0)
                        assert(tw_goal == 0);
                else
                        tw_goal /= divisor_saa;
                if (divisor_ra == 0)
                        assert(ntw_goal == 0);
                else
                        ntw_goal /= divisor_ra;
                if (divisor_bsaa == 0)
                        assert(floor_goal == 0);
                else
                        floor_goal /= divisor_bsaa;
                if (divisor_bsaua == 0)
                        assert(upside_goal == 0);
                else
                        upside_goal /= divisor_bsaua;
                if (divisor_bsaa == 0)
                        assert(consume_goal == 0);
                else
                        consume_goal /= divisor_bsaa;
                if (divisor_a == 0)
                        assert(inherit_goal == 0);
                else
                        inherit_goal /= divisor_a;
                if (divisor_bsaa == 0)
                        assert(tax_goal == 0);
                else
                        tax_goal /= divisor_bsaa;
                if (divisor_ra == 0)
                        assert(wer == 0);
                else
                        wer /= divisor_ra;

                if (-1-9 < tw_goal && tw_goal <= 0)
                        tw_goal = 0;
                if (1.0 < tw_goal && tw_goal <= 1.0 + 1e-6)
                        tw_goal = 1.0;
                if (-1-9 < ntw_goal && ntw_goal <= 0)
                        ntw_goal = 0;
                if (1.0 < ntw_goal && ntw_goal <= 1.0 + 1e-6)
                        ntw_goal = 1.0;
                assert (0.0 <= tw_goal && tw_goal <= 1.0);
                assert (0.0 <= ntw_goal && ntw_goal <= 1.0);

                Metrics result_metrics = new Metrics(tw_goal, ntw_goal, floor_goal, upside_goal, consume_goal, inherit_goal, combined_goal, tax_goal, wer, cost);

                String metrics_str = null;  // Useful for debugging.
                if (!config.skip_dump_log)
                {
                        StringBuilder sb = new StringBuilder();
                        sb.append("{'CONSUME': ");     sb.append(result_metrics.get(MetricsEnum.CONSUME));
                        sb.append(", 'INHERIT': ");    sb.append(result_metrics.get(MetricsEnum.INHERIT));
                        sb.append(", 'SUBMETRICS': "); sb.append(metrics.get(MetricsEnum.COMBINED));
                        //sb.append(", 'SUBCONSUME': "); sb.append(metrics.get(MetricsEnum.CONSUME));
                        //sb.append(", 'SUBINHERIT': "); sb.append(metrics.get(MetricsEnum.INHERIT));
                        sb.append("}");
                        metrics_str = sb.toString();
                }

                return new SimulateResult(result_metrics, spend_annual, consume_annual, first_payout, paths, metrics_str);
        }

        // Validation.
        private SimulateResult simulate_paths(int period, Integer num_sequences, int num_paths_record, double[] p, Returns returns, int bucket)
        {
                SimulateResult res = simulate(null, p, period, num_sequences, num_paths_record, false, false, returns, bucket);
                return res;
        }

        public Metrics[] simulate_retirement_number(final Returns returns) throws ExecutionException
        {
                Metrics[] metrics = new Metrics[config.retirement_number_steps + 1];
                for (int bucket = 0; bucket < config.retirement_number_steps + 1; bucket++)
                {
                        double tp = bucket * config.retirement_number_max_factor * scenario.retirement_number_max_estimate / config.retirement_number_steps;
                        double[] p = scenario.start_p.clone();
                        p[scenario.tp_index] = tp;
                        PathMetricsResult pm = path_metrics(config.retirement_age, p, config.num_sequences_retirement_number, false, config.validate_paths_seed, returns);
                        metrics[bucket] = pm.means;
                }

                return metrics;
        }

        public double jpmorgan_metric(int age, List<List<PathElement>> paths, int num_batches, Returns returns)
        {
                assert(config.max_jpmorgan_paths % num_batches == 0);
                int first_age = age;
                int period_offset = (int) Math.round((age - config.start_age) * returns.time_periods);
                if (config.utility_retire && age < config.retirement_age)
                        first_age = config.retirement_age;
                int first_period = (int) Math.round((first_age - scenario.validate_age) * returns.time_periods);
                double u = 0;
                for (int period = first_period; period < (int) ((scenario.ss.max_years - (scenario.validate_age - config.start_age)) * returns.time_periods); period++)
                {
                        double u2 = 0;
                        int num_paths = config.max_jpmorgan_paths / num_batches;
                        for (int pi = 0; pi < num_paths; pi++)
                        {
                                List<PathElement> path = paths.get(pi);
                                PathElement e = path.get(period);
                                double u_consume = uc_time.utility(e.consume_annual);
                                double u_inherit = scenario.utility_inherit.utility((e.p > 0) ? e.p : 0);
                                double u_combined = u_consume;
                                if (config.utility_dead_limit != 0)
                                {
                                        double inherit_proportion = (u_inherit - scenario.utility_inherit.u_0) / (scenario.utility_inherit.u_inf - scenario.utility_inherit.u_0);
                                        u_combined += config.utility_dead_limit * inherit_proportion * (uc_time.u_inf - u_consume);
                                }
                                u2 += uc_risk.utility(uc_time.inverse_utility(u_combined));
                        }
                        u2 /= num_paths;
                        double weight = 0;
                        if (!config.utility_retire || period >= Math.round((config.retirement_age - config.start_age) * returns.time_periods))
                                weight = (scenario.ss.validate_stats.alive[period_offset + period] + scenario.ss.validate_stats.alive[period_offset + period + 1]) / 2;
                        u += weight * uc_time.utility(uc_risk.inverse_utility(u2));
                }
                u /= scenario.ss.validate_stats.bounded_sum_avg_alive[period_offset];

                return u;
        }


        public PathMetricsResult path_metrics(final int age, final double[] p, Integer num_sequences, boolean record_paths, final int seed, final Returns returns) throws ExecutionException
        {
                double max_paths = 0;
                if (record_paths)
                {
                        max_paths = Math.max(config.max_distrib_paths, Math.max(config.max_pct_paths, Math.max(config.max_delta_paths, config.max_display_paths)));
                        if (!config.skip_metric_jpmorgan)
                                max_paths = Math.max(max_paths, config.max_jpmorgan_paths);
                }

                // Compute paths in batches so that we can calculate a sample standard deviation of the mean.
                Integer batch_size;
                int num_batches;
                if (num_sequences == null || num_sequences == 1)
                {
                        batch_size = num_sequences;
                        num_batches = 1;
                }
                else
                {
                        assert (num_sequences % config.path_metrics_bucket_size == 0);
                        batch_size = config.path_metrics_bucket_size;
                        num_batches = num_sequences / batch_size;
                }
                final int num_paths_record = (int) Math.ceil((double) max_paths / num_batches);

                final SimulateResult[] results = new SimulateResult[num_batches];
                final List<List<PathElement>> paths = new ArrayList<List<PathElement>>();

                List<Callable<Integer>> tasks = new ArrayList<Callable<Integer>>();
                final int batchesPerTask = ((int) Math.ceil(num_batches / (double) config.tasks_validate));
                final Integer fbatch_size = batch_size;
                final int fnum_batches = num_batches;
                final Random random = new Random(seed);
                for (int i0 = 0; i0 < num_batches; i0 += batchesPerTask)
                {
                        final int fi0 = i0;
                        final int fseed = random.nextInt();
                        tasks.add(new Callable<Integer>()
                        {
                                public Integer call()
                                {
                                        Thread.currentThread().setPriority((Thread.MIN_PRIORITY + Thread.NORM_PRIORITY) / 2);
                                        Random rand = new Random(fseed);
                                        int i1 = Math.min(fnum_batches, fi0 + batchesPerTask);
                                        for (int i = fi0; i < i1; i++)
                                        {
                                                Returns local_returns = returns.clone();
                                                local_returns.setSeed(rand.nextInt());
                                                results[i] = simulate_paths((int) Math.round((age - config.start_age) * returns.time_periods), fbatch_size, num_paths_record, p, local_returns, i);
                                                if (!config.skip_metric_jpmorgan)
                                                        results[i].metrics.set(MetricsEnum.JPMORGAN, jpmorgan_metric(age, results[i].paths, fnum_batches, returns));
                                        }
                                        return null;
                                }
                        });
                }

                invoke_all(tasks);

                Metrics means = new Metrics();
                Metrics standard_deviations = new Metrics();
                for (MetricsEnum metric : MetricsEnum.values())
                {
                        List<Double> samples = new ArrayList<Double>();
                        for (int i = 0; i < results.length; i++)
                        {
                                samples.add(results[i].metrics.get(metric));
                                for (List<PathElement> pl : results[i].paths)
                                        if (paths.size() < max_paths)
                                                paths.add(pl);
                                        else
                                                break;
                        }
                        means.set(metric, Utils.mean(samples));
                        standard_deviations.set(metric, Utils.standard_deviation(samples) / Math.sqrt(num_batches));
                                // Standard deviation of the sample mean is proportional to 1 sqrt(number of samples).
                }
                return new PathMetricsResult(scenario, means, standard_deviations, paths);
        }

        public TargetResult rps_target(int age, double target, Returns returns_target, boolean under_estimate) throws ExecutionException
        {
                double high = scenario.tp_high;
                double low = 0.0;
                double high_target = Double.NaN;
                double low_target = Double.NaN;
                double target_mean = Double.NaN;
                boolean first_time = true;
                while (high - low > 0.005 * scenario.tp_max_estimate)
                {
                        double mid = (high + low) / 2;
                        double p_mid[] = scenario.start_p.clone();
                        p_mid[scenario.tp_index] = mid;
                        PathMetricsResult r = path_metrics(age, p_mid, config.num_sequences_target, false, 0, returns_target);
                        target_mean = r.means.get(scenario.success_mode_enum);
                        if (target_mean == target && first_time)
                        {
                                // Trying to target 100% success.
                                high = Double.NaN;
                                break;
                        }
                        first_time = false;
                        if (target_mean < target)
                        {
                                low = mid;
                                low_target = target_mean;
                        }
                        else
                        {
                                high = mid;
                                high_target = target_mean;
                        }
                }
                if (under_estimate)
                        return new TargetResult(this, low, low_target);
                else
                        return new TargetResult(this, high, high_target);
        }

        // public TargetResult rcr_target(int age, double target, boolean baseline, Returns returns_generate, Returns returns_target, boolean under_estimate) throws ExecutionException, IOException
        // {
        //         double keep_rcr = config.accumulation_rate;
        //      double high = scenario.consume_max_estimate;
        //      double low = 0.0;
        //      AAMap map_loaded = null;
        //      double high_target = Double.NaN;
        //      double low_target = Double.NaN;
        //      double target_mean = Double.NaN;
        //      boolean first_time = true;
        //      while (high - low > 0.00002 * scenario.consume_max_estimate)
        //      {
        //              double mid = (high + low) / 2;
        //              config.accumulation_rate = mid;
        //              if (baseline) {
        //                      map_loaded = this;
        //              } else {
        //                      AAMapGenerate map_precise = new AAMapGenerate(scenario, returns_generate);
        //                      map_loaded = new AAMapDumpLoad(scenario, map_precise);
        //              }
        //              PathMetricsResult r = map_loaded.path_metrics(age, scenario.start_p, config.num_sequences_target, false, 0, returns_target);
        //              target_mean = r.means.get(scenario.success_mode_enum);
        //              if (target_mean == target && first_time)
        //              {
        //                      high = Double.NaN;
        //                      break;
        //              }
        //              if (target_mean < target)
        //              {
        //                      low = mid;
        //                      low_target = target_mean;
        //              }
        //              else
        //              {
        //                      high = mid;
        //                      high_target = target_mean;
        //              }
        //      }
        //      config.accumulation_rate = keep_rcr;
        //      if (under_estimate)
        //              return new TargetResult(map_loaded, low, low_target);
        //      else
        //              return new TargetResult(map_loaded, high, high_target);
        // }

        public void invoke_all(List<Callable<Integer>> tasks) throws ExecutionException
        {
                try
                {
                        List<Future<Integer>> future_tasks = scenario.ss.executor.invokeAll(tasks); // Will block until all tasks are finished
                        // If a task dies due to an assertion error, it can't be caught within the task, so we probe for it here.
                        for (Future<Integer> f : future_tasks)
                                //try
                                //{
                                //      f.get();
                                //} catch (Exception e) {
                                //      e.printStackTrace();
                                //      System.exit(1);
                                //}
                                f.get();
                }
                catch (InterruptedException e)
                {
                        System.exit(1);
                }
        }

        // Human readable dump of generated data.
        public void dump_log()
        {
                for (int pi = 0; pi < map.length; pi++)
                {
                        System.out.printf("age %.2f:\n", (pi + config.start_age * config.generate_time_periods) / config.generate_time_periods);
                        for (MapElement me : map[pi])
                                System.out.println(me);
                }
        }

        private double max_stocks()
        {
                double max_stocks = 1.0;
                if (!config.ef.equals("none"))
                {
                        assert(scenario.normal_assets == 2);
                        assert(scenario.asset_classes.contains("stocks"));
                        assert(scenario.asset_classes.contains("bonds"));

                        max_stocks = 0.0;
                        for (double[] aa : scenario.aa_ef)
                                max_stocks = Math.max(max_stocks, aa[scenario.asset_classes.indexOf("stocks")]);
                }

                return max_stocks;
        }

        private double[] target_date_stocks = new double[] { 0.316, 0.422, 0.519, 0.609, 0.684, 0.754, 0.803, 0.844, 0.877, 0.903 };
                // S&P Target Date indexes as reported by iShares prospectus of 2012-12-01 for holdings as of 2012-06-30.
        private double target_date_offset = -5 + -2.5;

        private double weighted_alive(VitalStats vital_stats, int period, int ref_period)
        {
                if (config.couple_unit || vital_stats.vital_stats1 == null)
                        return vital_stats.raw_alive[period] / vital_stats.raw_alive[ref_period];
                else
                {
                        double alive1 = vital_stats.vital_stats1.raw_alive[period] / vital_stats.vital_stats1.raw_alive[ref_period];
                        double alive2 = vital_stats.vital_stats2.raw_alive[period] / vital_stats.vital_stats2.raw_alive[ref_period];
                        return alive1 * alive2 + config.couple_db * (alive1 * (1 - alive1) + (1 - alive1) * alive2);
                }
        }

        protected double[] generate_aa(String aa_strategy, double age, double[] p)
        {
                double bonds;
                if (aa_strategy.equals("fixed_aa"))
                {
                        assert(config.fixed_aa.length == scenario.normal_assets);
                        assert(Math.abs(Utils.sum(config.fixed_aa) - 1) < 1e-6);
                        double[] aa = new double[scenario.asset_classes.size()];
                        System.arraycopy(config.fixed_aa, 0, aa, 0, config.fixed_aa.length);
                        return aa;
                }
                else if (aa_strategy.equals("fixed"))
                        bonds = 1 - scenario.fixed_stocks;
                else if (aa_strategy.equals("age_in_bonds"))
                        bonds = age / 100.0;
                else if (aa_strategy.equals("age_minus_10_in_bonds"))
                        bonds = (age - 10) / 100.0;
                else if (aa_strategy.equals("target_date"))
                {
                        double ytr = config.retirement_age - age;
                        double findex = (ytr - target_date_offset) / 5;
                        int index = (int) Math.floor(findex);
                        double stocks;
                        if (index < 0)
                                stocks = target_date_stocks[0];
                        else if (index + 1 >= target_date_stocks.length)
                                stocks = target_date_stocks[target_date_stocks.length - 1];
                        else
                                stocks = target_date_stocks[index] * (1 - (findex - index)) + target_date_stocks[index + 1] * (findex - index);
                        bonds = 1 - stocks;
                }
                else
                {
                        assert(false);
                        bonds = Double.NaN;
                }

                bonds = Math.min(1, bonds);

                if (guaranteed_income != 0 && config.db_bond || config.savings_bond)
                {
                        int period = (int) Math.round((age - config.start_age) * config.generate_time_periods);
                        int retire_period = (int) Math.round((Math.max(age, config.retirement_age) - config.start_age) * config.generate_time_periods);
                        double future_income = 0;
                        for (int pp = period; pp < scenario.ss.generate_stats.dying.length; pp++)
                        {
                                VitalStats vital_stats = scenario.ss.generate_stats;
                                double income = 0;
                                int ref_period = period;
                                if (pp < Math.round((config.retirement_age - config.start_age) * config.generate_time_periods))
                                {
                                        if (config.savings_bond)
                                        {
                                                if (pp == period)
                                                        continue;
                                                income = config.accumulation_rate * Math.pow(config.accumulation_ramp, pp / config.generate_time_periods);
                                        }
                                }
                                else
                                {
                                        if (config.db_bond)
                                        {
                                                if (config.vbond_discounted)
                                                {
                                                        if (pp == period)
                                                                continue;
                                                }
                                                else
                                                        // If not discounting include pp=period and approximate chance of being alive at retirement_age as 1
                                                        // so that rule of thumb can lookup le from a table.
                                                        ref_period = retire_period;
                                                income = guaranteed_income;
                                        }
                                }
                                double avg_alive = weighted_alive(vital_stats, pp, ref_period);
                                income *= avg_alive;
                                if (config.vbond_discounted)
                                        income /= Math.pow((1 + config.vbond_discount_rate), (pp - period) / config.generate_time_periods);
                                future_income += income;
                        }
                        if (p[scenario.tp_index] > 0)
                            bonds -= (1 - bonds) * future_income / p[scenario.tp_index];
                                        // db_bonds * (p + inc) = std_bonds * (p + inc).
                                        // db_bonds = (std_bonds * p + inc) / (p + inc).
                                        // db_bonds * (p + inc) - inc = std_bonds * p.
                                        // db_bonds * (1 + inc / p) - inc / p = std_bonds.
                                        // std_bonds = db_bonds - (1 - db_bonds) * inc / p.
                        else if (bonds < 1)
                                bonds = 0;
                }

                double max_stocks = max_stocks();
                bonds = Math.max(1 - max_stocks, bonds);

                double[] aa = new double[scenario.asset_classes.size()];
                int stock_index = scenario.asset_classes.indexOf("stocks");
                int bond_index = scenario.asset_classes.indexOf("bonds");
                if (stock_index == -1)
                         stock_index = scenario.asset_classes.indexOf("stocks_sbbi");
                if (bond_index == -1)
                         bond_index = scenario.asset_classes.indexOf("bonds_sbbi");
                aa[stock_index] = 1 - bonds;
                aa[bond_index] = bonds;

                return aa;
        }

        private static AAMap sub_factory(Scenario scenario, String aa_strategy, Returns returns, AAMap aamap1, AAMap aamap2, VitalStats generate_stats, VitalStats validate_stats, Utility uc_time, Utility uc_risk, double guaranteed_income) throws IOException, ExecutionException
        {
                if (returns != null)
                        return new AAMapGenerate(scenario, returns, aamap1, aamap2, generate_stats, validate_stats, uc_time, uc_risk, guaranteed_income);
                else
                        // returns == null. Hack. Called by targeting. Should get AAMapGenerate to handle. Then delete AAMapStatic.java.
                        return new AAMapStatic(scenario, aa_strategy, aamap1, aamap2, validate_stats, uc_time, uc_risk, guaranteed_income);
        }

        public static AAMap factory(Scenario scenario, String aa_strategy, Returns returns) throws IOException, ExecutionException
        {
                ScenarioSet ss = scenario.ss;
                Config config = scenario.config;

                if (aa_strategy.equals("file"))
                {
                        assert(config.couple_unit);
                        return new AAMapDumpLoad(scenario, config.validate, ss.validate_stats);
                }
                else if (config.sex2 == null || config.couple_unit)
                {
                        return sub_factory(scenario, aa_strategy, returns, null, null, ss.generate_stats, ss.validate_stats, scenario.utility_consume_time, scenario.utility_consume, config.defined_benefit);
                }
                else
                {
                        Utility uc_time = new UtilityScale(config, scenario.utility_consume_time, 1 / config.couple_consume);
                        Utility uc_risk = new UtilityScale(config, scenario.utility_consume, 1 / config.couple_consume);
                        AAMap aamap1 = sub_factory(scenario, aa_strategy, returns, null, null, ss.generate_stats.vital_stats1, ss.validate_stats.vital_stats1, uc_time, uc_risk, config.couple_db * config.defined_benefit);
                        AAMap aamap2 = sub_factory(scenario, aa_strategy, returns, null, null, ss.generate_stats.vital_stats2, ss.validate_stats.vital_stats2, uc_time, uc_risk, config.couple_db * config.defined_benefit);
                        return sub_factory(scenario, aa_strategy, returns, aamap1, aamap2, ss.generate_stats, ss.validate_stats, scenario.utility_consume_time, scenario.utility_consume, config.defined_benefit);
                }
        }

        public AAMap(Scenario scenario, AAMap aamap1, AAMap aamap2, VitalStats generate_stats, VitalStats validate_stats, Utility uc_time, Utility uc_risk, double guaranteed_income)
        {
                this.scenario = scenario;
                this.config = scenario.config;

                this.aamap1 = aamap1;
                this.aamap2 = aamap2;
                this.generate_stats = generate_stats;
                this.validate_stats = validate_stats;
                this.uc_time = uc_time;
                this.uc_risk = uc_risk;
                this.guaranteed_income = guaranteed_income;
        }
}
