package com.gordoni.opal;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.InputStream;
import java.io.IOException;
import java.lang.ProcessBuilder.Redirect;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ScenarioSet
{
	public ExecutorService executor;

        public int max_years = -1;
        public String cwd;

        public VitalStats generate_stats;
        public VitalStats validate_stats;
        private VitalStats generate_stats_annuity;
        private VitalStats validate_stats_annuity;
        public AnnuityStats generate_annuity_stats;
        public AnnuityStats validate_annuity_stats;

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

        public ScenarioSet(Config config, HistReturns hist, String cwd, Map<String, Object> params, String param_filename) throws ExecutionException, IOException, InterruptedException
        {
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
		generate_stats_annuity = new VitalStats(this, config, hist, config.generate_time_periods);
		generate_annuity_stats = new AnnuityStats(this, config, hist, generate_stats_annuity);
		generate_annuity_stats.compute_stats(config.generate_time_periods, config.annuity_table);
		validate_stats_annuity = new VitalStats(this, config, hist, config.validate_time_periods);
		validate_annuity_stats = new AnnuityStats(this, config, hist, validate_stats_annuity);
		validate_annuity_stats.compute_stats(config.validate_time_periods, config.annuity_table);

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
			compare_scenario = new Scenario(this, config, hist, asset_classes, asset_classes, null, null);
		}

	        Scenario scenario = new Scenario(this, config, hist, config.asset_classes, config.asset_class_names, config.start_ria, config.start_nia);
		scenario.report_returns();

		if (do_compare)
		        compare_scenario.run_mvo("compare"); // Helps determine max_stocks based on risk tolerance.
		scenario.run_mvo("scenario");

		executor = Executors.newFixedThreadPool(config.workers);
		try
		{
		        if (do_compare)
		            compare_scenario.run_compare();

			scenario.run_main();
		}
		catch (Exception | AssertionError e)
		{
		        executor.shutdownNow();
			throw e;
		}
		executor.shutdown();
	}
}
