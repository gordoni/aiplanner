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

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.lang.ProcessBuilder;
import java.text.DecimalFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

public class Scenario
{
        public ScenarioSet ss;
        public Config config;
        public Scale[] scale;
        public List<String> asset_classes;
        public List<String> asset_class_names;
        public Double fixed_stocks;
        public Double vw_percent;
        public String vw_strategy;
        public Utility utility_consume;
        public Utility utility_consume_time;
        public Utility utility_inherit;
        public List<double[]> aa_ef;
        protected HistReturns hist;

        public double[] start_p;
        public Integer tp_index;
        public Integer ria_index;
        public Integer nia_index;

        public double tp_max_estimate;
        public double consume_max_estimate;
        public double retirement_number_max_estimate;

        public int normal_assets;
        public int stochastic_classes;
        public int ria_aa_index;
        public int nia_aa_index;
        public int spend_fract_index;
        public int all_alloc;
        public int cpi_index;
        public int ef_index;

        public double[] dividend_yield;
        public List<double[]> at_returns;

        public int generate_bottom_bucket;      // Generate data all the way down to the floor.
        public int generate_top_bucket; // Generate data all the way up to the ceiling.
        public int validate_bottom_bucket;      // Report data all the way down to the validate floor.
        public int validate_top_bucket; // Report data all the way up to the validate ceiling.

        public MetricsEnum success_mode_enum;

        public boolean do_tax;
        private boolean do_generate;
        private boolean do_target;
        private Returns returns_generate = null;
        private Returns returns_target = null;
        private Returns returns_validate = null;

        private static DecimalFormat f8 = new DecimalFormat("0.000E00");
        private static DecimalFormat f1f = new DecimalFormat("0.0");
        private static DecimalFormat f2f = new DecimalFormat("0.00");
        private static DecimalFormat f3f = new DecimalFormat("0.000");
        private static DecimalFormat f4f = new DecimalFormat("0.0000");
        private static DecimalFormat f5f = new DecimalFormat("0.00000");
        private static DecimalFormat f6f = new DecimalFormat("0.000000");
        private static DecimalFormat f7f = new DecimalFormat("0.0000000");

        public double[] pToFractionalBucket(double[] p, double[] use_bucket)
        {
                if (use_bucket == null)
                        use_bucket = new double[scale.length];
                for (int i = 0; i < scale.length; i++)
                        use_bucket[i] = scale[i].pf_to_fractional_bucket(p[i]);

                return use_bucket;
        }

        public int[] pToBucket(double[] p, String dir)
        {
                int[] bucket = new int[scale.length];
                for (int i = 0; i < scale.length; i++)
                    bucket[i] = scale[i].pf_to_bucket(p[i], dir);

                return bucket;
        }

        public double[] bucketToP(int[] bucket)
        {
                double[] p = new double[scale.length];
                for (int i = 0; i < scale.length; i++)
                        p[i] = scale[i].bucket_to_pf(bucket[i]);

                return p;
        }

        public double[] guaranteed_safe_aa()
        {
                double[] safe = new double[asset_classes.size()]; // Create new object since at least AAMapGenerate mutates the result.
                for (int i = 0; i < safe.length; i++)
                {
                        if (config.ef.equals("none"))
                                if (asset_classes.get(i).equals(config.safe_aa))
                                        safe[i] = 1.0;
                                else
                                        safe[i] = 0.0;
                        else
                                safe[i] = aa_ef.get(0)[i];
                }
                return safe;
        }

        public double[] guaranteed_fail_aa()
        {
                double[] fail = new double[asset_classes.size()]; // Create new object since at least AAMapGenerate mutates the result.
                for (int i = 0; i < fail.length; i++)
                {
                        if (i == spend_fract_index)
                                fail[i] = 1;
                        else if (config.ef.equals("none"))
                        {
                                if (asset_classes.get(i).equals(config.fail_aa))
                                        fail[i] = 1.0 + config.max_borrow;
                                else if (asset_classes.get(i).equals(config.borrow_aa))
                                        fail[i] = - config.max_borrow;
                                else
                                        fail[i] = 0.0;
                        }
                        else
                                fail[i] = aa_ef.get(aa_ef.size() - 1)[i];
                }
                return fail;
        }

        public double[] inc_dec_aa_raw(double[] aa, int a, double inc, double[] p, int period)
        {
                double[] new_aa = aa.clone();
                double delta = inc;
                double alloc = new_aa[a];
                double min = (asset_classes.get(a).equals(config.borrow_aa) ? - config.max_borrow : 0.0);
                double max = (asset_classes.get(a).equals(config.borrow_only_aa) ? 0.0 : 1.0 + config.max_borrow);
                delta = Math.min(delta, max - alloc);
                delta = Math.max(delta, min - alloc);
                for (int i = 0; i < normal_assets; i++)
                        if (i == a)
                                new_aa[i] += delta;
                        else
                                // Scale back proportionally.
                                if (1 - alloc < 1e-12)
                                        new_aa[i] = - delta / (normal_assets - 1);
                                else
                                        new_aa[i] *= 1 - delta / (1 - alloc);
                if (config.min_safe != 0 || config.min_safe_le != 0)
                {
                        // Not entirely satisfying to fully or partially decrement asset class when it was requested that it be incremented,
                        // but this is the simplest approach and it shouldn't affect the underlying asset allocation machinery.
                        int a_safe = asset_classes.indexOf(config.safe_aa);
                        double alloc_safe = new_aa[a_safe];
                        double have_safe = 0;
                        if (ria_index != null)
                                have_safe += p[ria_index] * ss.generate_annuity_stats.real_annuity_price[period];
                        if (nia_index != null)
                                have_safe += p[nia_index] * ss.generate_annuity_stats.nominal_annuity_price[period];
                        double min_safe_aa;
                        if (p[tp_index] == 0)
                                min_safe_aa = 1;
                        else
                        {
                                double min_safe_le = config.min_safe_le * (ss.generate_stats.raw_sum_avg_alive[period] / ss.generate_stats.raw_alive[period]);
                                min_safe_aa = (min_safe_le - have_safe) / p[tp_index];
                                min_safe_aa = Math.max(min_safe_aa, config.min_safe);
                                min_safe_aa = Math.max(0, min_safe_aa);
                                min_safe_aa = Math.min(1, min_safe_aa);
                        }
                        double delta_safe = Math.max(0, min_safe_aa - alloc_safe);
                        for (int i = 0; i < normal_assets; i++)
                                if (i == a_safe)
                                        new_aa[i] += delta_safe;
                                else
                                        if (1 - alloc_safe < 1e-12)
                                                new_aa[i] = - delta_safe / (normal_assets - 1);
                                        else
                                                new_aa[i] *= 1 - delta_safe / (1 - alloc_safe);
                }
                // Keep summed to one as exactly as possible.
                double sum = 0;
                for (int i = 0; i < normal_assets; i++)
                {
                        assert(new_aa[i] > -1e12);
                        if (new_aa[i] <= 0)
                                new_aa[i] = 0;
                        sum += new_aa[i];
                }
                for (int i = 0; i < normal_assets; i++)
                        new_aa[i] /= sum;
                return new_aa;
        }

        private void dump_mvo_params(String s) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-" + s + "-mvo-params.csv"));
                out.println("ef_steps,risk_tolerance");
                out.println(config.aa_steps + "," + config.risk_tolerance);
                out.close();
        }

        private void asset_class_header(PrintWriter out)
        {
                for (int a = 0; a < normal_assets; a++)
                {
                        if (a > 0)
                                out.print(",");
                        out.print(config.asset_class_names == null ? asset_classes.get(a) : config.asset_class_names.get(a));
                }
                out.println();
        }

        private void dump_mvo_returns(List<double[]> returns, String s) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-" + s + "-mvo-returns.csv"));
                asset_class_header(out);
                for (int i = 0; i < returns.size(); i++)
                {
                        double rets[] = returns.get(i);
                        for (int a = 0; a < normal_assets; a++)
                        {
                                if (a > 0)
                                        out.print(",");
                                out.print(rets[a]);
                        }
                        out.println();
                }
                out.close();
        }

        private void dump_mvo_bounds(String s) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-" + s + "-mvo-bounds.csv"));
                asset_class_header(out);
                for (int a = 0; a < normal_assets; a++)
                {
                        if (a > 0)
                                out.print(",");
                        out.print(asset_classes.get(a).equals(config.borrow_aa) ? - config.max_borrow : 0);
                }
                out.println();
                for (int a = 0; a < normal_assets; a++)
                {
                        if (a > 0)
                                out.print(",");
                        out.print(asset_classes.get(a).equals(config.borrow_only_aa) ? 0 : config.max_borrow + 1);
                }
                out.println();
                out.close();
        }

        private void load_mvo_ef(String s) throws IOException
        {
                aa_ef = new ArrayList<double[]>();

                BufferedReader in = new BufferedReader(new FileReader(new File(ss.cwd + "/" + config.prefix + "-" + s + "-mvo-ef.csv")));
                String line = in.readLine();
                int index = 0;
                while ((line = in.readLine()) != null)
                {
                        String[] fields = line.split(",", -1);
                        double aa[] = new double[asset_classes.size()];
                        for (int i = 0; i < normal_assets; i++)
                        {
                                double alloc = Double.parseDouble(fields[2 + i]);
                                if (alloc <= 0)
                                {
                                        // Negative aa not supported by tax modules.
                                        if (alloc > -1e-6)
                                                alloc = 0;
                                        else
                                                assert(false);
                                }
                                aa[i] = alloc;
                        }
                        aa[ef_index] = index;
                        aa_ef.add(aa);
                        index++;
                }

                assert(aa_ef.size() == config.aa_steps + 1);
                in.close();
        }

        private void mvo(List<double[]> returns, String s) throws IOException, InterruptedException
        {
                dump_mvo_params(s);
                dump_mvo_returns(returns, s);
                dump_mvo_bounds(s);

                ss.subprocess("mvo.R", config.prefix + "-" + s);

                load_mvo_ef(s);
        }

        public double metric_normalize(MetricsEnum metric, double metric_sm, double age)
        {
                metric_sm /= ss.generate_stats.metric_divisor(metric, age);
                if (Arrays.asList(MetricsEnum.TW, MetricsEnum.NTW).contains(metric))
                        return metric_sm;
                if (config.utility_epstein_zin)
                        return utility_consume.inverse_utility(metric_sm);
                if (Arrays.asList(MetricsEnum.CONSUME, MetricsEnum.COMBINED).contains(metric))
                        return utility_consume_time.inverse_utility(metric_sm);
                if (metric == MetricsEnum.INHERIT)
                        return utility_inherit.inverse_utility(metric_sm);
                return metric_sm;
        }

        public double dump_utility(Utility utility, String name, double max, double c_start) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-utility-" + name + ".csv"));

                double ara_max = Double.NEGATIVE_INFINITY;
                for (int i = 0; i <= 1000; i++)
                {
                        double c = i * max / 1000;
                        out.print(f6f.format(c) + "," + utility.utility(c) + "," + utility.slope(c) + "," + utility.slope2(c) + "," + utility.inverse_utility(utility.utility(c)) + "," + utility.inverse_slope(utility.slope(c)) + "\n");
                        double ara = - utility.slope2(c) / utility.slope(c);
                        if (c >= c_start && ara > ara_max)
                                ara_max = ara;
                }
                out.close();

                return ara_max;
        }

        private String stringify_aa(double[] aa)
        {
                return stringify_aa(aa, false);
        }

        private String stringify_aa(double[] aa, boolean high_precision)
        {
                if (aa == null)
                {
                        StringBuilder sb = new StringBuilder();
                        for (int i = 0; i < normal_assets - 1; i++)
                                sb.append(",");
                        return sb.toString();
                }

                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < normal_assets; i++)
                {
                        if (i > 0)
                                sb.append(",");
                        if (high_precision)
                                sb.append(f4f.format(aa[i]));
                        else
                                sb.append(f3f.format(aa[i]));
                }
                return sb.toString();
        }

        // // Dump success probability and asset allocation as a function of RPS for
        // // the initial age.
        // public void dump_rps_initial(AAMap map, Metrics[][] success_lines, String metric) throws IOException
        // {
        //      PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-rps_initial-" + metric + ".csv"));
        //      MapElement[] map_period = map.map[0];
        //      for (int bucket = scenario.validate_bottom_bucket; bucket < scenario.validate_top_bucket + 1; bucket++)
        //      {
        //              MapElement fpb = map_period[bucket - scenario.validate_bottom_bucket];
        //              double p = scale.bucket_to_pf(bucket);
        //              if (!(0.0 <= p && p <= config.pf_validate))
        //                      continue;
        //              double goal = success_lines[0][(int) Math.floor(p / config.success_lines_scale_size)].get(Metrics.to_enum(metric));
        //              String aa = stringify_aa(fpb.aa);
        //              out.print(f2f.format(p));
        //              out.print(",");
        //              out.print(f5f.format(goal));
        //              out.print(",");
        //              out.print(aa);
        //              out.print("\n");
        //      }
        //      out.close();
        // }

        private double expected_return(double[] aa, Returns returns)
        {
                double r = 0.0;
                for (int i = 0; i < normal_assets; i++)
                        r += aa[i] * returns.am[i];
                return r;
        }

        private double expected_standard_deviation(double[] aa, Returns returns)
        {
                double v = 0.0;
                for (int i = 0; i < aa.length - (config.ef.equals("none") ? 0 : 1); i++)
                        for (int j = 0; j < normal_assets; j++)
                                v +=  aa[i] * aa[j] * returns.sd[i] * returns.sd[j] * returns.corr[i][j];
                return Math.sqrt(v);
        }

        // Gnuplot doesn't support heatmaps with an exponential scale, so we have to fixed-grid the data.
        private void dump_aa_linear_slice(AAMap map, Returns returns, double[] slice, String slice_suffix, double tp_max) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-linear" + slice_suffix + ".csv"));

                for (int i = 0; i < map.map.length; i++)
                {
                        double age_period = i + config.start_age * config.generate_time_periods;
                        for (int step = 0; step < config.gnuplot_steps + 1; step++)
                        {
                                double age = age_period / config.generate_time_periods;
                                double curr_pf = (config.gnuplot_steps - step) * tp_max / config.gnuplot_steps;
                                double[] p = slice.clone();
                                p[tp_index] = curr_pf;
                                MapElement fpb = map.lookup_interpolate(p, i);
                                double metric_normalized = metric_normalize(success_mode_enum, fpb.metric_sm, age);
                                double[] aa = fpb.aa;
                                String aa_str = stringify_aa(aa);
                                double annuitizable = fpb.spend - fpb.consume;
                                out.print(f2f.format(age));
                                out.print("," + f2f.format(curr_pf));
                                out.print("," + f2f.format(metric_normalized));
                                out.print("," + ((returns == null) ? "" : f4f.format(expected_return(aa, returns))));
                                out.print("," + ((returns == null) ? "" : f4f.format(expected_standard_deviation(aa, returns))));
                                // Annuitization may be greater than 100% because first_payout may contribute to consume.
                                out.print("," + f3f.format(annuitizable > 0 ? fpb.ria_purchase(this) / annuitizable : 0));
                                out.print("," + f2f.format(fpb.consume));
                                out.print("," + f3f.format(annuitizable > 0 ? fpb.nia_purchase(this) / annuitizable : 0));
                                out.print("," + aa_str);
                                out.print("\n");
                        }
                        out.print("\n");
                }
                out.close();
        }

        private void dump_aa_linear(AAMap map, Returns returns, double tp_max) throws IOException
        {
            dump_aa_linear_slice(map, returns, new double[start_p.length], "", tp_max);
            // dump_aa_linear_slice(map, returns, new double[]{0, 10000}, "10000");
        }

        private Double get_path_value(List<PathElement> path, int i, String what, boolean change)
        {
                if (change)
                {
                        if (i > 0)
                        {
                                Double prev_value = get_path_value(path, i - 1, what, false);
                                Double curr_value = get_path_value(path, i, what, false);
                                if (curr_value == null)
                                        return null;
                                else if (prev_value == 0 && curr_value == 0)
                                        return 0.0;
                                else
                                        return curr_value / prev_value - 1;
                        }
                        else
                                return 0.0;
                }
                else
                {
                        if (i >= path.size())
                                return null;
                        PathElement elem = path.get(i);
                        if (what.equals("p"))
                                return elem.p;
                        else if (what.equals("floor"))
                                return config.utility_join ? Math.min(elem.consume_annual, config.utility_join_required) : elem.consume_annual;
                        else if (what.equals("upside"))
                                return config.utility_join ? Math.max(elem.consume_annual - config.utility_join_required, 0) : 0;
                        else if (what.equals("consume"))
                                return elem.consume_annual;
                        else if (what.equals("inherit"))
                                return elem.p;
                        else
                                return elem.aa[asset_classes.indexOf(what)];
                }
        }

    private double[] distribution_bucketize(List<List<PathElement>> paths, int start, String what, boolean change, double min, double max, Double count_submin, Double count_supmax, double[] counts)
        {
                for (int pi = 0; pi < config.max_distrib_paths; pi++)
                {
                        List<PathElement> path = paths.get(pi);
                        int period = 0;
                        for (int i = start; i < path.size(); i++)
                        {
                                double value = get_path_value(path, i, what, change);
                                double weight;
                                if (what.equals("inherit"))
                                        weight = ss.validate_stats.dying[period];
                                        // XXX Fails for couple_unit=false. Both "inherit" and couple_unit=false not currently used in production.
                                else
                                        weight = path.get(i).weight;
                                int bucket = (int) ((value - min) / (max - min) * config.distribution_steps);
                                if (bucket < 0)
                                        count_submin += weight;
                                else if (0 <= bucket && bucket < counts.length)
                                        counts[bucket] += weight;
                                else
                                        count_supmax += weight;
                                period++;
                        }
               }

                return counts;
        }

        private void dump_distribution(List<List<PathElement>> paths, String what, boolean change, boolean retire_only) throws IOException
        {
                double min = Double.POSITIVE_INFINITY;
                double max = Double.NEGATIVE_INFINITY;
                int start = (int) Math.round((config.retirement_age - config.start_age) * config.validate_time_periods);
                if (!retire_only || start < 1)
                        start = 1; // Strategically ignore the first sample. Its behavior is fixed causing it to spike the results.
                for (int pi = 0; pi < config.max_distrib_paths; pi++)
                {
                        List<PathElement> path = paths.get(pi);
                        for (int i = start; i < path.size(); i++)
                        {
                                double value = get_path_value(path, i, what, change);
                                if (Double.isInfinite(value))
                                        continue; // consume zero then non-zero.
                                if (value < min)
                                        min = value;
                                if (value > max)
                                        max = value;
                        }
                }
                // Guard buckets that are zero so plots look nice.
                double bucket_size = (max - min) / config.distribution_steps;
                min -= bucket_size;
                max += bucket_size;
                if (bucket_size == 0)
                        max += 1; // Prevent multiple buckets at same location.
                if (!change)
                        min = 0;

                Double count_submin = 0.0;
                Double count_supmax = 0.0;
                double[] counts = null;

                // Some distributions have very long right tails. Zoom in so we can see the important part.
                int bucket;
                for (int i = 0; i < 10; i++)
                {
                        count_submin = 0.0;
                        count_supmax = 0.0;
                        counts = new double[config.distribution_steps + 1];
                        distribution_bucketize(paths, start, what, change, min, max, count_submin, count_supmax, counts);
                        double max_count = 0;
                        for (bucket = 0; bucket < counts.length; bucket++)
                                if (counts[bucket] > max_count)
                                        max_count = counts[bucket];
                        for (bucket = 0; bucket < counts.length; bucket++)
                                if (counts[bucket] >= config.distribution_significant * max_count)
                                        break;
                        bucket_size = (max - min) / config.distribution_steps;
                        boolean rescale = false;
                        double old_min = min;
                        if (change && bucket > 1)
                        {
                                rescale = true;
                                min = old_min + (bucket - 1) * bucket_size;
                        }
                        for (bucket = counts.length - 1; bucket > 0; bucket--)
                                if (counts[bucket] >= config.distribution_significant * max_count)
                                        break;
                        if (bucket < counts.length - 3)
                        {
                                rescale = true;
                                max = old_min + (bucket + 2) * bucket_size;
                        }
                        if (!rescale)
                                break;
                }

                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-distrib-" + (change ? "change-" : "") + what + ".csv"));

                double counts_sum = count_submin + Utils.sum(counts) + count_supmax;
                double cdf = count_submin;
                for (bucket = 0; bucket < counts.length; bucket++)
                {
                        cdf += counts[bucket];
                        out.println((min + (bucket + 0.5) * (max - min) / config.distribution_steps) + "," + counts[bucket] + "," + cdf / counts_sum);
                }
                out.close();
        }

        private void dump_distributions(List<List<PathElement>> paths) throws IOException
        {
                dump_distribution(paths, "p", false, false);
                dump_distribution(paths, "floor", false, true);
                dump_distribution(paths, "upside", false, true);
                dump_distribution(paths, "consume", false, true);
                dump_distribution(paths, "inherit", false, false);

                dump_distribution(paths, "p", true, false);
                dump_distribution(paths, "floor", true, true);
                dump_distribution(paths, "upside", true, true);
                dump_distribution(paths, "consume", true, true);
        }

        private double dump_pct_path(List<List<PathElement>> paths, String what, boolean change) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-pct-" + (change ? "change-" : "") + what + ".csv"));

                double max_pctl = Double.NEGATIVE_INFINITY;
                double age_period = config.validate_age * config.generate_time_periods;
                for (int i = 0; ; i++)
                {
                        int values = 0;
                        double[] vals = new double[config.max_pct_paths];
                        for (int j = 0; j < config.max_pct_paths; j++)
                        {
                                List<PathElement> path = paths.get(j);
                                Double value = get_path_value(path, i, what, change);
                                if (value != null)
                                        vals[values++] = value;
                        }
                        if (values == 0)
                                break;
                        Arrays.sort(vals, 0, values);
                        double pctl = 0.05 / 2;
                        double low = vals[(int) (pctl * values)];
                        double median = vals[(int) (0.5 * values)];
                        double high = vals[(int) ((1 - pctl) * values)];
                        if (high > max_pctl)
                                max_pctl = high;
                        out.println(f2f.format(age_period / config.generate_time_periods) + "," + f4f.format(median) + "," + f4f.format(low) + "," + f4f.format(high));
                        age_period++;
                }
                out.close();

                return max_pctl;
        }

        private void dump_pct_paths(List<List<PathElement>> paths) throws IOException
        {
                for (int i = 0; i < normal_assets; i++)
                        dump_pct_path(paths, asset_classes.get(i), false);
                dump_pct_path(paths, "p", true);
                dump_pct_path(paths, "consume", true);
        }

        // Dump the paths taken.
        private void dump_paths(List<List<PathElement>> paths) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-paths.csv"));

                double initial_period = config.validate_age * config.generate_time_periods;
                for (int pi = 0; pi < config.max_display_paths; pi++)
                {
                        List<PathElement> path = paths.get(pi);
                        double age_period = initial_period;
                        for (PathElement step : path)
                        {
                                double p = step.p;
                                double consume_annual = step.consume_annual;
                                double ria = step.ria;
                                double nia = step.nia;
                                double real_annuitize = step.real_annuitize;
                                double nominal_annuitize = step.nominal_annuitize;
                                String aa = stringify_aa(step.aa);
                                out.print(f2f.format(age_period / config.generate_time_periods));
                                out.print("," + f2f.format(p));
                                out.print("," + (Double.isNaN(consume_annual) ? "" : f2f.format(consume_annual)));
                                out.print("," + f2f.format(ria));
                                out.print("," + f2f.format(nia));
                                out.print("," + f2f.format(real_annuitize));
                                out.print("," + f2f.format(nominal_annuitize));
                                out.print("," + aa);
                                out.print("\n");
                                age_period += 1;
                        }
                        out.print("\n");
                }
                out.close();
        }

        // Dump the changes in the paths.
        private void dump_delta_paths(List<List<PathElement>> paths, int delta_years) throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-delta_paths-" + delta_years + ".csv"));
                List<List<List<Double>>> deltas = new ArrayList<List<List<Double>>>();
                for (int pi = 0; pi < config.max_delta_paths; pi++)
                {
                        List<PathElement> path = paths.get(pi);
                        for (int index = 0; index < ss.max_years * config.generate_time_periods; index++)
                        {
                                if (index >= path.size())
                                        break;
                                if (index >= deltas.size())
                                        deltas.add(new ArrayList<List<Double>>());
                                PathElement pl = path.get(index);
                                double[] aa = null;
                                Double p = null;
                                if (pl != null)
                                {
                                        aa = pl.aa;
                                        p = pl.p;
                                }
                                if (p == null || p < 0.0)
                                        break;
                                if (aa == null)
                                        aa = guaranteed_safe_aa();
                                if (index >= delta_years)
                                {
                                        pl = path.get(index - delta_years);
                                        double[] old_aa = null;
                                        Double old_p = null;
                                        if (pl != null)
                                        {
                                                old_aa = pl.aa;
                                                old_p = pl.p;
                                        }
                                        if (old_aa == null)
                                            old_aa = guaranteed_safe_aa();
                                        List<Double> delta = new ArrayList<Double>();
                                        for (int i = 0; i < normal_assets; i++)
                                                delta.add(aa[i] - old_aa[i]);
                                        deltas.get(index).add(delta);
                                }
                        }
                }
                for (int index = 0; index < ss.max_years * config.generate_time_periods; index++)
                {
                        double[] sd = null;
                        if (index < deltas.size() && deltas.get(index).size() > 1)
                        {
                                sd = new double[deltas.get(index).get(0).size()];
                                int a = 0;
                                for (List<Double> l : Utils.zip(deltas.get(index)))
                                {
                                        sd[a] = Utils.standard_deviation(l);
                                        a++;
                                }
                        }
                        String ssd = stringify_aa(sd, true);
                        out.print(f2f.format((index + config.start_age * config.generate_time_periods) / config.generate_time_periods) + "," + ssd + "\n");
                }
                out.close();
        }

        private void dump_cw() throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-cw.csv"));
                if (config.cw_schedule != null)
                        for (int y = 0; y < config.cw_schedule.length; y++)
                        {
                                out.print(f6f.format(y / config.generate_time_periods) + "," + f6f.format(config.cw_schedule[y]) + "\n");
                        }
                out.close();
        }

        // // Only useful if invariant over portfolio size.
        // private void dump_average(AAMap map) throws IOException
        // {
        //      PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-average.csv"));

        //      for (int period = 0; period < map.map.length; period++)
        //      {
        //              double age = config.start_age + period / config.generate_time_periods;
        //              double ria = 0;
        //              double nia = 0;
        //              double[] aa = new double[normal_assets];
        //              for (int step = 1; step <= config.gnuplot_steps; step++)
        //                      // step = 0 results in division by zero.
        //              {
        //                      double curr_pf = step * config.pf_gnuplot / config.gnuplot_steps;
        //                      double[] p = new double[start_p.length];
        //                      p[tp_index] = curr_pf;
        //                      MapElement fpb = map.lookup_interpolate(p, period);
        //                      double ria_purchase = fpb.ria_purchase(this);
        //                      double nia_purchase = fpb.nia_purchase(this);
        //                      //double spend = fpb.spend;
        //                      //ria += ria_purchase / spend;
        //                      //nia += nia_purchase / spend;
        //                      ria += ria_purchase / curr_pf;
        //                      nia += nia_purchase / curr_pf;
        //                      for (int a = 0; a < aa.length; a++)
        //                              aa[a] += fpb.aa[a];
        //              }
        //              ria /= config.gnuplot_steps;
        //              nia /= config.gnuplot_steps;
        //              for (int a = 0; a < aa.length; a++)
        //                      aa[a] /= config.gnuplot_steps;
        //              out.println(f2f.format(age) + "," + f3f.format(ria) + "," + f3f.format(nia) + "," + stringify_aa(aa));
        //      }
        //      out.close();
        // }

        private void dump_annuity_price() throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-annuity_price.csv"));

                for (int i = 0; i < ss.validate_annuity_stats.actual_real_annuity_price.length; i++)
                {
                        double age = config.start_age + i / config.generate_time_periods;
                        out.println(f2f.format(age) + "," + f3f.format(ss.validate_annuity_stats.actual_real_annuity_price[i]) + "," + f3f.format(ss.validate_annuity_stats.period_real_annuity_price[i]) + "," + f3f.format(ss.validate_annuity_stats.synthetic_real_annuity_price[i]) + "," + f3f.format(ss.validate_annuity_stats.actual_nominal_annuity_price[i]) + "," + f3f.format(ss.validate_annuity_stats.period_nominal_annuity_price[i]) + "," + f3f.format(ss.validate_annuity_stats.synthetic_nominal_annuity_price[i]));
                }
                out.close();
        }

        private void dump_annuity_yield_curve() throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-yield_curve.csv"));

                for (int i = 1; i <= 30; i++)
                        // yield for maturity=0 is arbitrary.
                {
                        out.println(i + "," + (config.annuity_real_yield_curve == null ? config.annuity_real_rate : ss.validate_annuity_stats.rcmt_get(i)) + "," + (config.annuity_nominal_yield_curve == null ? config.annuity_nominal_rate : ss.validate_annuity_stats.hqm_get(i)));
                }

                out.close();
        }

        private void dump_le() throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-le.csv"));
                for (String table : Arrays.asList("ssa-cohort", "iam2012-basic-period", "iam2012-basic-period-aer2005_08", "ssa-period"))
                {
                        boolean iam_aer = table.equals("iam2012-basic-period-aer2005_08");
                        VitalStats stats = new VitalStats(ss, config, hist, 1.0);
                        String keep_method = config.mortality_projection_method;
                        String keep_experience = config.mortality_experience;
                        config.mortality_projection_method = (table.startsWith("iam2012-basic-period") ? "g2" : "rate"); // Irrelevant for cohort.
                        config.mortality_experience = (iam_aer ? "aer2005_08" : "none");
                        stats.compute_stats(iam_aer ? "iam2012-basic-period" : table);
                        config.mortality_projection_method = keep_method;
                        config.mortality_experience = keep_experience;
                        double le = stats.le.get(config.start_age);
                        out.print(table + "," + le);
                        double pct_prev = 0;
                        double pct_curr = 0;
                        int ple = 0;
                        for (double pct_level : Arrays.asList(0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.98, 0.99))
                        {
                                for (; ple < stats.alive.length; ple++)
                                {
                                        pct_curr = 1 - stats.alive[ple];
                                        if (pct_curr >= pct_level)
                                                break;
                                        pct_prev = pct_curr;
                                }
                                double extra = (pct_curr - pct_level) / (pct_curr - pct_prev);
                                if (Double.isInfinite(extra))
                                        extra = 0;
                                out.print("," + (ple - extra));
                        }
                        out.println();
                }
                out.close();
        }

        public void dump_gnuplot_params(double p_max, double consume_max, double annuitization_max, double consume_ara_max) throws IOException
        {
                PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-gnuplot-params.gnuplot")));
                out.println("paths = " + (!config.skip_validate ? 1 : 0));
                out.println("retirement_number = " + (!config.skip_retirement_number ? 1 : 0));
                out.println("bequest = " + (config.utility_dead_limit != 0 ? 1 : 0));
                out.println("age_label = \"" + (config.sex2 == null || config.start_age == config.start_age2 ? "age" : "age of first person") + "\"");
                out.println("age_low = " + config.start_age);
                int age_high = config.start_age + ss.max_years;
                int age_limit = 99;
                if (config.sex2 != null && config.start_age2 < config.start_age)
                        age_limit += config.start_age - config.start_age2;
                if (!config.debug_till_end && age_high > age_limit)
                        age_high = age_limit;
                out.println("age_high = " + age_high);
                out.println("tp = " + p_max);
                out.println("consume = " + consume_max);
                double payout = 0;
                double annuitization = 0;
                if (ria_index != null && config.ria_high > payout)
                {
                        payout = config.ria_high;
                        annuitization = annuitization_max;
                }
                if (nia_index != null && config.nia_high > payout)
                {
                        payout = config.nia_high;
                        annuitization = annuitization_max;
                }
                out.println("annuity_payout = " + payout);
                out.println("annuitization = " + annuitization);
                double scale = 1 / (utility_consume.slope(consume_max) * 200);
                if (utility_consume.slope(0) > 0 && scale * utility_consume.slope(0) < 1)
                        scale = 1 / utility_consume.slope(0);
                out.println("consume_slope_scale = " + scale);
                out.println("consume_ara_max = " + consume_ara_max);
                out.println("retirement_number_max = " + (config.retirement_number_max_factor * retirement_number_max_estimate));
                List<String> ac_names = (asset_class_names == null ? asset_classes : asset_class_names);
                StringBuilder symbols = new StringBuilder();
                StringBuilder names = new StringBuilder();
                for (int i = 0; i < normal_assets; i++)
                {
                        if (i > 0)
                        {
                                symbols.append(" ");
                                names.append(" ");
                        }
                        symbols.append(asset_classes.get(i));
                        names.append(ac_names.get(i).replace(" ", "_"));
                }
                out.println("asset_class_symbols = \"" + symbols + "\"");
                out.println("asset_class_names = \"" + names + "\"");
                out.close();
        }

        private void plot() throws IOException, InterruptedException
        {
                ss.subprocess("plot", config.prefix);
        }

        // Dump and plot the data files.
        private void dump_plot(AAMap map, Metrics[] retirement_number, List<List<PathElement>> paths, Returns returns) throws IOException, InterruptedException
        {
                if (!config.skip_retirement_number)
                {
                        dump_retirement_number(retirement_number);
                }

                double tp_max = tp_max_estimate;
                double consume_max = consume_max_estimate;
                if (!config.skip_validate)
                {
                        dump_distributions(paths);
                        tp_max = dump_pct_path(paths, "p", false);
                        consume_max = dump_pct_path(paths, "consume", false);
                        dump_pct_paths(paths);
                        dump_paths(paths);
                        // Delta paths breaks when validate using validate dump because guaranteed_safe_aa relies on MVO tangency.
                        //dump_delta_paths(paths, 1);
                        //dump_delta_paths(paths, 5);
                }
                if (config.gnuplot_tp != null)
                        tp_max = config.gnuplot_tp;
                else
                        tp_max *= config.gnuplot_extra;
                if (tp_max == 0)
                        tp_max = tp_max_estimate; // Avoid crashing gnuplot.
                tp_max = Math.min(tp_max, config.map_max_factor * tp_max_estimate);
                if (config.gnuplot_consume != null)
                        consume_max = config.gnuplot_consume;
                else
                        consume_max *= config.gnuplot_extra;
                double annuitization_max;
                if (config.gnuplot_annuitization != null)
                        annuitization_max = config.gnuplot_annuitization;
                else
                        annuitization_max = tp_max;

                double consume_ara_max = dump_utility(utility_consume, "consume", consume_max, consume_max / 50);
                        // Avoid plotting possibly highly postive points near the origin.
                consume_ara_max *= config.gnuplot_extra;
                dump_utility(utility_consume_time, "consume_time", consume_max, 0);
                if (config.utility_dead_limit != 0)
                        dump_utility(utility_inherit, "inherit", tp_max, 0);

                if (returns != null)
                {
                        dump_aa_linear(map, returns, tp_max);
                        //dump_average(map);
                        dump_annuity_price();
                        dump_annuity_yield_curve();
                }

                if (!config.skip_dump_le)
                        dump_le();

                if (!config.skip_generate || !config.skip_retirement_number)
                {
                        dump_gnuplot_params(tp_max, consume_max, annuitization_max, consume_ara_max);
                        plot();
                }
        }

        // Dump retirement number values.
        private void dump_retirement_number(Metrics[] retirement_number) throws IOException
        {
                // Success probability percentile lines versus age and wr
                PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-number.csv")));
                for (int i = retirement_number.length - 1; i >= 0; i--)
                {
                        double pf = i * config.retirement_number_max_factor * retirement_number_max_estimate / config.retirement_number_steps;
                        double failure_chance = retirement_number[i].fail_chance();
                        double failure_length = retirement_number[i].fail_length() * ss.validate_stats.le.get(config.retirement_age);
                        double invutil = 0.0;
                        invutil = utility_consume.inverse_utility(retirement_number[i].get(MetricsEnum.CONSUME) / ss.validate_stats.metric_divisor(MetricsEnum.CONSUME, config.validate_age));
                        out.print(pf + "," + failure_chance + "," + failure_length + "," + invutil + "\n");
                }
                out.close();
        }

        private void dump_initial_aa(double[] aa) throws IOException
        {
                PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-initial_aa.csv")));
                out.println("asset class,allocation");
                List<String> names = (asset_class_names == null ? asset_classes : asset_class_names);
                for (int i = 0; i < aa.length; i++)
                        out.println(names.get(i) + "," + aa[i]);
                out.close();
        }

        public void run_mvo(String s) throws IOException, InterruptedException
        {
                if ((do_generate || do_target) && !config.ef.equals("none"))
                {
                        long start = System.currentTimeMillis();
                        mvo(at_returns, s);
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Efficient frontier done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();
                }
        }

        public void report_returns()
        {
                if (returns_generate != null)
                {
                        System.out.println("Returns:");
                        List<double[]> returns = Utils.zipDoubleArray(returns_generate.original_data);
                        for (int index = 0; index < normal_assets; index++)
                        {
                                double gm = Utils.plus_1_geomean(returns.get(index)) - 1;
                                double am = Utils.mean(returns.get(index));
                                double sd = Utils.standard_deviation(returns.get(index));
                                System.out.println("  " + asset_classes.get(index) + " " + f2f.format(gm * 100) + "% +/- " + f2f.format(sd * 100) + "% (arithmetic " + f2f.format(am * 100) + "%)");

                                // System.out.println(am);

                                // double minval = Double.POSITIVE_INFINITY;
                                // int minloc = -1;
                                // for (int i = 0; i < returns.get(index).length - 30; i++)
                                // {
                                //         double val = Utils.plus_1_geomean(Arrays.copyOfRange(returns.get(index), i, i + 30));
                                //      if (val < minval)
                                //      {
                                //              minval = val;
                                //              minloc = i;
                                //      }
                                // }
                                // System.err.println((config.generate_start_year + minloc) + " " + (minval - 1));
                        }
                        // System.out.println(Arrays.deepToString(Utils.covariance_returns(returns)));
                        // System.out.println(Arrays.deepToString(Utils.correlation_returns(returns.toArray(new double[0][]))));
                        System.out.println();

                        System.out.println("Generated returns:");
                        List<double[]> ac_returns = Utils.zipDoubleArray(returns_generate.data);
                        for (int index = 0; index < normal_assets; index++)
                        {
                                double gm = Utils.weighted_plus_1_geo(ac_returns.get(index), returns_generate.returns_unshuffled_probability) - 1;
                                double am = Utils.weighted_sum(ac_returns.get(index), returns_generate.returns_unshuffled_probability);
                                double sd = Utils.weighted_standard_deviation(ac_returns.get(index), returns_generate.returns_unshuffled_probability);
                                System.out.println("  " + asset_classes.get(index) + " " + f2f.format(gm * 100) + "% +/- " + f2f.format(sd * 100) + "% (arithmetic " + f2f.format(am * 100) + "%)");
                        }
                        System.out.println();
                        // System.out.println(Arrays.deepToString(Utils.covariance_returns(ac_returns)));
                        // System.out.println(Arrays.deepToString(Utils.correlation_returns(ac_returns.toArray(new double[0][]))));

                        if (do_tax)
                        {
                                System.out.println("After tax generated returns:");
                                List<double[]> at_rets = Utils.zipDoubleArray(at_returns);
                                for (int index = 0; index < normal_assets; index++)
                                {
                                        double[] at_return = at_rets.get(index);
                                        double gm = Utils.weighted_plus_1_geo(at_return, returns_generate.returns_unshuffled_probability) - 1;
                                        double am = Utils.weighted_sum(at_return, returns_generate.returns_unshuffled_probability);
                                        double sd = Utils.weighted_standard_deviation(at_return, returns_generate.returns_unshuffled_probability);
                                        System.out.println("  " + asset_classes.get(index) + " " + f2f.format(gm * 100) + "% +/- " + f2f.format(sd * 100) + "% (arithmetic " + f2f.format(am * 100) + "%)");
                                }
                                // System.out.println(Arrays.deepToString(Utils.covariance_returns(at_returns)));
                                System.out.println();
                        }
                }

        }

        public void run_compare() throws ExecutionException, IOException
        {
                long start = System.currentTimeMillis();
                for (String aa : config.compare_aa)
                {
                        for (String vw : config.compare_vw)
                        {
                                vw_strategy = vw;
                                AAMap map_compare = AAMap.factory(this, aa, null);
                                PathMetricsResult pm = map_compare.path_metrics(config.validate_age, start_p, config.num_sequences_validate, false, config.validate_seed, returns_validate);
                                System.out.printf("Compare %s/%s: %f\n", aa, vw, pm.mean(success_mode_enum));
                        }
                }
                double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                System.out.println("Compare done: " + f1f.format(elapsed) + " seconds");
                System.out.println();
        }

        private PathMetricsResult search_aa(Returns returns_generate, Returns returns_validate) throws ExecutionException, IOException
        {
                if (config.aa_fixed_stocks == null)
                {
                        double low = 0;
                        double high = 1;
                        while (high - low > 2.0 / config.aa_fixed_steps)
                        {
                                double left = (2 * low + high) / 3;
                                fixed_stocks = left;
                                AAMap map_fixed = AAMap.factory(this, config.aa_strategy, returns_generate);
                                PathMetricsResult pm = map_fixed.path_metrics(config.validate_age, start_p, config.num_sequences_validate, false, config.validate_seed, returns_validate);
                                double left_metric = pm.means.get(success_mode_enum);
                                double right = (low + 2 * high) / 3;
                                fixed_stocks = right;
                                map_fixed = AAMap.factory(this, config.aa_strategy, returns_generate);
                                pm = map_fixed.path_metrics(config.validate_age, start_p, config.num_sequences_validate, false, config.validate_seed, returns_validate);
                                double right_metric = pm.means.get(success_mode_enum);
                                if (left_metric < right_metric)
                                        low = left;
                                else
                                        high = right;
                        }
                        fixed_stocks = (low + high) / 2;
                }
                else
                        fixed_stocks = config.aa_fixed_stocks;

                AAMap map_fixed = AAMap.factory(this, config.aa_strategy, returns_generate);
                PathMetricsResult pm = map_fixed.path_metrics(config.validate_age, start_p, config.num_sequences_validate, false, config.validate_seed, returns_validate);

                return pm;
        }

        public void run_main() throws ExecutionException, IOException, InterruptedException
        {
                AAMap map_validate = null;
                AAMap map_loaded = null;
                AAMap map_precise = null;

                Metrics[] retirement_number = null;

                boolean do_aa_search = config.aa_strategy.equals("fixed") && config.aa_fixed_stocks == null;
                boolean do_vw_search = (config.vw_strategy.equals("percentage") || config.vw_strategy.equals("retirement_amount")) && config.vw_percentage == null;
                if (do_aa_search || do_vw_search)
                {
                        long start = System.currentTimeMillis();
                        if (config.vw_percentage == null)
                        {
                                double vw_low = 0;
                                double vw_high = 1;
                                while (vw_high - vw_low > 2.0 / config.vw_percentage_steps)
                                {
                                        double vw_left = (2 * vw_low + vw_high) / 3;
                                        vw_percent = vw_left;
                                        PathMetricsResult vw_left_pm = search_aa(returns_generate, returns_validate);
                                        double vw_right = (vw_low + 2 * vw_high) / 3;
                                        vw_percent = vw_right;
                                        PathMetricsResult vw_right_pm = search_aa(returns_generate, returns_validate);
                                        if (vw_left_pm.means.get(success_mode_enum) < vw_right_pm.means.get(success_mode_enum))
                                            vw_low = vw_left;
                                        else
                                            vw_high = vw_right;
                                }
                                vw_percent = (vw_low + vw_high) / 2;
                        }
                        else
                                vw_percent = config.vw_percentage;

                        search_aa(returns_generate, returns_validate); // Sets fixed stocks.

                        if (do_aa_search)
                                System.out.println("Fixed stocks: " + fixed_stocks);
                        if (do_vw_search)
                                System.out.println("Variable withdrawal percentage: " + vw_percent);
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Search done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();
                }

                if (do_generate)
                {
                        long start = System.currentTimeMillis();
                        map_precise = AAMap.factory(this, config.aa_strategy, returns_generate);
                        MapElement fpb = map_precise.lookup_interpolate(start_p, (int) Math.round((config.validate_age - config.start_age) * config.generate_time_periods));
                        String metric_str;
                        double metric_normalized = metric_normalize(success_mode_enum, fpb.metric_sm, config.start_age);
                        if (Arrays.asList(MetricsEnum.TW, MetricsEnum.NTW).contains(success_mode_enum))
                        {
                                metric_str = f2f.format(metric_normalized * 100) + "%";
                        }
                        else
                        {
                                metric_str = Double.toString(metric_normalized);
                        }
                        double[] aa = new double[normal_assets];
                        for (int a = 0; a < aa.length; a++)
                        {
                                aa[a] = fpb.aa[a];
                        }
                        System.out.println("Age " + config.validate_age + ", Portfolio " + Arrays.toString(fpb.rps));
                        System.out.println("Consume: " + fpb.consume);
                        System.out.println("Asset allocation: " + Arrays.toString(aa));
                        System.out.println("Real immediate annuities purchase: " + fpb.ria_purchase(this));
                        System.out.println("Nominal immediate annuities purchase: " + fpb.nia_purchase(this));
                        System.out.println("Generated metric: " + config.success_mode + " " + metric_str);
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Asset allocation done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();

                        dump_initial_aa(aa);

                        start = System.currentTimeMillis();
                        map_loaded = new AAMapDumpLoad(this, map_precise, ss.validate_stats);
                        elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        if (!config.skip_dump_load)
                        {
                                System.out.println("Reload done: " + f1f.format(elapsed) + " seconds");
                                System.out.println();
                        }

                        // if (!config.skip_smooth)
                        // {
                        //      start = System.currentTimeMillis();
                        //      ((AAMapDumpLoad) map_loaded).smooth_map();
                        //      elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        //      System.out.println("Smoothed done: " + f1f.format(elapsed) + " seconds");
                        //      System.out.println();
                        // }
                }
                else if (config.validate != null)
                {
                        map_validate = new AAMapDumpLoad(this, config.validate, ss.validate_stats);
                        map_loaded = map_validate;
                }

                if (!config.skip_retirement_number && ((config.validate == null) || config.validate_dump))
                {
                        long start = System.currentTimeMillis();
                        retirement_number = map_loaded.simulate_retirement_number(returns_validate);
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Retirement number done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();
                }

                // if (!config.skip_success_lines && ((config.validate == null) || config.validate_dump))
                // {
                //      long start = System.currentTimeMillis();
                //      success_lines = map_loaded.simulate_success_lines(returns_validate);
                //      double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                //      System.out.println("Success probability lines done: " + f1f.format(elapsed) + " seconds");
                //      System.out.println();
                // }

                if (do_target)
                {
                        long start = System.currentTimeMillis();
                        for (String scheme : config.target_schemes)
                        {
                                AAMap map_compare = AAMap.factory(this, scheme, null);
                                double keep_rebalance_band = config.rebalance_band_hw;
                                if (config.target_rebalance)
                                        config.rebalance_band_hw = 0.0;
                                AAMap baseline_map = (config.target_sdp_baseline ? map_loaded : map_compare);
                                AAMap target_map = (config.target_sdp_baseline ? map_compare : map_loaded);
                                PathMetricsResult pm = baseline_map.path_metrics(config.validate_age, start_p, config.num_sequences_target, false, 0, returns_target);
                                config.rebalance_band_hw = keep_rebalance_band;
                                Metrics means = pm.means;
                                Metrics standard_deviations = pm.standard_deviations;
                                String location_str;
                                double target_result = Double.NaN;
                                double target_tp = Double.NaN;
                                double target_rcr = Double.NaN;
                                if (config.target_mode.equals("rps"))
                                {
                                        TargetResult t = target_map.rps_target(config.validate_age, means.get(success_mode_enum), returns_target, config.target_sdp_baseline);
                                        //map_loaded = t.map;
                                        target_result = t.target_result;
                                        target_tp = t.target;
                                        location_str = f2f.format(target_tp);
                                }
                                else
                                {
                                        assert(false);
                                        location_str = null;
                                        // TargetResult t = target_map.rcr_target(config.validate_age, means.get(success_mode_enum), config.target_sdp_baseline, returns_generate, returns_target, config.target_sdp_baseline);
                                        // //if (!config.target_sdp_baseline)
                                        // //   map_loaded = t.map;
                                        // target_result = t.target_result;
                                        // target_rcr = t.target;
                                        // location_str = "RCR " + f4f.format(target_rcr);
                                }
                                String target_str;
                                if (!Arrays.asList(MetricsEnum.TW, MetricsEnum.NTW).contains(success_mode_enum))
                                        target_str = f8.format(target_result);
                                else
                                        target_str = f2f.format(target_result * 100) + "%";
                                double savings;
                                String savings_str;
                                if (config.target_mode.equals("rps"))
                                {
                                        if (config.target_sdp_baseline)
                                                savings = (target_tp - start_p[tp_index]) / target_tp;
                                        else
                                                savings = (start_p[tp_index] - target_tp) / start_p[tp_index];
                                        savings_str = f1f.format(savings * 100) + "%";
                                }
                                else
                                {
                                        if (config.target_sdp_baseline)
                                                savings = (target_rcr - config.accumulation_rate) / target_rcr;
                                        else
                                                savings = (config.accumulation_rate - target_rcr) / config.accumulation_rate;
                                        savings_str = f1f.format(savings * 100) + "%";
                                }
                                System.out.printf("Target %-21s %s found at %s savings %s\n", scheme, target_str, location_str, savings_str);
                        }
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Target done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();
                }

                List<List<PathElement>> paths = new ArrayList<List<PathElement>>();
                if (!config.skip_validate)
                {
                        long start = System.currentTimeMillis();
                        if (!config.skip_validate_all)
                        {
                                PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-ce.csv")));
                                for (int age = config.start_age; age < config.start_age + ss.max_years; age++)
                                {
                                        PathMetricsResult pm = map_loaded.path_metrics(age, start_p, config.num_sequences_validate, false, config.validate_seed, returns_validate);
                                        double ce = utility_consume.inverse_utility(pm.means.get(MetricsEnum.CONSUME) / ss.validate_stats.metric_divisor(MetricsEnum.CONSUME, age));
                                        out.println(age + "," + f7f.format(ce));

                                }
                                out.close();
                        }
                        PathMetricsResult pm = map_loaded.path_metrics(config.validate_age, start_p, config.num_sequences_validate, true, config.validate_seed, returns_validate);
                        paths = pm.paths;
                        pm.print();
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Calculate metrics done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();
                }

                if (config.validate != null)
                {
                        if (config.validate_dump)
                        {
                                long start = System.currentTimeMillis();
                                dump_plot(null, retirement_number, paths, null);
                                double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                                System.out.println("Dump and plot done: " + f1f.format(elapsed) + " seconds");
                                System.out.println();
                        }
                }
                else
                {
                        long start = System.currentTimeMillis();
                        dump_plot(map_precise, retirement_number, paths, returns_generate);
                        double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                        System.out.println("Dump/plot done: " + f1f.format(elapsed) + " seconds");
                        System.out.println();
                        if (!config.skip_dump_log)
                        {
                                System.out.println("Dump generated:");
                                map_precise.dump_log();
                                System.out.println();
                                //System.out.println("Dump loaded:");
                                //map_loaded.dump_log();
                        }
                }
        }

        public Scenario(ScenarioSet ss, Config config, HistReturns hist, List<String> asset_classes, List<String> asset_class_names, Double start_ria, Double start_nia) throws IOException, InterruptedException
        {
                this.ss = ss;
                this.config = config;
                this.hist = hist;
                this.asset_classes = asset_classes;
                this.asset_class_names = asset_class_names;

                // Internal parameters.

                int p_size = 0;
                tp_index = (config.start_tp == null ? null : p_size);
                if (tp_index != null)
                        p_size++;
                ria_index = (start_ria == null ? null : p_size);
                if (ria_index != null)
                        p_size++;
                nia_index = (start_nia == null ? null : p_size);
                if (nia_index != null)
                        p_size++;
                start_p = new double[p_size];
                if (tp_index != null)
                        start_p[tp_index] = config.start_tp;
                if (ria_index != null)
                        start_p[ria_index] = start_ria;
                if (nia_index != null)
                        start_p[nia_index] = start_nia;

                int years = Math.max(0, config.retirement_age - config.start_age);
                double retirement_le = ss.validate_stats.le.get(config.retirement_age);
                double ia = 0;
                if (ria_index != null)
                        ia += start_ria;
                if (nia_index != null)
                        ia += start_nia;
                tp_max_estimate = 0;
                // The following scaling factors are detrmined empirically to give reasonable matches to the actual values.
                if (!config.skip_retirement_number)
                        tp_max_estimate = 2 * Math.max(0, config.floor - config.defined_benefit - ia) * retirement_le;
                final double return_rate = 1.05;
                double discounted_savings;
                if (config.accumulation_ramp == return_rate)
                        discounted_savings = years;
                else
                        discounted_savings = (Math.pow(config.accumulation_ramp / return_rate, years) - 1) / (config.accumulation_ramp / return_rate - 1);
                discounted_savings *= config.accumulation_rate;
                tp_max_estimate = Math.max(tp_max_estimate, 5 * (config.start_tp + discounted_savings) * Math.pow(return_rate, years));
                consume_max_estimate = config.defined_benefit + 2 * tp_max_estimate / retirement_le + ia;
                tp_max_estimate += config.defined_benefit + ia; // Assume minimal carry over from one period to the next.
                retirement_number_max_estimate = Math.max(1e-3 * config.floor, (config.floor - config.defined_benefit - ia) * retirement_le);

                // Set up the scales.
                scale = new Scale[start_p.length];
                if (tp_index != null)
                        scale[tp_index] = Scale.scaleFactory(config.tp_zero_factor * consume_max_estimate, config.scaling_factor);
                if (ria_index != null)
                        scale[ria_index] = Scale.scaleFactory(config.annuity_zero_factor * consume_max_estimate, config.annuity_scaling_factor);
                if (nia_index != null)
                        scale[nia_index] = Scale.scaleFactory(config.annuity_zero_factor * consume_max_estimate, config.annuity_scaling_factor);

                // Calculated parameters.

                generate_bottom_bucket = this.scale[tp_index].pf_to_bucket(config.map_max_factor * tp_max_estimate);
                generate_top_bucket = this.scale[tp_index].pf_to_bucket(config.pf_fail);
                validate_bottom_bucket = this.scale[tp_index].pf_to_bucket(config.map_max_factor * tp_max_estimate);
                validate_top_bucket = this.scale[tp_index].pf_to_bucket(0.0);
                success_mode_enum = Metrics.to_enum(config.success_mode);

                fixed_stocks = config.aa_fixed_stocks;

                vw_strategy = config.vw_strategy;
                vw_percent = config.vw_percentage;

                if (config.cw_schedule != null && ss.max_years > config.cw_schedule.length)
                        ss.max_years = config.cw_schedule.length;

                // Sanity checks.
                assert(config.validate_age < config.start_age + ss.max_years);
                if (config.ef.equals("none"))
                {
                        assert(asset_classes.contains(config.safe_aa));
                        assert(asset_classes.contains(config.fail_aa));
                }
                else
                {
                        assert(!config.search.equals("memory"));
                }
                assert(config.max_borrow == 0.0 || !config.borrow_aa.equals(config.fail_aa));
                assert(config.validate_time_periods >= config.rebalance_time_periods);
                if (config.utility_join)
                {
                        assert(config.consume_discount_rate <= config.upside_discount_rate);
                                // Ensures able to add upside utility to floor utility without exceeding u_inf.
                        assert(config.utility_age <= (config.utility_retire ? config.retirement_age : config.start_age));
                                // Ditto.
                }
                assert(!config.utility_epstein_zin || (success_mode_enum == MetricsEnum.COMBINED)); // Other success modes not Epstein-Zinized.

                // More internal parameters.

                do_tax = config.tax_rate_cg != 0 || config.tax_rate_div != null || config.tax_rate_div_default != 0 || config.tax_rate_annuity != 0;
                do_target = !config.skip_target && config.target_mode != null;
                do_generate = !config.skip_generate || (!config.skip_validate && (config.validate == null)) || (do_target && (config.target_sdp_baseline || config.target_mode.equals("rps")));

                normal_assets = asset_classes.size();
                cpi_index = -1;
                if (do_tax || (ria_index != null && config.tax_rate_annuity != 0) || nia_index != null)
                {
                        cpi_index = asset_classes.size();
                        asset_classes.add("[cpi]");
                }
                stochastic_classes = asset_classes.size();
                ria_aa_index = -1;
                if (ria_index != null)
                {
                        assert(config.sex2 == null); // Calculated annuity purchase prices are for a couple which doesn't work if one party is dead.
                        ria_aa_index = asset_classes.size();
                        asset_classes.add("[ria]");
                }
                nia_aa_index = -1;
                if (nia_index != null)
                {
                        assert(config.sex2 == null);
                        nia_aa_index = asset_classes.size();
                        asset_classes.add("[nia]");
                }
                spend_fract_index = asset_classes.size();
                asset_classes.add("[spend_fract]");
                all_alloc = asset_classes.size();
                ef_index = -1;
                if (!config.ef.equals("none"))
                {
                        ef_index = asset_classes.size();
                        asset_classes.add("[ef_index]");
                }

                // Set up utility functions.

                double consume_ref = consume_max_estimate / 2; // Somewhat arbitrary.
                Double eta = (config.utility_epstein_zin ? (Double) config.utility_gamma : config.utility_eta);
                Utility utility_consume_risk = Utility.utilityFactory(config, config.utility_consume_fn, eta, config.utility_beta, config.utility_alpha, 0, consume_ref, config.utility_ce, config.utility_ce_ratio, 2 * consume_ref, 1 / config.utility_slope_double_withdrawal, consume_ref, 1, config.public_assistance, config.public_assistance_phaseout_rate);
                eta = (config.utility_epstein_zin ? (Double) (1 / config.utility_psi) : config.utility_eta);
                utility_consume_time = Utility.utilityFactory(config, config.utility_consume_fn, eta, config.utility_beta, config.utility_alpha, 0, consume_ref, config.utility_ce, config.utility_ce_ratio, 2 * consume_ref, 1 / config.utility_slope_double_withdrawal, consume_ref, 1, config.public_assistance, config.public_assistance_phaseout_rate);

                if (config.utility_join)
                {
                        Utility utility_consume_risk_2 = Utility.utilityFactory(config, "power", config.utility_eta_2, 0, 0.0, 0, consume_ref, 0.0, 0, 0, 0, config.utility_join_required, config.utility_join_slope_ratio * utility_consume_risk.slope(config.utility_join_required), 0, 0);
                        utility_consume_risk = Utility.joinFactory(config, config.utility_join_type, utility_consume_risk, utility_consume_risk_2, config.utility_join_required, config.utility_join_required + config.utility_join_desired);
                        Utility utility_consume_time_2 = Utility.utilityFactory(config, "power", config.utility_eta_2, 0, 0.0, 0, consume_ref, 0.0, 0, 0, 0, config.utility_join_required, config.utility_join_slope_ratio * utility_consume_time.slope(config.utility_join_required), 0, 0);
                        utility_consume_time = Utility.joinFactory(config, config.utility_join_type, utility_consume_time, utility_consume_time_2, config.utility_join_required, config.utility_join_required + config.utility_join_desired);
                }
                utility_consume = utility_consume_risk;

                if (config.utility_dead_limit != 0)
                        // Model: Bequest to 1 person for utility_inherit_years or utility_inherit_years people for 1 year who are currently consuming bequest_consume
                        // and share the same utility function as you.
                        utility_inherit = new UtilityScale(config, utility_consume_time, 0, 1 / config.utility_inherit_years, config.utility_inherit_years * config.utility_dead_limit, - config.utility_bequest_consume);

                // Set up returns.

                returns_generate = null;
                if (do_generate || do_target  || do_tax)
                        returns_generate = new Returns(this, hist, config, config.generate_seed, false, config.generate_start_year, config.generate_end_year, config.num_sequences_generate, config.generate_time_periods, config.generate_ret_equity, config.generate_ret_bonds, config.ret_risk_free, config.generate_ret_inflation, config.management_expense, config.generate_shuffle, config.ret_reshuffle, config.generate_draw, config.ret_bootstrap_block_size, config.ret_pair, config.ret_short_block, config.generate_all_adjust, config.generate_equity_vol_adjust);

                returns_target = null;
                if (do_target)
                        returns_target = new Returns(this, hist, config, config.target_seed, false, config.target_start_year, config.target_end_year, config.num_sequences_target, config.validate_time_periods, config.validate_ret_equity, config.validate_ret_bonds, config.ret_risk_free, config.validate_ret_inflation, config.management_expense, config.target_shuffle, config.ret_reshuffle, config.target_draw, config.ret_bootstrap_block_size, config.ret_pair, config.target_short_block, config.validate_all_adjust, config.validate_equity_vol_adjust);

                returns_validate = new Returns(this, hist, config, config.validate_seed, !config.skip_retirement_number, config.validate_start_year, config.validate_end_year, config.num_sequences_validate, config.validate_time_periods, config.validate_ret_equity, config.validate_ret_bonds, config.ret_risk_free, config.validate_ret_inflation, config.management_expense, config.validate_shuffle, config.ret_reshuffle, config.validate_draw, config.ret_bootstrap_block_size, config.ret_pair, config.ret_short_block, config.validate_all_adjust, config.validate_equity_vol_adjust);

                if (returns_generate != null)
                {
                        dividend_yield = new double[normal_assets];
                        double[] dividend_fract = (config.dividend_fract == null ? returns_generate.dividend_fract : config.dividend_fract);
                        List<double[]> ac_returns = Utils.zipDoubleArray(returns_generate.data);
                        for (int index = 0; index < normal_assets; index++)
                        {
                                double gm = Utils.weighted_plus_1_geo(ac_returns.get(index), returns_generate.returns_unshuffled_probability) - 1;
                                dividend_yield[index] = dividend_fract[index] * gm / (1 + gm);
                        }

                        at_returns = returns_generate.data;
                        if (do_tax)
                        {
                                at_returns = Utils.zipDoubleArray(at_returns);
                                Tax tax = new TaxImmediate(this, config.tax_immediate_adjust);
                                for (int index = 0; index < normal_assets; index++)
                                {
                                        double[] at_return = at_returns.get(index);
                                        double[] aa = new double[normal_assets];
                                        aa[index] = 1;
                                        tax.initial(1, aa);
                                        for (int i = 0; i < at_return.length; i++)
                                        {
                                                at_return[i] -= tax.total_pending(1 + at_return[i], 1, aa, returns_generate.data.get(i));
                                                        // This like most tax calculations is imperfect.
                                        }
                                }
                                at_returns = Utils.zipDoubleArray(at_returns);
                        }
                }
        }
}
