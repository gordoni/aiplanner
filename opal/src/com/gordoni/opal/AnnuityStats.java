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
        private VitalStats vital_stats;

        private double time_periods = Double.NaN;
        private String table = null;

        private void dump_rcmt_params() throws IOException
        {
                PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-rcmt-params.csv"));
                out.println("date");
                out.println(config.annuity_real_yield_curve);
                out.close();
        }

        private Map<Double, Double> real_yield_curve = null;

        private void load_rcmt() throws IOException
        {
                real_yield_curve = new HashMap<Double, Double>();

                BufferedReader in = new BufferedReader(new FileReader(new File(ss.cwd + "/" + config.prefix + "-rcmt.csv")));
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
                        real_yield_curve.put(years, spot_yield * 2);
                        if (years > 0)
                                discount_rate_sum += discount_rate;
                }

                in.close();
        }

        private void rcmt() throws IOException, InterruptedException // R-CMT = real - constant maturity treasuries.
        {
                dump_rcmt_params();

                ss.subprocess("real_yield_curve.R", config.prefix);

                load_rcmt();
        }

        private void pre_compute_annuity_le(VitalStats vital_stats)
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

        public double rcmt_get(double maturity)
        {
                maturity = Math.max(0, maturity);
                maturity = Math.min(maturity, 30);
                return Math.pow(1 + real_yield_curve.get(maturity) / 2, 2) - 1; // Treasury quotes are semi-annual values.
        }

        public double hqm_get(double maturity)
        {
                maturity = Math.max(0.5, maturity);
                maturity = Math.min(maturity, 30); // Data goes up to 100, but cap because bonds not readily available.
                double nominal_rate = 0;
                int matches = 0;
                for (String k : hist.hqm.keySet())
                {
                        if (k.matches(config.annuity_nominal_yield_curve))
                        {
                                nominal_rate += hist.hqm.get(k).get(maturity);
                                matches++;
                        }
                }
                return Math.pow(1 + nominal_rate / matches / 2, 2) - 1; // Treasury quotes are semi-annual values.
        }

        private void pre_compute_annuity_price(VitalStats vital_stats)
        {
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
                        Double[] annuitant_death = vital_stats.death.clone();
                        Double[] period_death = vital_stats.death.clone();
                        for (int j = 0; j < period_death.length; j++)
                        {
                                assert(config.sex2 == null);
                                double maturity = (j - i) / time_periods - config.start_age;
                                double good_health_discount = 1;
                                if (maturity >= 0)
                                {
                                        if (config.annuity_contract_years.equals("aer2005_08"))
                                        {
                                                assert(config.annuity_table.equals("iam2012-basic-period"));
                                                List<Double> aer2005_08 = config.sex.equals("male") ? hist.soa_aer2005_08_m : hist.soa_aer2005_08_f;
                                                double contract_length = Math.min(maturity, aer2005_08.size() - 1);
                                                good_health_discount = aer2005_08.get((int) contract_length);
                                        }
                                        else if (config.annuity_contract_years.equals("healthy_decay"))
                                        {
                                                good_health_discount = 1 - config.annuity_healthy * Math.pow(config.annuity_healthy_decay, maturity);
                                        }
                                        else
                                        {
                                                assert(config.annuity_contract_years.equals("none"));
                                        }
                                }
                                annuitant_death[j] = good_health_discount * annuitant_death[j];
                                double rate = vital_stats.mortality_projection(config.sex, (int) (j / time_periods));
                                double cohort_to_cohort = Math.pow(1 - rate, - i / time_periods); // Back up earlier projection in VitalStats.get().
                                period_death[j] = Math.min(cohort_to_cohort * good_health_discount * period_death[j], 1); // Values j < i don't matter so long as valid.
                        }
                        double[] annuitant_alive = new double[vital_stats.alive.length];
                        double[] period_alive = new double[vital_stats.alive.length];
                        vital_stats.pre_compute_alive_dying(annuitant_death, annuitant_alive, null, null, null, time_periods, 0);
                        vital_stats.pre_compute_alive_dying(period_death, period_alive, null, null, null, time_periods, 0);
                        double ra_price = config.annuity_payout_immediate * annuitant_alive[i];
                        double na_price = config.annuity_payout_immediate * annuitant_alive[i];
                        double period_ra_price = config.annuity_payout_immediate * period_alive[i];
                        double period_na_price = config.annuity_payout_immediate * period_alive[i];
                        for (int j = i + 1; j < vital_stats.alive.length; j++)
                        {
                                double maturity = (j - i) / time_periods;
                                double avg_alive = annuitant_alive[j];
                                double period_avg_alive = period_alive[j];
                                double real_rate;
                                if (config.annuity_real_yield_curve == null)
                                        real_rate = config.annuity_real_rate;
                                else
                                        real_rate = rcmt_get(maturity) + config.annuity_real_yield_curve_adjust;
                                double real_tr = Math.pow(1 + real_rate, maturity);
                                if (maturity > config.annuity_real_long_years)
                                        real_tr *= Math.pow(1 - config.annuity_real_long_penalty, maturity - config.annuity_real_long_years);
                                ra_price += avg_alive / real_tr;
                                period_ra_price += period_avg_alive / real_tr;
                                double nominal_rate;
                                if (config.annuity_nominal_yield_curve == null)
                                        nominal_rate = config.annuity_nominal_rate;
                                else
                                        nominal_rate = hqm_get(maturity) + config.annuity_nominal_yield_curve_adjust;
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
                        this.synthetic_real_annuity_price[i] = ra_price / (annuitant_alive[i] * time_periods * real_mwr);
                        this.synthetic_nominal_annuity_price[i] = na_price / (annuitant_alive[i] * time_periods * nominal_mwr);
                        this.period_real_annuity_price[i] =  period_ra_price / (period_alive[i] * time_periods * real_mwr);
                        this.period_nominal_annuity_price[i] = period_na_price / (period_alive[i] * time_periods * nominal_mwr);
                        double real_annuity_price_male[] = hist.real_annuity_price.get(config.annuity_real_quote + "-male");
                        double real_annuity_price_female[] = hist.real_annuity_price.get(config.annuity_real_quote + "-female");
                        if (config.sex.equals("male") && (int) age < real_annuity_price_male.length)
                                this.actual_real_annuity_price[i] = real_annuity_price_male[(int) age];
                        else if (config.sex.equals("female") && (int) age < real_annuity_price_female.length)
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
                        if (config.annuity_nominal_synthetic)
                                this.nominal_annuity_price[i] = this.synthetic_nominal_annuity_price[i];
                        else
                                this.nominal_annuity_price[i] = this.actual_nominal_annuity_price[i];
                }
        }

        public AnnuityStats(ScenarioSet ss, Config config, HistReturns hist, VitalStats vital_stats) throws IOException, InterruptedException
        {
                this.ss = ss;
                this.config = config;
                this.hist = hist;
                this.vital_stats = vital_stats;

                if (config.annuity_real_yield_curve != null)
                        rcmt();
        }

        public void compute_stats(double time_periods, String table)
        {
                if (config.sex2 != null)
                        return;

                this.time_periods = time_periods;

                boolean regenerated = vital_stats.compute_stats(table);

                if (regenerated)
                {
                        pre_compute_annuity_le(vital_stats);
                        pre_compute_annuity_price(vital_stats);
                }
        }
}
