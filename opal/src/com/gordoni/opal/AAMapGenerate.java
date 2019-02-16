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
import java.util.Iterator;
import java.util.List;
import java.util.Random;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;

public class AAMapGenerate extends AAMap
{
        private MapElement new_bucket(int[] bucket, int period)
        {
                double[] p = scenario.bucketToP(bucket);

                List<SearchResult> simulate_results = null;
                if (!config.skip_dump_log && !config.conserve_ram)
                        simulate_results = new ArrayList<SearchResult>();

                MapElement me = new MapElement(p, null, null, simulate_results, null);

                return me;
        }

        private double[] extrapolate(double[] current, double[] prior)
        {
                if (current == null)
                        return null;
                else if (prior == null || !config.ef.equals("none"))
                        return current.clone();
                else
                {
                        double[] aa = new double[scenario.asset_classes.size()];
                        for (int a = 0; a < aa.length; a++)
                                aa[a] = current[a] - (prior[a] - current[a]);
                        return aa;
                }
        }

        private boolean aa_invalid(MapElement me)
        {
                return (me != null) && (me.aa[scenario.consume_index] == me.consumable(scenario)); // Avoid getting stuck by using an aa when the aa used didn't matter.
        }

        // Generate a good hint of where to start the aa search.
        private void new_aa(int[] bucket, MapElement me, int period, MapElement sibling, MapElement prior_sibling)
        {
                double[] aa = null;

                boolean safe_search = false;
                if (config.search.equals("all"))
                        safe_search = true;
                else
                {
                        MapElement older = (period + 1 < map.length ? map[period + 1].get(bucket) : null);
                        MapElement oldest = (period + 3 < map.length ? map[period + 2].get(bucket) : null); // period + 3 since map.length - 1 aa is arbitrary, so we don't want to extrapolate from it.
                        if (oldest != null)
                        {
                                aa = extrapolate(older.aa, (oldest != null) ? oldest.aa : null);
                                safe_search = aa_invalid(older) || aa_invalid(oldest);
                        }
                        else if (sibling != null)
                        {
                                aa = extrapolate(sibling.aa, (prior_sibling != null) ? prior_sibling.aa : null);
                                safe_search = aa_invalid(sibling) || aa_invalid(prior_sibling);
                        }
                        else
                        {
                                aa = scenario.guaranteed_safe_aa();
                        }
                        if (oldest == null)
                                aa[scenario.consume_index] = Math.max(0, me.rps[scenario.tp_index] + config.defined_benefit); // Shortcut to approximate value.
                }
                if (safe_search)
                {
                        aa = scenario.guaranteed_safe_aa();
                        aa[scenario.consume_index] = 0;
                }

                me.aa = make_safe_aa(aa, me.rps, period);
        }

        public double search_difference(SimulateResult a, SimulateResult b)
        {
                double val_a = (a != null ? a.metrics.get(scenario.success_mode_enum) : Double.NEGATIVE_INFINITY);
                double val_b = (b != null ? b.metrics.get(scenario.success_mode_enum) : Double.NEGATIVE_INFINITY);
                double diff = (val_a == val_b) ? 0 : val_a - val_b; // Yield zero rather than NaN if both infinite.
                if (scenario.success_mode_enum == MetricsEnum.COST)
                        return - diff;
                else
                        return diff;
        }

        private SimulateResult search_simulate_cache(MapElement me, double[] aa, double[] p, int period, Returns returns)
        {
                String key;
                if (config.ef.equals("none"))
                {
                        StringBuilder sb_key = new StringBuilder("");
                        for (int a = 0; a < scenario.all_alloc; a++)
                        {
                                if (sb_key.length() > 0)
                                        sb_key.append("'");
                                sb_key.append(aa[a]);
                        }
                        key = sb_key.toString();
                }
                else
                {
                        key = aa[scenario.ef_index] + "," + aa[scenario.consume_index];
                }

                if (me.cache == null)
                        me.cache = new SearchCache(scenario);

                SimulateResult results = me.cache.get(key);
                String note;
                if (results == null)
                {
                        results = simulate(aa, p, period, config.num_sequences_generate, 0, true, false, returns, 0);
                        if ((config.map_headroom != null) && (results.metrics.get(scenario.success_mode_enum) != Double.NEGATIVE_INFINITY))
                        {
                                SimulateResult pessimal_results = simulate(aa, p, period, config.num_sequences_generate, 0, true, true, returns, 0);
                                if (pessimal_results.metrics.get(scenario.success_mode_enum) == Double.NEGATIVE_INFINITY)
                                        results = pessimal_results;
                        }
                        me.cache.put(key, results);
                        note = results.metrics_str;
                }
                else
                {
                        note = "hit";
                }

                if (me.simulate != null)
                        me.simulate.add(new SearchResult(aa, results.metrics.get(scenario.success_mode_enum), note));

                return results;
        }

        private double[] inc_dec_aa(double[] aa, int a, double inc, double[] p, int period)
        {
                if ((a != -1) && (a == scenario.consume_index || a == scenario.ria_aa_index || a == scenario.nia_aa_index))
                {
                        double[] new_aa = aa.clone();
                        double alloc = new_aa[a];
                        alloc += inc;
                        if (alloc <= 0)
                                alloc = 0;
                        if (a != scenario.consume_index)
                        {
                                if (alloc > 1)
                                        alloc = 1;
                        }
                        new_aa[a] = alloc;

                        return new_aa;
                }
                else if (config.ef.equals("none"))
                        return scenario.inc_dec_aa_raw(aa, a, inc, p, period);
                else
                {
                        assert(config.min_safe_le <= 0);
                        double[] new_aa = aa.clone();
                        double index = aa[scenario.ef_index] + inc * config.aa_steps;
                        int low = (int) Math.floor(index);
                        int high = (int) Math.ceil(index);
                        double weight = 1 - (index - low);
                        if (low < 0)
                        {
                                low = 0;
                                high = 0;
                                index = 0;
                                weight = 1;
                        }
                        else if (high >= scenario.aa_ef.size())
                        {
                                low = scenario.aa_ef.size() - 1;
                                high = scenario.aa_ef.size() - 1;
                                index = scenario.aa_ef.size() - 1;
                                weight = 1;
                        }
                        for (int i = 0; i < scenario.normal_assets; i++)
                                new_aa[i] = weight * scenario.aa_ef.get(low)[i] + (1 - weight) * scenario.aa_ef.get(high)[i];
                        new_aa[scenario.ef_index] = index;
                        return new_aa;
                }
        }

        private double[] make_safe_aa(double[] aa, double[] p, int period)
        {
                double[] safe_aa = inc_dec_aa(aa, -1, 0, p, period); // inc_dec_aa() with increment of zero will force respecting of min_safe.

                if (safe_aa[scenario.consume_index] < 0)
                        safe_aa[scenario.consume_index] = 0;

                return safe_aa;
        }

        private void search_all(MapElement me, List<Integer> dimensions, double[] step, int d_index, double[] current_aa, int period, Returns returns)
        {
            double[] p = me.rps;

            if (d_index == 0)
            {
                    assert(!config.ef.equals("none"));
            }

            if (d_index == dimensions.size())
            {
                    // Don't cache results because we don't have the memory to store a large number of results.
                    SimulateResult results = simulate(current_aa, p, period, config.num_sequences_generate, 0, true, false, returns, 0);
                    if (search_difference(results, me.results) > 0)
                    {
                            me.aa = current_aa;
                            me.results = results;
                    }
                    return;
            }

            int d = dimensions.get(d_index);
            int perturb = 0;
            double[] old_aa = null;
            while (true)
            {
                    double[] try_aa = current_aa;
                    try_aa = inc_dec_aa(current_aa, d, - perturb * step[d], p, period);
                    if (Arrays.equals(try_aa, old_aa))
                            break;
                    old_aa = try_aa;
                    search_all(me, dimensions, step, d_index + 1, try_aa, period, returns);
                    if (d == -1)
                            break;
                    perturb++;
            }
        }

        private boolean search_hill_climb(MapElement me, List<Integer> dimensions, double[] step, double step_size, double[] aa, int period, Returns returns)
        {
                if (me.simulate != null && !me.simulate.isEmpty())
                        me.simulate.add(new SearchResult(null, Double.NaN, "++++++++"));
                MapElement best = me;
                double[] p = me.rps;
                final double accel = 3.0;  // Empirically determined to give good performance.
                boolean improved = false;
                SimulateResult best_results;
                double[] best_aa;
                if (aa == null)
                {
                        SimulateResult results = search_simulate_cache(me, best.aa, p, period, returns);
                        best.results = results;
                        best_aa = best.aa;
                        best_results = results;
                }
                else
                {
                        boolean far = false;
                        for (int di = 0; di < dimensions.size(); di++)
                        {
                                int d = dimensions.get(di);
                                double distance = Math.abs(aa[d] - me.aa[d]);
                                if (distance >= (accel - 1e-12) * step[d]) // Want to ensure probes are at least step[d] appart.
                                {
                                        far = true;
                                        break;
                                }
                        }
                        if (!far)
                                return false;
                        SimulateResult results = search_simulate_cache(me, aa, p, period, returns);
                        double diff = search_difference(results, best.results);
                        if (diff < 0)
                                return false;
                        else if (diff > 0)
                                improved = true;
                        best.aa = aa;
                        best.results = results;
                        best_aa = aa;
                        best_results = results;
                }
                double[] stepper = new double[step.length];
                for (int i = 0; i < stepper.length; i++)
                        stepper[i] = step_size * accel * step[i];
                boolean[] equal_best = new boolean[dimensions.size()];
                boolean looped = false;
                while (true)
                {
                        if (looped && me.simulate != null)
                                me.simulate.add(new SearchResult(null, Double.NaN, "--------"));
                        looped = true;
                        boolean big_step = false;
                        for (int di = 0; di < dimensions.size(); di++)
                        {
                                if (di > 0 && me.simulate != null)
                                        me.simulate.add(new SearchResult(null, Double.NaN, "----"));
                                int d = dimensions.get(di);
                                boolean better = false;
                                double best_perturb = Double.NaN;
                                boolean pos_seen_decend = false;
                                boolean neg_seen_decend = false;
                                for (double perturb : new double[] { 0, - 1 / accel, 1 / accel, - accel, accel })
                                        // Search zero first so that ria/nia will be exactly zero when unwarranted.
                                        // Search smallest perturbs first so can short circuit if pos/neg_seen_decend.
                                        // Need zero first and negative before positive so perturb > 0 test is OK at perturb == 0.
                                {
                                        if (perturb > 0 ? pos_seen_decend : neg_seen_decend)
                                                continue;
                                                // May be better walking since map isn't totally smooth, but instead appears to contain small ripples.
                                                // This may be because we use real world data, not data from some normal distribution.
                                                // This brings in to question our ability to find the global maxima.
                                                // It would seem we are close to doing so before continue skips incorrectly.
                                        double[] try_aa = best.aa;
                                        try_aa = inc_dec_aa(best.aa, d, perturb * stepper[d], p, period);
                                        SimulateResult results = search_simulate_cache(me, try_aa, p, period, returns);
                                        double diff = search_difference(results, best_results);
                                        if (diff > 0)
                                        {
                                                best_aa = try_aa;
                                                best_results = results;
                                                best_perturb = perturb;
                                                better = true;
                                                equal_best = new boolean[dimensions.size()];
                                        }
                                        else if (diff == 0 && !Arrays.equals(try_aa, best_aa))
                                        {
                                                equal_best[di] = true;
                                        }
                                        else if (perturb <= 0 && diff < 0)
                                                // perturb == 0 && diff < 0 can occur if search_hill_climb() is called a second time.
                                        {
                                                neg_seen_decend = true;
                                        }
                                        else if (perturb > 0 && diff < 0)
                                        {
                                                pos_seen_decend = true;
                                        }
                                }
                                if (!better)
                                {
                                        stepper[d] *= 1 / accel; // Refine.
                                }
                                else
                                {
                                        improved = true;
                                        best.aa = best_aa;
                                        best.results = best_results;
                                        if (best_perturb != 0)
                                                stepper[d] *= Math.abs(best_perturb);
                                }
                                // Stop when small step. Works only if no pronounced ridges.
                                if (stepper[d] >= (accel - 1e-12) * step[d])
                                        big_step = true;
                                else
                                        stepper[d] = Math.max(stepper[d], accel * step[d]); // Prevent ever becoming zero or too small.
                                                // The search space might not be totally smooth in which case if stepper ever becomes too small it will
                                                // detect ripples and fail to see the bigger picture. This might be OK now, but won't be if the location
                                                // of the other dimensions changes.
                        }
                        if (!big_step)
                                break;
                }
                return improved;
        }

        private double distance(List<Integer> dimensions, double[] step, double[] aa, double bb[])
        {
                double ssq = 0;
                for (int d : dimensions)
                {
                        double distance = Math.abs(aa[d] - bb[d]) / step[d];
                        ssq += distance * distance;
                }
                return Math.sqrt(ssq);
        }

        private double radius(List<Integer> dimensions, double[] step, double[] aa)
        {
                double ssq = 0;
                for (int d : dimensions)
                {
                        double distance = Math.abs(aa[d]) / step[d];
                        ssq += distance * distance;
                }
                return Math.sqrt(ssq);
        }

        private double[] gradient(MapElement me, double[] aa, List<Integer> dimensions, double[] step, double delta_size, double[] p, int period, Returns returns)
        {
                SimulateResult origin_results = search_simulate_cache(me, aa, p, period, returns);
                double[] gradient = new double[scenario.all_alloc];
                double ssq = 0;
                for (int d : dimensions)
                {
                        double delta = delta_size * step[d];
                        double[] try_aa = aa;
                        boolean reverse;
                        try_aa = inc_dec_aa(aa, d, - delta, p, period);
                        reverse = (try_aa[d] == 0);
                        if (reverse)
                                try_aa = inc_dec_aa(aa, d, delta, p, period);
                        SimulateResult delta_results = search_simulate_cache(me, try_aa, p, period, returns);
                        gradient[d] = search_difference(origin_results, delta_results) / delta;
                        if (reverse)
                                gradient[d] = - gradient[d];
                        ssq += gradient[d] * gradient[d];
                }
                double len = Math.sqrt(ssq);
                boolean flat = (len == 0);
                if (!flat)
                        for (int d : dimensions)
                        {
                                if (gradient[d] == Double.POSITIVE_INFINITY)
                                        gradient[d] = 1;
                                else if (gradient[d] == Double.NEGATIVE_INFINITY)
                                        gradient[d] = -1;
                                else
                                        gradient[d] /= len;
                                gradient[d] *= delta_size * step[d];
                                assert(!Double.isNaN(gradient[d]));
                        }
                return gradient;
        }

        private double[] perturb_aa(double[] aa, double[] perturb, List<Integer> dimensions, double[] p, int period)
        {
                for (int d : dimensions)
                {
                            aa = inc_dec_aa(aa, d, perturb[d], p, period);
                }
                return aa;
        }

        private boolean search_gradient(MapElement me, List<Integer> dimensions, double step[], double step_size, double[] aa, int period, Returns returns)
        {
                if (me.simulate != null && !me.simulate.isEmpty())
                        me.simulate.add(new SearchResult(null, Double.NaN, "++++++++"));
                MapElement best = me;
                double[] p = me.rps;
                boolean improved = false;
                if (aa != null)
                {
                        if (distance(dimensions, step, aa, me.aa) < 1.0)
                                return false;
                        SimulateResult results = search_simulate_cache(me, aa, p, period, returns);
                        double diff = search_difference(results, best.results);
                        if (diff < 0)
                                return false;
                        else if (diff > 0)
                                improved = true;
                        best.aa = aa;
                        best.results = results;
                }
                double stepper = step_size;
                boolean looped = false;
                while (true)
                {
                        if (looped && me.simulate != null)
                                me.simulate.add(new SearchResult(null, Double.NaN, "--------"));
                        looped = true;
                        double[] gradient = gradient(me, best.aa, dimensions, step, stepper, p, period, returns);
                        double[] try_aa = perturb_aa(best.aa, gradient, dimensions, p, period);
                        SimulateResult results = search_simulate_cache(me, try_aa, p, period, returns);
                        boolean better = (search_difference(results, best.results) > 0);
                        if (better)
                        {
                                improved = true;
                                best.aa = try_aa;
                                best.results = results;
                        }
                        if (better)
                        {
                                stepper *= 2;
                        }
                        else
                        {
                                stepper *= 1 / 1.3; // Empirically determined to give good performance.
                                if (stepper < 1)
                                        break;
                        }
                }
                return improved;
        }

        private double[] unit_random(List <Integer> dimensions, double[] step, Random random)
        {
                double[] aa = new double[scenario.all_alloc];
                assert(config.ef.equals("none"));
                double ssq = 0;
                for (int d : dimensions)
                {
                        double val = 2 * random.nextDouble() - 1;
                        aa[d] = val * step[d];
                        ssq += val * val;
                }
                double len = Math.sqrt(ssq);
                assert(len != 0);
                for (int d : dimensions)
                {
                        aa[d] /= len;
                }
                return aa;
        }

        // http://www2.denizyuret.com/pub/aitr1569/node17.html
        private boolean search_memory(MapElement me, List<Integer> dimensions, double step[], double step_size, double[] aa, int period, Returns returns)
        {
                if (me.simulate != null && !me.simulate.isEmpty())
                        me.simulate.add(new SearchResult(null, Double.NaN, "++++++++"));
                MapElement best = me;
                double[] p = me.rps;
                boolean improved = false;
                if (best.results == null)
                        best.results = search_simulate_cache(me, best.aa, p, period, returns);
                if (aa != null)
                {
                        if (distance(dimensions, step, aa, me.aa) < 1.0)
                                return false;
                        SimulateResult results = search_simulate_cache(me, aa, p, period, returns);
                        double diff = search_difference(results, best.results);
                        if (diff < 0)
                                return false;
                        else if (diff > 0)
                                improved = true;
                        best.aa = aa;
                        best.results = results;
                }
                double stepper = step_size;
                Random random = new Random(0);
                double[] u = new double[scenario.all_alloc]; // memory of successful moves
                double[] v = null; // current random step
                double[] grad = null;
                while (stepper >= 1)
                {
                        if (me.simulate != null)
                                me.simulate.add(new SearchResult(null, Double.NaN, "-------- stepper: " + stepper + " best: " + Arrays.toString(best.aa)));
                        SimulateResult prev_results = best.results;
                        boolean better = false;
                        boolean first_try = true;
                        boolean try_gradient = false; // Might be faster but sometimes causes us to pathologically climb to near the top of a ridge and then stop.
                        for (int i = 0; i < config.search_memory_attempts; i++)
                        {
                                if (!first_try || v == null)
                                {
                                        double unit[];
                                        if (try_gradient)
                                        {
                                                if (grad == null)
                                                {
                                                        grad = gradient(me, best.aa, dimensions, step, 1, p, period, returns);
                                                                // Using stepper in place of 1 and no subsequent stepper scaling would be more accurate
                                                                // but would prevent caching when decelerating.
                                                        if (me.simulate != null)
                                                            me.simulate.add(new SearchResult(null, Double.NaN, "---- gradient ---- " + Arrays.toString(grad)));
                                                }
                                                unit = grad;
                                                try_gradient = false;
                                        }
                                        else
                                        {
                                                // Commented out because results in bad metrics at least if try_gradient is false.
                                                // if (stepper / 2 > 1) // Only try random probing if looks like we might be about to finish.
                                                //         break;
                                                unit = unit_random(dimensions, step, random);
                                        }
                                        v = Utils.scalar_product(stepper, unit);
                                }
                                double[] try_aa = perturb_aa(best.aa, v, dimensions, p, period);
                                SimulateResult results = search_simulate_cache(me, try_aa, p, period, returns);
                                double diff = search_difference(results, prev_results);
                                if (diff > 0)
                                {
                                        improved = true;
                                        best.aa = try_aa;
                                        best.results = results;
                                        grad = null;
                                        better = true;
                                        break;
                                }
                                first_try = false;
                        }
                        final double accel = 2;
                        if (!better)
                        {
                                v = Utils.scalar_product(1 / accel, v);
                        }
                        else if (first_try)
                        {
                                u = Utils.vector_sum(u, v);
                                v = Utils.scalar_product(accel, v);
                        }
                        else
                        {
                                if (me.simulate != null)
                                        me.simulate.add(new SearchResult(null, Double.NaN, "----"));
                                double[] try_aa = perturb_aa(best.aa, u, dimensions, p, period);
                                SimulateResult results = search_simulate_cache(me, try_aa, p, period, returns);
                                if (search_difference(results, prev_results) > 0)
                                {
                                        improved = true;
                                        best.aa = try_aa;
                                        best.results = results;
                                        grad = null;
                                        u = Utils.vector_sum(u, v);
                                        v = Utils.scalar_product(accel, u);
                                }
                                else
                                {
                                        u = v;
                                        v = Utils.scalar_product(accel, v);
                                }
                        }
                        stepper = radius(dimensions, step, v);
                }
                return improved;
        }

        private boolean search(MapElement me, List<Integer> dimensions, double[] step, double[] aa, int period, Returns returns)
        {
                if (config.search.equals("all"))
                {
                        search_all(me, dimensions, step, 0, me.aa, period, returns);
                        return false; // No point trying to improve on exhaustive search.
                }
                else if (config.search.equals("hill"))
                {
                        double step_size = 1;
                        boolean improve = search_hill_climb(me, dimensions, step, step_size, aa, period, returns);
                        return improve;
                }
                else if (config.search.equals("gradient"))
                {
                        double step_size = 10;
                        boolean improve = search_gradient(me, dimensions, step, step_size, aa, period, returns);
                        return improve;
                }
                else if (config.search.equals("memory"))
                {
                        double step_size = 1;
                        boolean improve = search_memory(me, dimensions, step, step_size, aa, period, returns);
                        return improve;
                }
                else
                {
                        assert(false);
                        return false;
                }

        }

        private boolean search_hint(MapElement me, double[] aa, int period, Returns returns)
        {
                boolean search_aa = config.aa_strategy.equals("sdp");
                boolean retired = period >= (config.retirement_age - config.start_age) * returns.time_periods;
                boolean annuitize = period >= (config.annuity_age - config.start_age) * returns.time_periods;
                boolean search_consume = scenario.vw_strategy.equals("sdp") && (retired || config.spend_pre_retirement);

                me.aa = me.aa.clone(); // May be shared with older bucket.

                List<Integer> dimensions = new ArrayList<Integer>();
                double[] step = new double[scenario.asset_classes.size()];
                if (!search_aa)
                        ;
                else if (config.ef.equals("none"))
                {
                        int search_aa_dimensions = scenario.normal_assets;
                        if (search_aa_dimensions <= 1)
                                search_aa_dimensions = 0;
                        else if (search_aa_dimensions == 2)
                                search_aa_dimensions = 1;
                        for (int d = 0; d < search_aa_dimensions; d++)
                        {
                                if (!annuitize || config.annuity_classes_supress == null || !config.annuity_classes_supress.contains(scenario.asset_classes.get(d)))
                                {
                                        dimensions.add(d);
                                        step[d] = 1.0 / config.aa_steps;
                                }
                        }
                }
                else
                {
                        dimensions.add(scenario.ef_index);
                        step[scenario.ef_index] = 1.0 / config.aa_steps;
                }
                int ria_loc = dimensions.size();
                if (scenario.ria_index != null)
                {
                        if (annuitize)
                        {
                                dimensions.add(scenario.ria_aa_index);
                                step[scenario.ria_aa_index] = 1.0 / config.annuity_steps;
                        }
                        else
                                me.aa[scenario.ria_aa_index] = 0;
                }
                int nia_loc = dimensions.size();
                if (scenario.nia_index != null)
                {
                        if (annuitize)
                        {
                                dimensions.add(scenario.nia_aa_index);
                                step[scenario.nia_aa_index] = 1.0 / config.annuity_steps;
                        }
                        else
                                me.aa[scenario.nia_aa_index] = 0;
                }
                if (search_consume)
                {
                        dimensions.add(scenario.consume_index); // Contrib/consume.
                        step[scenario.consume_index] = Math.max(Math.abs(me.rps[scenario.tp_index]), config.tp_zero_factor * scenario.consume_max_estimate) / config.spend_steps;
                }

                if (!search_aa)
                        me.aa = generate_aa(config.aa_strategy, config.start_age + period / returns.time_periods, me.rps);
                if (!search_consume)
                {
                    me.aa[scenario.consume_index] = vw_spend(config.start_age + period / returns.time_periods, me.rps);
                }

                if (dimensions.size() == 0)
                {
                        // Force search when not performing any sdp so we have a me.results to allow later code to work.
                        me.results = search_simulate_cache(me, me.aa, me.rps, period, returns);
                        return false;
                }
                else
                        assert(!scenario.vw_strategy.equals("retirement_amount")); // retirement_amount is a run time strategy that does not lend itself to SDP.

                boolean improve = false;
                if ((scenario.ria_index != null || scenario.nia_index != null) && !config.annuity_partial && aa == null)
                {
                        // All annuitization may represent a local maxima preventing non-annuitization local maxima being found, so we handle them separately.
                        // Hints from future ages don't work properly when not annuitized, but not a big deal.
                        if ((scenario.ria_index == null || me.rps[scenario.ria_index] == 0) && (scenario.nia_index == null || me.rps[scenario.nia_index] == 0))
                        {
                                List<Integer> reduced_dimensions = new ArrayList<Integer>(dimensions);
                                double[] original_aa = me.aa.clone();
                                double[] no_annuitize_aa = me.aa.clone();
                                if (scenario.ria_index != null)
                                {
                                        reduced_dimensions.remove(ria_loc);
                                        no_annuitize_aa[scenario.ria_aa_index] = 0;
                                }
                                if (scenario.nia_index != null)
                                {
                                        reduced_dimensions.remove(nia_loc);
                                        no_annuitize_aa[scenario.nia_aa_index] = 0;
                                }
                                me.aa = no_annuitize_aa;
                                search(me, reduced_dimensions, step, null, period, returns);
                                double[] no_annuity_aa = me.aa;
                                SimulateResult no_annuity_results = me.results;
                                me.aa = original_aa;
                                search(me, dimensions, step, null, period, returns);
                                if (search_difference(no_annuity_results, me.results) >= 0)
                                {
                                        me.aa = no_annuity_aa;
                                        me.results = no_annuity_results;
                                }
                                improve = true;
                        }
                        else
                        {
                                improve = search(me, dimensions, step, null, period, returns) || improve;
                        }
                }
                else
                {
                        improve = search(me, dimensions, step, aa, period, returns) || improve;
                }

                return improve;

                // Random restart and nearby restart both run too slowly.
                //
                // double[] p = me.rps;
                // SimulateResult orig_results = me.results;
                // boolean improve = search(me, dimensions, step, aa, period, returns);
                // Random random = new Random(0);
                // double[] best_aa = me.aa;
                // SimulateResult best_results = me.results;
                // int restart = 0;
                // while (improve && restart < 10)
                // {
                //         restart++;
                //      double[] unit = unit_random(dimensions, step, random);
                //      double[] perturb = Utils.scalar_product(10, unit);
                //         double[] try_aa = perturb_aa(best_aa, perturb, dimensions, p, period);
                //      me.aa = try_aa;
                //      me.results = null;
                //      search(me, dimensions, step, null, period, returns);
                //      if (distance(dimensions, step, me.aa, best_aa) >= 1 && search_difference(me.results, best_results) > 0)
                //      {
                //              restart = 0;
                //              best_aa = me.aa;
                //              best_results = me.results;
                //      }
                // }
                // me.aa = best_aa;
                // me.results = best_results;
                // return orig_results == null || search_difference(me.results, orig_results) > 0;
        }

        // Generate asset allocation.
        Object next_check_lock = new Object();
        int next_check; // Can't declare locally as modified by thread.
        public AAMapGenerate(final Scenario scenario, final Returns returns, AAMap aamap1, AAMap aamap2, VitalStats generate_stats, VitalStats validate_stats, Utility uc_time, Utility uc_risk, double guaranteed_income) throws ExecutionException
        {
                super(scenario, aamap1, aamap2, generate_stats, validate_stats, uc_time, uc_risk, guaranteed_income);

                pre_compute_vw(returns);

                map = new MapPeriod[(int) (scenario.ss.max_years * returns.time_periods)];

                List<Callable<Integer>> tasks = new ArrayList<Callable<Integer>>();

                final int period_0 = 0;
                final int period_1 = (int) (scenario.ss.max_years * returns.time_periods);
                for (int period = period_1 - 1; period >= period_0; period--)
                {
                        if (config.trace)
                                System.out.print("period " + period);
                        long start = System.currentTimeMillis();
                        final MapPeriod mp = new MapPeriod(this, period);
                        map[period] = mp;
                        final int fperiod = period;

                        List<SearchBucket> check_list = new ArrayList<SearchBucket>();
                        MapPeriodIterator<MapElement> mpitr = mp.iterator();
                        while (mpitr.hasNext())
                        {
                                int[] bucket = mpitr.nextIndex().clone();
                                mpitr.next();
                                MapElement me = new_bucket(bucket, period);
                                mp.set(bucket, me);
                                check_list.add(new SearchBucket(bucket, null));
                        }

                        while (!check_list.isEmpty())
                        {
                                //System.out.print(" " + check_list.size());
                                Collections.sort(check_list);
                                next_check = 0;
                                List<SearchBucket> new_check_list = new ArrayList<SearchBucket>();
                                final List<SearchBucket> fcheck_list = check_list;
                                final List<SearchBucket> fnew_check_list = new_check_list;
                                for (int t = 0; t < config.tasks_generate; t++)
                                {
                                        tasks.add(new Callable<Integer>()
                                        {
                                                public Integer call()
                                                {
                                                        Thread.currentThread().setPriority((Thread.MIN_PRIORITY + Thread.NORM_PRIORITY) / 2);
                                                        // Avoid random number generator contention by giving each thread it's own generator.
                                                        // Not deterministic. But only used by Cholesky.
                                                        Returns local_returns = returns.clone();
                                                        while (true)
                                                        {
                                                                int start;
                                                                int end;
                                                                synchronized (next_check_lock)
                                                                {
                                                                        if (next_check == fcheck_list.size())
                                                                                break;
                                                                        start = next_check;
                                                                        next_check++;
                                                                        while (next_check < fcheck_list.size() &&
                                                                               (Arrays.equals(fcheck_list.get(next_check).bucket, fcheck_list.get(next_check - 1).bucket)
                                                                                 || ((next_check - start) * config.bucket_groups_per_task * config.tasks_generate) < mp.total_length))
                                                                        {
                                                                                // We process all checks for a given bucket in order to ensure runs are deterministic.
                                                                                next_check++;
                                                                        }
                                                                        end = next_check;
                                                                }
                                                                MapElement prior_sibling = null;
                                                                MapElement sibling = null;
                                                                for (int elem = start; elem < end; elem++)
                                                                {
                                                                        SearchBucket check = fcheck_list.get(elem);
                                                                        MapElement me = mp.get(check.bucket);
                                                                        double[] aa = check.aa;
                                                                        if (aa == null)
                                                                                new_aa(check.bucket, me, fperiod, sibling, prior_sibling);
                                                                        else
                                                                                aa = make_safe_aa(aa, me.rps, fperiod);
                                                                        boolean improve = search_hint(me, aa, fperiod, local_returns);
                                                                        // Perhaps we have only searched where were the metric was -Inf. If so try somewhere safe.
                                                                        if ((aa == null) && !improve)
                                                                        {
                                                                                aa = make_safe_aa(scenario.guaranteed_safe_aa(), me.rps, fperiod);
                                                                                aa[scenario.consume_index] = 0;
                                                                                improve = search_hint(me, aa, fperiod, local_returns);
                                                                        }
                                                                        // Get a 50% speedup due to early deletion of cache. Otherwise cache too big for CPU cache.
                                                                        me.cache = null;
                                                                        if (improve && config.search_neighbour)
                                                                        {
                                                                                for (int d = 0; d < check.bucket.length; d++)
                                                                                {
                                                                                        for (int dir : new int[] {-1, 1})
                                                                                        {
                                                                                                int tryval = check.bucket[d] + dir;
                                                                                                if (mp.bottom[d] <= tryval && tryval < mp.bottom[d] + mp.length[d])
                                                                                                {
                                                                                                        int[] neighbour = check.bucket.clone();
                                                                                                        neighbour[d] = tryval;
                                                                                                        SearchBucket new_check = new SearchBucket(neighbour, me.aa);
                                                                                                        synchronized (fnew_check_list)
                                                                                                        {
                                                                                                                fnew_check_list.add(new_check);
                                                                                                        }
                                                                                                }
                                                                                        }
                                                                                }
                                                                        }
                                                                        prior_sibling = sibling;
                                                                        sibling = me;
                                                                }
                                                        }
                                                        return null;
                                                }
                                        });
                                }
                                invoke_all(tasks);
                                tasks.clear();

                                check_list = new_check_list;
                        }

                        for (MapElement me : map[period])
                        {
                                if (config.stock_bias != 0)
                                {
                                        assert(config.min_safe_le == 0);
                                        me.aa = inc_dec_aa(me.aa, scenario.asset_classes.indexOf("stocks"), config.stock_bias, me.rps, 0);
                                }

                                if (me.results.metrics.get(scenario.success_mode_enum) == Double.NEGATIVE_INFINITY)
                                {
                                        // Make map look consistent when values to use are indeterminite.
                                        // Also ensures period - 1 has reasonable hints to start from.
                                        double[] gs = scenario.guaranteed_safe_aa();
                                        // Make sure aa is valid if min_safe is in effect.
                                        gs = make_safe_aa(gs, me.rps, period);
                                        for (int i = 0; i < scenario.normal_assets; i++)
                                                me.aa[i] = gs[i];
                                        me.aa[scenario.consume_index] = 0;
                                        if (!config.ef.equals("none"))
                                                me.aa[scenario.ef_index] = gs[scenario.ef_index];
                                        me.results = search_simulate_cache(me, me.aa, me.rps, period, returns);
                                }

                                me.cache = null;
                                me.spend = me.results.spend;
                                me.first_payout = me.results.first_payout;
                                me.metric_sm = me.results.metrics.get(scenario.success_mode_enum);
                                me.metric_human_capital = me.results.metrics.get(MetricsEnum.HUMAN_CAPITAL);
                        }

                        map[period].interpolate(true);

                        if (period + 1 < map.length)
                        {
                                for (MapElement me : map[period + 1])
                                {
                                        if (config.conserve_ram || config.skip_dump_log ||
                                                (config.start_age + (period + 1) / config.generate_time_periods < config.dump_min_age) ||
                                                (config.start_age + (period + 1) / config.generate_time_periods > config.dump_max_age) ||
                                                (scenario.tp_index != null && me.rps[scenario.tp_index] > config.dump_max_tp) ||
                                                (scenario.ria_index != null && me.rps[scenario.ria_index] > config.dump_max_ria) ||
                                                (scenario.nia_index != null && me.rps[scenario.nia_index] > config.dump_max_nia))
                                        {
                                                // Now that ef_index no longer needed, delete it to save RAM.
                                                double[] aa = new double[scenario.all_alloc];
                                                System.arraycopy(me.aa, 0, aa, 0, aa.length);
                                                me.aa = aa;
                                                me.results = null;
                                                me.simulate = null;
                                        }
                                }
                        }

                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        if (config.trace)
                                System.out.printf(" - %.3fs\n", elapsed);
                }

                if (period_0 < period_1)
                {
                        for (MapElement me : map[period_0])
                        {
                                if ((config.start_age + period_0 / config.generate_time_periods < config.dump_min_age) ||
                                        (config.start_age + period_0 / config.generate_time_periods > config.dump_max_age) ||
                                        (scenario.tp_index != null && me.rps[scenario.tp_index] > config.dump_max_tp) ||
                                        (scenario.ria_index != null && me.rps[scenario.ria_index] > config.dump_max_ria) ||
                                        (scenario.nia_index != null && me.rps[scenario.nia_index] > config.dump_max_nia))
                                {
                                        me.results = null;
                                        me.simulate = null;
                                }
                        }
                }
        }

        private double vw_spend(double age, double[] p)
        {
                if (age < config.retirement_age)
                        return 0;

                double income = guaranteed_income;
                if (scenario.ria_index != null)
                        income += p[scenario.ria_index];
                if (scenario.nia_index != null)
                        income += p[scenario.nia_index];
                double wealth = p[scenario.tp_index] + income;
                double inc_pct = 0;
                if (wealth > 0)
                        inc_pct = income / wealth;

                int period = (int) Math.round((age - config.start_age) * config.generate_time_periods);
                double le;
                if (scenario.vw_strategy.equals("rmd"))
                {
                        if (Math.round(age) < scenario.hist.rmd_le.length)
                                le = scenario.hist.rmd_le[(int) Math.round(age)];
                        else
                                le = scenario.hist.rmd_le[scenario.hist.rmd_le.length - 1];
                }
                else
                {
                        VitalStats generate_stats = scenario.ss.generate_stats;
                        if (scenario.vw_strategy.equals("discounted_life"))
                        {
                                assert(generate_stats.vital_stats1 == null);
                                le = generate_stats.sum_avg_alive[period] / generate_stats.alive[period];
                        }
                        else if (generate_stats.vital_stats1 == null)
                                le = generate_stats.raw_sum_avg_alive[period] / generate_stats.raw_alive[period];
                        else
                                le = config.couple_weight1 * generate_stats.vital_stats1.raw_sum_avg_alive[period] / generate_stats.vital_stats1.raw_alive[period] + (1 - config.couple_weight1) * generate_stats.vital_stats2.raw_sum_avg_alive[period] / generate_stats.vital_stats2.raw_alive[period];
                        if (Double.isNaN(le))
                            le = 0.0;
                        le /= scenario.ss.generate_stats.time_periods;
                }
                le = Math.max(le, config.vw_le_min);
                double life_pct = Math.min(1 / le, 1);

                double fixed_le = config.vw_years - (age - config.retirement_age);

                double pct = 0;
                if (scenario.vw_strategy.equals("merton"))
                {
                        assert(config.generate_time_periods == 1);
                        if (fixed_le <= 0)
                        {
                                pct = 1;
                        }
                        else if (config.vw_merton_nu == 0)
                        {
                                pct = 1 / fixed_le;
                        }
                        else
                        {
                                pct = config.vw_merton_nu / (1 - Math.exp(- config.vw_merton_nu * fixed_le));
                        }
                }
                else if (scenario.vw_strategy.equals("vpw"))
                {
                        assert(config.generate_time_periods == 1);
                        if (fixed_le <= 0)
                                pct = 1;
                        else
                        {
                                if (config.vw_rate == 0)
                                        pct = 1 / fixed_le;
                                else
                                        pct = config.vw_rate * Math.pow(1 + config.vw_rate, fixed_le - 1) / (Math.pow(1 + config.vw_rate, fixed_le) - 1);
                        }
                }
                else if (scenario.vw_strategy.equals("flra") || scenario.vw_strategy.equals("slra"))
                {
                        pct = vw_slra[period];
                }
                else
                        pct = scenario.vw_percent;
                assert(pct >= 0);
                pct = Math.min(pct, 1);

                if (scenario.vw_strategy.equals("amount") || scenario.vw_strategy.equals("retirement_amount"))
                        return 0;
                else if (scenario.vw_strategy.equals("percentage") || scenario.vw_strategy.equals("merton") || scenario.vw_strategy.equals("vpw") || scenario.vw_strategy.equals("flra") || scenario.vw_strategy.equals("slra"))
                        return Math.min(pct * (1 - inc_pct) + inc_pct, 1 - 1e-15) * wealth;
                else if (scenario.vw_strategy.equals("rmd") || scenario.vw_strategy.equals("life") || scenario.vw_strategy.equals("discounted_life"))
                        return Math.min(life_pct * (1 - inc_pct) + inc_pct, 1 - 1e-15) * wealth;
                else
                        assert(false);
                return Double.NaN;
        }

        double avg_utility(double consume, double future_ce, double current_alive, double future_alive, Returns returns)
        {
                if (current_alive == 0)
                        return consume;
                double u = current_alive * uc_time.utility(consume);
                if (future_alive > 0)
                    u += future_alive * uc_time.utility((1 - consume + config.vw_rate / returns.time_periods) * future_ce);
                return u / (current_alive + future_alive);
        }

        double vw_slra[];

        void pre_compute_vw(Returns returns)
        {
                VitalStats generate_stats = scenario.ss.generate_stats;
                vw_slra = new double[(int) (scenario.ss.max_years * returns.time_periods)];

                double future_ce = 1;
                for (int period = vw_slra.length - 1; period >= 0; period--)
                {
                        double current_alive;
                        double future_alive;
                        if (scenario.vw_strategy.equals("flra"))
                        {
                                int le = (int) Math.round(config.vw_years * returns.time_periods) - period;
                                current_alive = ((le > 0) ? 1 : 0);
                                future_alive = Math.max(le - 1, 0);
                        }
                        else
                        {
                                current_alive = generate_stats.alive[period];
                                future_alive = generate_stats.sum_avg_alive[period + 1];
                        }
                        // Golden segment search on consume fraction for maximum averaged utility.
                        double a = 0;
                        double b = 1;
                        double gr = (Math.sqrt(5.0) - 1) / 2;
                        for (int i = 0; i < 50; i++)
                        {
                                double c = b - gr * (b - a);
                                double d = a + gr * (b - a);
                                if (avg_utility(c, future_ce, current_alive, future_alive, returns) > avg_utility(d, future_ce, current_alive, future_alive, returns))
                                        b = d;
                                else
                                        a = c;
                        }
                        double consume = (a + b) / 2;
                        vw_slra[period] = consume;
                        if (current_alive > 0)
                            future_ce = uc_time.inverse_utility(avg_utility(consume, future_ce, current_alive, future_alive, returns));
                        else
                                future_ce = 1;
                }
        }
}
