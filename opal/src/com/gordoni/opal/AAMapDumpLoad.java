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
import java.text.DecimalFormat;
import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;

class AAMapDumpLoad extends AAMap
{
        private static DecimalFormat f2f = new DecimalFormat("0.00");
        private static DecimalFormat f9f = new DecimalFormat("0.000000000");

        public void dump_aa(AAMap map) throws IOException
        {
                for (int a = 0; a < scenario.normal_assets - 1; a++)
                {
                        dump_map(map, scenario.asset_classes.get(a));
                }
        }

        public void dump_map(AAMap map, String map_name) throws IOException
        {
                PrintWriter out = new PrintWriter(new FileWriter(new File(scenario.ss.cwd + '/' + config.prefix + "-" + map_name + ".csv")));
                for (int i = 1; i < scenario.start_p.length; i++)
                        out.write(",");
                for (int i = 0; i < map.map.length; i++)
                        out.write("," + f2f.format((i + config.start_age * config.generate_time_periods) / config.generate_time_periods));
                out.write("\n");
                for (MapElement me_index : map.map[0])
                {
                        double fb[] = scenario.pToFractionalBucket(me_index.rps, null);
                        int[] index = new int[fb.length];
                        for (int i = 0; i < fb.length; i++)
                                index[i] = (int) Math.round(fb[i]);
                        if (index[scenario.tp_index] < scenario.validate_bottom_bucket || index[scenario.tp_index] > scenario.validate_top_bucket)
                                continue;
                        for (int i = 0; i < me_index.rps.length; i++)
                        {
                                if (i > 0)
                                        out.write(",");
                                out.write(f2f.format(me_index.rps[i]));
                        }
                        int aa_index = scenario.asset_classes.indexOf(map_name);
                        int borrow_index = scenario.asset_classes.indexOf(config.borrow_aa);
                        for (MapPeriod map_period : map.map)
                        {
                                MapElement me = map_period.get(index);
                                String value = null;
                                if (map_name.equals("return"))
                                        value = f9f.format(me.mean);
                                else if (map_name.equals("risk"))
                                        value = f9f.format(me.std_dev);
                                else if (map_name.equals("spend_fract"))
                                        value = f9f.format(me.aa[scenario.spend_fract_index]);
                                else if (map_name.equals("ria"))
                                        value = f9f.format(me.aa[scenario.ria_aa_index]);
                                else if (map_name.equals("nia"))
                                        value = f9f.format(me.aa[scenario.nia_aa_index]);
                                else
                                {
                                        assert(aa_index != -1);

                                        double[] aa = me.aa;

                                        double s = 0.0;
                                        double a = 0.0;
                                        for (int j = 0; j < scenario.normal_assets; j++)
                                        {
                                                s += aa[j];
                                                assert(-config.max_borrow - 1e-6 <= aa[j] && aa[j] <= 1.0 + config.max_borrow + 1e-6);
                                                a += Math.min(aa[j], 0.0);
                                        }
                                        assert (-1e-6 < 1.0 - s && 1.0 - s < 1e-6);
                                        assert(-config.max_borrow - 1e-6 <= a);

                                        double remainder = 0.0;
                                        double allocation = 0.0;
                                        for (int j = 0; j <= aa_index; j++)
                                        {
                                                allocation = Math.round((aa[j] + remainder) * 1e9) / 1e9; // Carry across fractions so result sums to 1.
                                                double min = (j == borrow_index ? - config.max_borrow : 0.0);
                                                allocation = Math.max(allocation, min);
                                                remainder += aa[j] - allocation;
                                        }
                                        if (aa_index == scenario.normal_assets - 1)
                                                assert(-1e-6 < remainder && remainder < 1e-6);

                                        value = f9f.format(allocation);
                                }
                                out.write("," + value);
                        }
                        out.write("\n");
                }
                out.close();
        }

        private void load_extra(MapPeriod [] map, String aa_file_prefix, String what) throws IOException
        {
                BufferedReader in = new BufferedReader(new FileReader(new File(aa_file_prefix + "-" + what + ".csv")));
                String line = null;

                List<String> ages_strs = new ArrayList<String>();
                int idx = 0;
                List<Double> periods = new ArrayList<Double>();
                while ((line = in.readLine()) != null)
                {
                        if (idx++ == 0)
                        {
                                String ages_str = line;
                                String[] a_ages_strs = ages_str.split(",", -1);
                                for (int i = scenario.start_p.length; i < a_ages_strs.length; i++)
                                {
                                        ages_strs.add(a_ages_strs[i]);
                                }
                                for (String age : ages_strs)
                                {
                                        periods.add(Double.parseDouble(age) * config.generate_time_periods);
                                }
                                assert (Math.round(periods.get(0)) == Math.round(config.start_age * config.generate_time_periods));
                                continue;
                        }
                        line = line.trim();
                        List<Double> fields = new ArrayList<Double>();
                        for (String field : line.split(",", -1))
                        {
                                fields.add(field.equals("") ? null : Double.parseDouble(field));
                        }
                        double[] p = new double[scenario.start_p.length];
                        for (int i = 0; i < p.length; i++)
                                p[i] = fields.get(i);
                        List<Double> contrib_array = new ArrayList<Double>();
                        for (int i = p.length; i < fields.size(); i++)
                        {
                                contrib_array.add(fields.get(i));
                        }
                        int[] bucket = scenario.pToBucket(p, "round");
                        for (List<Double> l : Utils.zip(periods, contrib_array))
                        {
                                double age_period = l.get(0);
                                Double value = l.get(1);
                                MapElement me = map[(int) Math.round(age_period - config.start_age * config.generate_time_periods)].get(bucket);
                                if (what.equals("spend_fract"))
                                        me.aa[scenario.spend_fract_index] = value;
                                else if (what.equals("ria"))
                                        me.aa[scenario.ria_aa_index] = value;
                                else if (what.equals("nia"))
                                        me.aa[scenario.nia_aa_index] = value;
                                else
                                        assert(false);
                        }
                }
                in.close();
        }

        @SuppressWarnings("unchecked")
        public AAMapDumpLoad(Scenario scenario, String aa_file_prefix, VitalStats validate_stats) throws IOException
        {
                super(scenario, null, null, null, validate_stats, scenario.utility_consume_time, scenario.utility_consume, scenario.config.defined_benefit);

                map = new MapPeriod[(int) (scenario.ss.max_years * config.generate_time_periods)];

                for (int aa_index = 0; aa_index < scenario.normal_assets - 1; aa_index++)
                {
                        String aa_name = scenario.asset_classes.get(aa_index);
                        if (aa_file_prefix == null)
                                aa_file_prefix = scenario.ss.cwd + '/' + config.prefix;

                        BufferedReader in = new BufferedReader(new FileReader(new File(aa_file_prefix + "-" + aa_name + ".csv")));
                        String line = null;
                        int idx = 0;

                        List<String> ages_strs = new ArrayList<String>();
                        List<Double> periods = new ArrayList<Double>();
                        while ((line = in.readLine()) != null)
                        {
                                if (idx++ == 0)
                                {
                                        String ages_str = line;
                                        String[] a_ages_strs = ages_str.split(",", -1);
                                        for (int i = scenario.start_p.length; i < a_ages_strs.length; i++)
                                        {
                                                ages_strs.add(a_ages_strs[i]);
                                        }
                                        for (String age : ages_strs)
                                        {
                                            periods.add(Double.parseDouble(age) * config.generate_time_periods);
                                        }
                                        assert (Math.round(periods.get(0)) == Math.round(config.start_age * config.generate_time_periods));
                                        continue;
                                }
                                line = line.trim();
                                if (line.length() == 0)
                                        continue;
                                List<Double> fields = new ArrayList<Double>();
                                for (String field : line.split(",", -1))
                                {
                                        fields.add(field.equals("") ? null : Double.parseDouble(field));
                                }
                                double[] p = new double[scenario.start_p.length];
                                for (int i = 0; i < p.length; i++)
                                        p[i] = fields.get(i);
                                List<Double> allocation_array = new ArrayList<Double>();
                                for (int i = p.length; i < fields.size(); i++)
                                {
                                        allocation_array.add(fields.get(i));
                                }
                                int[] bucket = scenario.pToBucket(p, "round");
                                double[] rps = scenario.bucketToP(bucket);
                                for (List<Double> l : Utils.zip(periods, allocation_array))
                                {
                                        double age_period = l.get(0);
                                        int pi = (int) Math.round(age_period - config.start_age * config.generate_time_periods);
                                        Double allocation = l.get(1);
                                        if (map[pi] == null)
                                                map[pi] = new MapPeriod(scenario, false);
                                        MapElement fpb = map[pi].get(bucket);
                                        if (fpb == null)
                                        {
                                                fpb = new MapElement(rps, null, null, null, null);
                                                map[pi].set(bucket, fpb);
                                        }
                                        if (allocation != null)
                                        {
                                                if (fpb.aa == null)
                                                    fpb.aa = new double[0];
                                                assert (fpb.aa.length == aa_index);
                                                double[] new_aa = new double[fpb.aa.length + 1];
                                                for (int a = 0; a < fpb.aa.length; a++)
                                                        new_aa[a] = fpb.aa[a];
                                                new_aa[new_aa.length - 1] = allocation;
                                                fpb.aa = new_aa;
                                        }
                                        else
                                        {
                                                assert (fpb.aa == null);
                                        }
                                }
                        }
                        in.close();
                }

                for (int pi = 0; pi < map.length; pi++)
                {
                        if (scenario.normal_assets == 1)
                        {
                                assert(false);
                                // Want:
                                //    loop:
                                //        double[] aa = new double[] {};
                                //        MapElement fpb = new MapElement(p, aa, 0.0, null, null, null);
                                //        map[pi].set(bucket_index, fpb);
                                // but no easy way to loop.
                        }
                        for (MapElement me : map[pi])
                        {
                                assert(me != null);
                                double[] aa = me.aa;
                                if (aa != null)
                                {
                                        double[] new_aa = new double[scenario.asset_classes.size()];
                                        for (int a = 0; a < aa.length; a++)
                                        {
                                                new_aa[a] = aa[a];
                                        }
                                        new_aa[aa.length] = 1.0 - Utils.sum(aa);
                                        me.aa = new_aa;
                                        assert (new_aa.length == scenario.asset_classes.size());
                                        double s = 0.0;
                                        double a = 0.0;
                                        for (int i = 0; i <= aa.length; i++)
                                        {
                                                s += new_aa[i];
                                                assert(-config.max_borrow - 1e-6 <= new_aa[i] && new_aa[i] <= 1.0 + config.max_borrow + 1e-6);
                                                a += Math.min(new_aa[i], 0.0);
                                        }
                                        assert (-1e-6 < 1.0 - s && 1.0 - s < 1e-6);
                                        assert(-config.max_borrow - 1e-6 <= a);
                                }
                        }
                        map[pi].interpolate(false);
                }

                if (!scenario.vw_strategy.equals("amount"))
                        load_extra(map, aa_file_prefix, "spend_fract");
                if (scenario.ria_index != null)
                    load_extra(map, aa_file_prefix, "ria");
                if (scenario.nia_index != null)
                    load_extra(map, aa_file_prefix, "nia");
        }

        public AAMapDumpLoad(Scenario scenario, AAMap map_precise, VitalStats validate_stats) throws IOException
        {
                // Dump out and re-read asset allocation so that we are reporting stats after any loss of precision resulting from the limited
                // precision of the aa file.  Emperically, the results are found to vary by around 0.01% as a result of this.

                super(scenario, null, null, null, validate_stats, map_precise.uc_time, map_precise.uc_risk, map_precise.guaranteed_income);

                if (config.skip_dump_load)
                {
                        map = new MapPeriod[(int) (scenario.ss.max_years * config.generate_time_periods)];

                        for (int pi = 0; pi < map.length; pi++)
                        {
                                MapPeriod mp = new MapPeriod(scenario, false);
                                map[pi] = mp;
                                MapPeriodIterator itr = mp.iterator();
                                while (itr.hasNext())
                                {
                                        int[] v_index = itr.nextIndex();
                                        int[] g_index = v_index.clone();
                                        g_index[scenario.tp_index] += scenario.validate_bottom_bucket - scenario.generate_bottom_bucket;
                                        mp.set(v_index, map_precise.map[pi].get(g_index));
                                        itr.next();
                                }
                                mp.interpolate(false);
                        }

                        if (map_precise.aamap1 != null)
                        {
                                aamap1 = new AAMapDumpLoad(scenario, map_precise.aamap1, validate_stats.vital_stats1);
                                aamap2 = new AAMapDumpLoad(scenario, map_precise.aamap2, validate_stats.vital_stats2);
                        }

                        return;
                }

                assert(config.sex2 == null || config.couple_unit);

                dump_aa(map_precise);
                // for (int pi = 0; pi < map_precise.map.length; pi++)
                // {
                //         for (int bi = 0; bi < map_precise.map[pi].length[scenario.tp_index]; bi++)
                //      {
                //              int[] bucket_index = new int[scenario.start_p.length];
                //              bucket_index[scenario.tp_index] = bi + scenario.generate_bottom_bucket;
                //              MapElement me = map_precise.map[pi].get(bucket_index);
                //              RiskReward rw = scenario.rw_aa(scenario.at_returns, me.aa, "linear");
                //              me.mean = rw.mean;
                //              me.std_dev = rw.std_dev;
                //      }
                // }
                // dump_map(map_precise, "risk");
                // dump_map(map_precise, "return");
                if (!scenario.vw_strategy.equals("amount"))
                        dump_map(map_precise, "spend_fract");
                if (scenario.ria_index != null)
                        dump_map(map_precise, "ria");
                if (scenario.nia_index != null)
                        dump_map(map_precise, "nia");
                AAMapDumpLoad loaded_map = new AAMapDumpLoad(scenario, (String) null, validate_stats);
                map = loaded_map.map;
                // // Copy across raw goal so that dump_paths() can display it. Only for opal-paths-success.png, which isn't very popular.
                // // Also used by opal-success-raw.png.
                // for (int pi = 0; pi < map.length; pi++)
                // {
                //      for (int bucket = scenario.validate_bottom_bucket; bucket < scenario.validate_top_bucket + 1; bucket++)
                //      {
                //              int[] bucket_index = new int[scenario.start_p.length];
                //              bucket_index[scenario.tp_index] = bucket - scenario.validate_bottom_bucket;
                //              map[pi].get(bucket_index).results = map_precise.map[pi].get(bucket_index).results;
                //      }
                // }
        }

        // public void smooth_map()
        // {
        //      // Initial smoothing had an age shift bias; re-smooth unbiased.
        //         // Could code in parallel.
        //      for (int pi = 0; pi < map.length; pi++)
        //      {
        //              smooth_map_period(pi, false);
        //      }
        // }

        // // Smooth out the map before it can be used.
        // private void smooth_map_period(int period, boolean partial_mode)
        // {
        //         if (config.skip_smooth)
        //              return;

        //      int bucket_range0;
        //      int bucket_range1;
        //      if (partial_mode)
        //      {
        //              bucket_range0 = scenario.generate_bottom_bucket;
        //              bucket_range1 = scenario.generate_top_bucket + 1;
        //      }
        //      else
        //      {
        //              bucket_range0 = scenario.validate_bottom_bucket;
        //              bucket_range1 = scenario.validate_top_bucket + 1;
        //      }

        //      double period_radius = (partial_mode ? config.age_radius_generate : config.age_radius_dump) * config.generate_time_periods;
        //      double bucket_radius = (partial_mode ? config.bucket_radius_generate : config.bucket_radius_dump);
        //      double smooth_radius_squared = period_radius * bucket_radius;
        //      int lower_period = (partial_mode ? 0 : -(int) Math.ceil(3 * period_radius));
        //      int upper_period = (int) Math.ceil(3 * period_radius);
        //      int lower_bucket = -(int) Math.ceil(3 * bucket_radius);
        //      int upper_bucket = (int) Math.ceil(3 * bucket_radius);
        //      double[][] a_weights = new double[upper_period - lower_period + 1][upper_bucket - lower_bucket + 1];
        //      for (int a = lower_period; a < upper_period + 1; a++)
        //      {
        //              for (int b = lower_bucket; b < upper_bucket + 1; b++)
        //              {
        //                      double weight;
        //                      if (smooth_radius_squared == 0)
        //                              weight = 1.0;
        //                      else
        //                              weight = Math.exp(-(a * a + b * b) / (2 * smooth_radius_squared)); // Gaussian blur.
        //                      a_weights[a - lower_period][b - lower_bucket] = weight;
        //              }
        //      }
        //      for (int smooth_bucket = bucket_range0; smooth_bucket < bucket_range1; smooth_bucket++)
        //      {
        //          double[] aa_smooth = new double[scenario.normal_assets];
        //              double contrib_smooth = 0.0;
        //              double weights = 0.0;
        //              for (int a = lower_period; a < upper_period + 1; a++)
        //              {
        //                      int pi = period + a;
        //                      if (pi < 0 || pi >= map.length)
        //                              continue;
        //                      MapElement[] map_period_plus_a = map[pi];

        //                      for (int b = lower_bucket; b < upper_bucket + 1; b++)
        //                      {
        //                              int bi = smooth_bucket - bucket_range0 + b;
        //                              if (bi < 0 || bi >= map_period_plus_a.length)
        //                                      continue;
        //                              MapElement fpb = map_period_plus_a[bi];
        //                              double weight = a_weights[a - lower_period][b - lower_bucket];
        //                              double[] raw_aa = fpb.raw_aa;
        //                              for (int index = 0; index < aa_smooth.length; index++)
        //                              {
        //                                      aa_smooth[index] += weight * raw_aa[index];
        //                              }
        //                              contrib_smooth += weight * fpb.raw_contrib;
        //                              weights += weight;
        //                      }
        //              }
        //              MapElement fpb = map[period][smooth_bucket - bucket_range0];
        //              for (int i = 0; i < aa_smooth.length; i++)
        //              {
        //                      aa_smooth[i] /= weights;
        //              }
        //              for (double allocation : aa_smooth)
        //              {
        //                      assert(-config.max_borrow - 1e-6 <= allocation && allocation <= 1.0 + config.max_borrow + 1e-6);
        //              }
        //              assert(-1e-6 < 1.0 - Utils.sum(aa_smooth) && 1.0 - Utils.sum(aa_smooth) < 1e-6);
        //              contrib_smooth /= weights;
        //              fpb.aa = aa_smooth;
        //              fpb.contrib = contrib_smooth;
        //      }
        // }
}
