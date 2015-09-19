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
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.InputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.lang.ProcessBuilder.Redirect;
import java.text.DecimalFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.apache.commons.math3.distribution.ChiSquaredDistribution;
import org.apache.commons.math3.random.JDKRandomGenerator;

public class ScenarioSet
{
        public ExecutorService executor;

        private Config config;
        public int max_years = -1;
        public String cwd;

        public VitalStats generate_stats;
        public VitalStats validate_stats;
        public AnnuityStats generate_annuity_stats;
        public AnnuityStats validate_annuity_stats;

        private static DecimalFormat f1f = new DecimalFormat("0.0");
        private static DecimalFormat f2f = new DecimalFormat("0.00");
        private static DecimalFormat f4f = new DecimalFormat("0.0000");

        public void subprocess(String cmd, String prefix) throws IOException, InterruptedException
        {
                String real_cwd = System.getProperty("user.dir");
                ProcessBuilder pb = new ProcessBuilder(real_cwd + "/" + cmd);
                Map<String, String> env = pb.environment();
                env.put("OPAL_FILE_PREFIX", cwd + "/" + prefix);
                pb.redirectError(Redirect.INHERIT);
                Process p = pb.start();

                InputStream stdout = p.getInputStream();
                byte buf[] = new byte[8192];
                while (stdout.read(buf) != -1)
                {
                }
                p.waitFor();
                assert(p.exitValue() == 0);
        }

        private void dump_error(Scenario scenario, Scenario[] error_scenario, String signif, double significance) throws IOException
        {
                assert(error_scenario[0].start_p.length == 1); // No annuities.
                PrintWriter out = new PrintWriter(new FileWriter(new File(cwd + "/" + config.prefix + "-error-" + signif + ".csv")));
                for (int i = 0; i < scenario.map.map.length; i++)
                {
                        double age_period = i + config.start_age * config.generate_time_periods;
                        for (int step = 0; step < config.gnuplot_steps + 1; step++)
                        {
                                double age = age_period / config.generate_time_periods;
                                double curr_pf = (config.gnuplot_steps - step) * scenario.tp_max / config.gnuplot_steps;
                                double[] p = new double[1];
                                p[scenario.tp_index] = curr_pf;

                                MapElement me_s = scenario.map.lookup_interpolate(p, i);

                                double[][] aa_array = new double[error_scenario.length][];
                                double[] consume_array = new double[error_scenario.length];
                                for (int e = 0; e < error_scenario.length; e++)
                                {
                                        MapElement me = error_scenario[e].map.lookup_interpolate(p, i);
                                        aa_array[e] = me.aa;
                                        consume_array[e] = me.consume;
                                }

                                double[][] allocs = Utils.zipDoubleArrayArray(aa_array);
                                double[] aa_error = new double[scenario.normal_assets];
                                int low = (int) ((1 - significance) / 2 * (error_scenario.length - 1));
                                int high = low + (int) (Math.round(significance * (error_scenario.length - 1)));
                                for (int a = 0; a < scenario.normal_assets; a++)
                                {
                                        Arrays.sort(allocs[a]);
                                        aa_error[a] = allocs[a][high] - allocs[a][low];
                                }
                                Arrays.sort(consume_array);
                                double consume_diff = consume_array[high] - consume_array[low];
                                double consume_error = 0.0;
                                if (consume_diff > 0)
                                        consume_error = (me_s.consume == 0.0 ? 1e6 : consume_diff / me_s.consume);

                                String aa_str = scenario.stringify_aa(aa_error);
                                out.print(f2f.format(age));
                                out.print("," + f2f.format(curr_pf));
                                out.print("," + f4f.format(consume_error));
                                out.print(","); // Reserve space for ria and nia.
                                out.print(",");
                                out.print("," + aa_str);
                                out.print("\n");
                        }
                        out.print("\n");
                }
                out.close();
        }

        public ScenarioSet(Config config, HistReturns hist, String cwd, Map<String, Object> params, String param_filename) throws ExecutionException, IOException, InterruptedException
        {
                this.config = config;
                this.cwd = cwd;

                // Override default scenario based on scenario file.
                boolean param_filename_is_default = (param_filename == null);
                if (param_filename_is_default)
                        param_filename = config.prefix + "-scenario.txt";

                File f = new File(cwd + '/' + param_filename);
                if (!f.exists())
                {
                        if (!param_filename_is_default)
                                throw new FileNotFoundException(param_filename);
                }
                else
                {
                        BufferedReader reader = new BufferedReader( new FileReader (f));
                        StringBuilder stringBuilder = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null)
                        {
                                stringBuilder.append(line);
                                stringBuilder.append(System.getProperty("line.separator"));
                        }
                        Map<String, Object> fParams = new HashMap<String, Object>();
                        config.load_params(fParams, stringBuilder.toString());
                        config.applyParams(fParams);
                }

                // Override default scenario based on command line arguments.
                if (params != null)
                        config.applyParams(params);

                generate_stats = new VitalStats(this, config, hist, config.generate_time_periods);
                generate_stats.compute_stats(config.generate_life_table); // Compute here so we can access death.length.
                validate_stats = new VitalStats(this, config, hist, config.validate_time_periods);
                validate_stats.compute_stats(config.validate_life_table);
                generate_annuity_stats = new AnnuityStats(this, config, hist, generate_stats, config.generate_time_periods, config.annuity_table);
                validate_annuity_stats = new AnnuityStats(this, config, hist, validate_stats, config.validate_time_periods, config.annuity_table);

                System.out.println("Parameters:");
                config.dumpParams();
                System.out.println();

                boolean do_compare = !config.skip_compare;

                Scenario compare_scenario = null;
                if (do_compare)
                {
                        assert(config.tax_rate_div == null);
                        assert(!config.ef.equals("none"));
                        List<String> asset_classes = new ArrayList<String>(Arrays.asList("stocks", "bonds"));
                        compare_scenario = new Scenario(this, config, hist, false, !config.skip_validate, asset_classes, asset_classes, config.ret_equity_premium, 1, null, null);
                }

                Scenario scenario = new Scenario(this, config, hist, config.compute_risk_premium, !config.skip_validate, config.asset_classes, config.asset_class_names, config.ret_equity_premium, 1, config.start_ria, config.start_nia);
                scenario.report_returns();

                if (config.compute_risk_premium)
                        return;

                Scenario[] error_scenario = new Scenario[config.error_count];
                if (config.error_count > 0)
                {
                        List<String> asset_classes = new ArrayList<String>(Arrays.asList("stocks", "bonds"));
                        Scenario risk_premium_scenario = new Scenario(this, config, hist, true, false, asset_classes, asset_classes, config.ret_equity_premium, 1, config.start_ria, config.start_nia);
                        List<double[]> rp_returns = Utils.zipDoubleArray(risk_premium_scenario.returns_generate.original_data);
                        double n = rp_returns.get(0).length;
                        double sample_erp_am = Utils.mean(rp_returns.get(0));
                        double sample_erp_sd = Utils.standard_deviation(rp_returns.get(0));

                        JDKRandomGenerator random = new JDKRandomGenerator();
                        random.setSeed(0);
                        ChiSquaredDistribution chi_squared = new ChiSquaredDistribution(random, n - 1);
                        for (int i = 0; i < error_scenario.length; i++)
                        {
                                double population_erp_am = sample_erp_am;
                                double equity_vol_adjust = Math.sqrt((n - 1) / chi_squared.sample());
                                double population_erp_sd = sample_erp_sd * equity_vol_adjust;
                                double erp_am = population_erp_am;
                                double erp_sd = population_erp_sd / Math.sqrt(n);
                                double erp = erp_am + erp_sd * random.nextGaussian();
                                error_scenario[i] = new Scenario(this, config, hist, false, false, config.asset_classes, config.asset_class_names, erp, equity_vol_adjust, config.start_ria, config.start_nia);
                        }
                }

                if (do_compare)
                        compare_scenario.run_mvo("compare"); // Helps determine max_stocks based on risk tolerance.
                scenario.run_mvo("scenario");
                for (int i = 0; i < error_scenario.length; i++)
                        error_scenario[i].run_mvo("error");

                executor = Executors.newFixedThreadPool(config.workers);
                try
                {
                        if (do_compare)
                                compare_scenario.run_compare();

                        scenario.run_main();

                        if (error_scenario.length > 0)
                        {
                                long start = System.currentTimeMillis();

                                for (int i = 0; i < error_scenario.length; i++)
                                {
                                        if (config.trace)
                                                System.out.println("error scenario " + (i + 1));
                                        error_scenario[i].run_error();
                                }
                                dump_error(scenario, error_scenario, "0.68", 0.68);
                                dump_error(scenario, error_scenario, "0.95", 0.95);

                                double elapsed = (System.currentTimeMillis() - start) / 1000.0;
                                System.out.println("Error done: " + f1f.format(elapsed) + " seconds");
                                System.out.println();
                        }
                }
                catch (Exception | AssertionError e)
                {
                        executor.shutdownNow();
                        throw e;
                }
                executor.shutdown();
        }
}
