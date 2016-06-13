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
import java.io.IOException;
import java.io.PrintWriter;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class AnnuityStats
{
        public int[] annuity_le = new int[0];

        public double[] synthetic_real_annuity_price = new double[0];
        public double[] synthetic_nominal_annuity_price = new double[0];
        public double[] period_real_annuity_price = new double[0];
        public double[] period_nominal_annuity_price = new double[0];
        public double[] actual_real_annuity_price = new double[0];
        public double[] actual_nominal_annuity_price = new double[0];
        public double[] real_annuity_price = new double[0];
        public double[] nominal_annuity_price = new double[0];

        private ScenarioSet ss;
        private Config config;
        private HistReturns hist;

        private String table = null;

        public int yield_curve_years;

        private Map<Double, Double> real_yield_curve = null;
        private Map<Double, Double> nominal_treasury_yield_curve = null;

        private Map<Double, Double> load_treasury(String bond_type) throws IOException
        {
                Map<Double, Double> yield_curve = new HashMap<Double, Double>();

                BufferedReader in = new BufferedReader(new FileReader(new File(ss.cwd + "/" + config.prefix + "-yield_curve-" + bond_type + ".csv")));
                String line = in.readLine();
                double discount_rate_sum = 0;
                while ((line = in.readLine()) != null)
                {
                        String[] fields = line.split(",", -1);
                        double years = Double.parseDouble(fields[0]);
                        double yield = Double.parseDouble(fields[1]) / 100;
                        double coupon_yield = yield / 2;
                        double discount_rate = (1 - coupon_yield * discount_rate_sum) / (1 + coupon_yield);
                        double spot_yield = years == 0 ? 0 : Math.pow(discount_rate, - 1 / (2 * years)) - 1;
                        yield_curve.put(years, spot_yield * 2);
                        if (years > 0)
                                discount_rate_sum += discount_rate;
                }

                in.close();

                return yield_curve;
        }

        private Map<Double, Double> treasury(String bond_type, int yield_curve_years) throws IOException, InterruptedException
        {

                String yield_curve_date = (bond_type.equals("real") ? config.annuity_real_yield_curve : config.annuity_nominal_treasury_yield_curve);
                String year = yield_curve_date.substring(0, yield_curve_date.indexOf("-"));
                String dir = hist.find_subdir(bond_type.equals("real") ? "rcmt" : "cmt"); // R-CMT = real - constant maturity treasuries.
                String fname = dir + "/" + bond_type + "-" + year + ".csv";
                String outname = ss.cwd + "/" + config.prefix + "-yield_curve-" + bond_type + ".csv";
                ss.subprocess("yield_curve.R", config.prefix, "--args", fname, yield_curve_date, outname);

                Map<Double, Double> yield_curve = load_treasury(bond_type);

                return project_curve(yield_curve, 15, yield_curve_years); // Treasury method: project using average forward rate beyond 15 years.
        }

        private Map<Double, Double> spots_to_forwards(Map<Double, Double> spots)
        {
                Map<Double, Double> forwards = new HashMap<Double, Double>();
                forwards.put(0.0, 0.0);
                int count = 0;
                double old_spot_rate = 0;
                for (double maturity = 0.5; spots.containsKey(maturity); maturity += 0.5)
                {
                        count++;
                        double new_spot_rate = spots.get(maturity) / 2;
                        double forward_rate = Math.pow(1 + new_spot_rate, count) / Math.pow(1 + old_spot_rate, count - 1);
                        forwards.put(maturity, (forward_rate - 1) * 2);
                        old_spot_rate = new_spot_rate;
                }

                return forwards;
        }

        private Map<Double, Double> forwards_to_spots(Map<Double, Double> forwards)
        {
                Map<Double, Double> spots = new HashMap<Double, Double>();
                spots.put(0.0, 0.0);
                int count = 0;
                double spot_rate = 1;
                for (double maturity = 0.5; forwards.containsKey(maturity); maturity += 0.5)
                {
                        count++;
                        double forward_rate = 1 + forwards.get(maturity) / 2;
                        spot_rate = Math.pow(forward_rate * Math.pow(spot_rate, count - 1), 1.0 / count);
                        spots.put(maturity, (spot_rate - 1) * 2);
                }

                return spots;
        }

        private Map<Double, Double> project_curve(Map<Double, Double> spots, int start_year, int yield_curve_years)
        {
                Map<Double, Double> forwards = spots_to_forwards(spots);

                double count = 0;
                double sum = 0;
                double maturity = start_year;
                for (; forwards.containsKey(maturity); maturity += 0.5)
                {
                        count++;
                        sum += forwards.get(maturity);
                }
                double avg_rate = sum / count;

                for (; maturity < yield_curve_years; maturity += 0.5)
                {
                        forwards.put(maturity, avg_rate);
                }

                return forwards_to_spots(forwards);
        }

        private Map<Double, Double> nominal_corporate_yield_curve = null;

        private void hqm()
        {
                nominal_corporate_yield_curve = new HashMap<Double, Double>();

                for (double maturity = 0.5; maturity <= 100.0; maturity += 0.5)
                {
                        double sum_nominal_rate = 0;
                        int matches = 0;
                        for (String k : hist.hqm.keySet())
                        {
                                if (k.matches(config.annuity_nominal_corporate_yield_curve))
                                {
                                        sum_nominal_rate += hist.hqm.get(k).get(maturity);
                                        matches++;
                                }
                        }
                        assert(matches > 0);
                        nominal_corporate_yield_curve.put(maturity, sum_nominal_rate / matches);
                }
        }

        private void pre_compute_annuity_le(VitalStats vital_stats, double time_periods)
        {
                if (config.tax_rate_annuity == 0)
                        return;
                assert(config.sex2 == null);

                this.annuity_le = new int[vital_stats.dying.length];
                for (int i = 0; i < this.annuity_le.length; i++)
                {
                        int le_index = config.start_age + (int) (i / time_periods);
                        this.annuity_le[i] = Math.max((int) Math.round(hist.annuity_le[Math.min(le_index, hist.annuity_le.length - 1)] * time_periods), 1);
                }
        }

        public double get_rate(String bond_type, double maturity)
        {
                maturity = Math.round(maturity * 2) / 2.0; // Quotes are semi-annual.
                Map<Double, Double> yield_curve = null;
                double adjust = 0;
                if (bond_type.equals("real"))
                {
                        if (config.annuity_real_yield_curve == null)
                                return config.annuity_real_rate;
                        maturity = Math.max(0, maturity);
                        yield_curve = real_yield_curve;
                        adjust = config.annuity_real_yield_curve_adjust;
                }
                else if (bond_type.equals("nominal"))
                {
                        if (config.annuity_nominal_treasury_yield_curve == null)
                                return config.annuity_nominal_rate;
                        maturity = Math.max(0, maturity);
                        yield_curve = nominal_treasury_yield_curve;
                        adjust = config.annuity_nominal_treasury_yield_curve_adjust;
                }
                else if (bond_type.equals("corporate"))
                {
                        if (config.annuity_nominal_corporate_yield_curve == null)
                                return config.annuity_nominal_rate;
                        maturity = Math.max(0.5, maturity);
                        maturity = Math.min(maturity, 100); // Might want to cap at 30 because longer bonds not readily available.
                        yield_curve = nominal_corporate_yield_curve;
                        adjust = config.annuity_nominal_corporate_yield_curve_adjust;
                }
                else
                        assert(false);
                return Math.pow(1 + yield_curve.get(maturity) / 2, 2) - 1 + adjust; // Treasury quotes are semi-annual values.
        }

        private void pre_compute_annuity_price(VitalStats vital_stats, double time_periods)
        {
                assert(config.sex2 == null);

                this.synthetic_real_annuity_price = new double[vital_stats.dying.length];
                this.synthetic_nominal_annuity_price = new double[vital_stats.dying.length];
                this.period_real_annuity_price = new double[vital_stats.dying.length];
                this.period_nominal_annuity_price = new double[vital_stats.dying.length];
                this.actual_real_annuity_price = new double[vital_stats.dying.length];
                this.actual_nominal_annuity_price = new double[vital_stats.dying.length];
                this.real_annuity_price = new double[vital_stats.dying.length];
                this.nominal_annuity_price = new double[vital_stats.dying.length];

                for (int i = 0; i < vital_stats.alive.length - 1; i++)
                {
                        Double[] annuitant_death = vital_stats.get_q(table, config.sex, vital_stats.get_birth_year(config.start_age), 0, config.start_age + i, true, 1);
                        Double[] period_death = vital_stats.get_q(table, config.sex, vital_stats.get_birth_year(config.start_age) - i, 0, config.start_age + i, true, 1);
                        int annuitant_alive_len = (int) Math.round((annuitant_death.length - config.start_age) * config.annuity_time_periods) + 1;
                        double[] annuitant_alive = new double[annuitant_alive_len];
                        double[] period_alive = new double[annuitant_alive_len];
                        vital_stats.pre_compute_alive_dying(annuitant_death, annuitant_alive, null, null, null, config.annuity_time_periods, 0);
                        vital_stats.pre_compute_alive_dying(period_death, period_alive, null, null, null, config.annuity_time_periods, 0);
                        int first_index = (int) Math.round(i * config.annuity_time_periods / time_periods);
                        double ra_price = 0;
                        double na_price = 0;
                        double period_ra_price = 0;
                        double period_na_price = 0;
                        for (int j = 0;; j++)
                        {
                                double maturity = config.annuity_payout_delay / 12 + j / config.annuity_time_periods;
                                double d_index = first_index + maturity * config.annuity_time_periods;  // bucket is age nearest.
                                int index = (int) (d_index);
                                double fract = d_index % 1;
                                if (index + 1 >= annuitant_alive.length)
                                        break;
                                double avg_alive = (1 - fract) * annuitant_alive[index] + fract * annuitant_alive[index + 1];
                                double period_avg_alive = (1 - fract) * period_alive[index] + fract * period_alive[index + 1];
                                double real_rate = get_rate("real", maturity);
                                double real_tr = Math.pow(1 + real_rate, maturity);
                                if (maturity > config.annuity_real_long_years)
                                        real_tr *= Math.pow(1 - config.annuity_real_long_penalty, maturity - config.annuity_real_long_years);
                                ra_price += avg_alive / real_tr;
                                period_ra_price += period_avg_alive / real_tr;
                                double nominal_rate = 0;
                                if (!config.annuity_nominal_type.equals("actual"))
                                        nominal_rate = get_rate(config.annuity_nominal_type, maturity);
                                double nominal_tr = Math.pow(1 + nominal_rate, Math.min(maturity, config.annuity_nominal_long_years));
                                if (maturity > config.annuity_nominal_long_years)
                                {
                                        double remaining_rate = (1 + nominal_rate) * (1 - config.annuity_nominal_long_penalty);
                                        if (remaining_rate > 1) // Else able to hold cash.
                                                nominal_tr *= Math.pow(remaining_rate, maturity - config.annuity_nominal_long_years);
                                }
                                na_price += avg_alive / nominal_tr;
                                period_na_price += period_avg_alive / nominal_tr;
                        }
                        double age = config.start_age + i / time_periods;
                        double real_mwr = config.annuity_real_mwr1 + (age - config.annuity_mwr_age1) * (config.annuity_real_mwr2 - config.annuity_real_mwr1) / (config.annuity_mwr_age2 - config.annuity_mwr_age1);
                        double nominal_mwr = config.annuity_nominal_mwr1 + (age - config.annuity_mwr_age1) * (config.annuity_nominal_mwr2 - config.annuity_nominal_mwr1) / (config.annuity_mwr_age2 - config.annuity_mwr_age1);
                        this.synthetic_real_annuity_price[i] = ra_price / (annuitant_alive[first_index] * config.annuity_time_periods * real_mwr);
                        this.synthetic_nominal_annuity_price[i] = na_price / (annuitant_alive[first_index] * config.annuity_time_periods * nominal_mwr);
                        this.period_real_annuity_price[i] =  period_ra_price / (period_alive[first_index] * config.annuity_time_periods * real_mwr);
                        this.period_nominal_annuity_price[i] = period_na_price / (period_alive[first_index] * config.annuity_time_periods * nominal_mwr);
                        double real_annuity_price_male[] = hist.real_annuity_price.get(config.annuity_real_quote + "-male");
                        double real_annuity_price_female[] = hist.real_annuity_price.get(config.annuity_real_quote + "-female");
                        if (config.sex.equals("male") && real_annuity_price_male != null && (int) age < real_annuity_price_male.length)
                                this.actual_real_annuity_price[i] = real_annuity_price_male[(int) age];
                        else if (config.sex.equals("female") && real_annuity_price_female != null && (int) age < real_annuity_price_female.length)
                                this.actual_real_annuity_price[i] = real_annuity_price_female[(int) age];
                        else
                                this.actual_real_annuity_price[i] = Double.POSITIVE_INFINITY;
                        double nominal_annuity_price_male[] = hist.nominal_annuity_price.get(config.annuity_nominal_quote + "-male");
                        double nominal_annuity_price_female[] = hist.nominal_annuity_price.get(config.annuity_nominal_quote + "-female");
                        if (config.sex.equals("male") && (int) age < nominal_annuity_price_male.length)
                                this.actual_nominal_annuity_price[i] = nominal_annuity_price_male[(int) age];
                        else if (config.sex.equals("female") && (int) age < nominal_annuity_price_female.length)
                                this.actual_nominal_annuity_price[i] = nominal_annuity_price_female[(int) age];
                        else
                                this.actual_nominal_annuity_price[i] = Double.POSITIVE_INFINITY;
                        if (config.annuity_real_synthetic)
                                this.real_annuity_price[i] = this.synthetic_real_annuity_price[i];
                        else
                                this.real_annuity_price[i] = this.actual_real_annuity_price[i];
                        if (!config.annuity_nominal_type.equals("actual"))
                                this.nominal_annuity_price[i] = this.synthetic_nominal_annuity_price[i];
                        else
                                this.nominal_annuity_price[i] = this.actual_nominal_annuity_price[i];
                }
        }

        public AnnuityStats(ScenarioSet ss, Config config, HistReturns hist, VitalStats vital_stats, double time_periods, String table) throws IOException, InterruptedException
        {
                this.ss = ss;
                this.config = config;
                this.hist = hist;
                // vital_stats and time_periods only used for scaling the resulting annuity_le and annuity_price arrays.
                this.table = table;

                this.yield_curve_years = vital_stats.get_q(table, config.sex, vital_stats.get_birth_year(config.start_age), 0, config.start_age, true, 1).length
                        - config.start_age;
                        // Beautiful waste. We need the annuitant life table size to know how many yield curve values to generate.
                if (config.annuity_real_yield_curve != null) // Don't slow down by invoking R if not needed.
                    real_yield_curve = treasury("real", this.yield_curve_years);
                if (config.annuity_nominal_treasury_yield_curve != null)
                        nominal_treasury_yield_curve = treasury("nominal", this.yield_curve_years);
                hqm();

                if (config.sex2 != null)
                        return;

                pre_compute_annuity_le(vital_stats, time_periods);
                pre_compute_annuity_price(vital_stats, time_periods);
        }
}
