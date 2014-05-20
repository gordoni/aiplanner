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
        public Utility utility_consume;
        public Utility utility_consume_time;
        public Utility utility_inherit;
	public List<double[]> aa_ef;
        protected HistReturns hist;
        public List<String> asset_classes;
        public String vw_strategy;

        public double[] start_p;
        public Integer tp_index;
        public Integer ria_index;
        public Integer nia_index;

        public int normal_assets;
        public int ria_aa_index;
        public int nia_aa_index;
        public int spend_fract_index;
        public int all_alloc;
        public int cpi_index;
        public int ef_index;

        public double[] dividend_yield;
        public List<double[]> at_returns;

	public int generate_bottom_bucket;	// Generate data all the way down to the floor.
	public int generate_top_bucket;	// Generate data all the way up to the ceiling.
	public int validate_bottom_bucket;	// Report data all the way down to the validate floor.
	public int validate_top_bucket;	// Report data all the way up to the validate ceiling.

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
		if (config.min_safe_le != 0)
		{
		        // Not entirely satisfying to fully or partially decrement asset class when it was requested that it be incremented,
		        // but this is the simplest approach and it shouldn't affect the underlying asset allocation machinery.
		        int a_safe = asset_classes.indexOf(config.safe_aa);
			double alloc_safe = new_aa[a_safe];
			double min_safe = config.min_safe_le * (ss.vital_stats.raw_sum_avg_alive[period] / ss.vital_stats.raw_alive[period]) / p[tp_index];
			min_safe = Math.min(1, min_safe);
			double delta_safe = Math.max(0, min_safe - alloc_safe);
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

        public void dump_utility(Utility utility, String name) throws IOException
	{
		PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-utility-" + name + ".csv"));
		for (double c = 0; c <= utility.range; c += utility.range / 1000)
		{
		        out.print(f6f.format(c) + "," + utility.utility(c) + "," + utility.slope(c) + "," + utility.slope2(c) + "," + utility.inverse_utility(utility.utility(c)) + "," + utility.inverse_slope(utility.slope(c)) + "\n");
		}
		out.close();
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
	// 	PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-rps_initial-" + metric + ".csv"));
	// 	MapElement[] map_period = map.map[0];
	// 	for (int bucket = scenario.validate_bottom_bucket; bucket < scenario.validate_top_bucket + 1; bucket++)
	// 	{
	// 		MapElement fpb = map_period[bucket - scenario.validate_bottom_bucket];
	// 		double p = scale.bucket_to_pf(bucket);
	// 		if (!(0.0 <= p && p <= config.pf_validate))
	// 			continue;
	// 		double goal = success_lines[0][(int) Math.floor(p / config.success_lines_scale_size)].get(Metrics.to_enum(metric));
	// 		String aa = stringify_aa(fpb.aa);
	// 		out.print(f2f.format(p));
	// 		out.print(",");
	// 		out.print(f5f.format(goal));
	// 		out.print(",");
	// 		out.print(aa);
	// 		out.print("\n");
	// 	}
	// 	out.close();
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
        private void dump_aa_linear_slice(AAMap map, Returns returns, double[] slice, String slice_suffix) throws IOException
	{
		PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-linear" + slice_suffix + ".csv"));

		for (int i = 0; i < map.map.length; i++)
		{
		        double age_period = i + config.start_age * config.generate_time_periods;
 			for (int step = 0; step < config.gnuplot_steps + 1; step++)
			{
				double curr_pf = (config.gnuplot_steps - step) * config.pf_gnuplot / (double) config.gnuplot_steps;
				double[] p = slice.clone();
				p[tp_index] = curr_pf;
				MapElement fpb = map.lookup_interpolate(p, i);
				String metric = f5f.format(fpb.metric_sm);
				double[] aa = fpb.aa;
				String aa_str = stringify_aa(fpb.aa);
				out.print(f2f.format(age_period / config.generate_time_periods));
				out.print("," + f3f.format(curr_pf));
				out.print("," + metric);
				out.print("," + ((returns == null) ? "" : f4f.format(expected_return(aa, returns))));
				out.print("," + ((returns == null) ? "" : f4f.format(expected_standard_deviation(aa, returns))));
				//out.print("," + f3f.format(fpb.spend > 0 ? fpb.ria_purchase(this) / fpb.spend : 0));
				out.print("," + f3f.format(curr_pf > 0 ? fpb.ria_purchase(this) / curr_pf : 0));
				out.print("," + f2f.format(fpb.consume));
				//out.print("," + f3f.format(fpb.spend > 0 ? fpb.nia_purchase(this) / fpb.spend : 0));
				out.print("," + f3f.format(curr_pf > 0 ? fpb.nia_purchase(this) / curr_pf : 0));
				out.print("," + aa_str);
				out.print("\n");
			}
			out.print("\n");
		}
		out.close();
	}

        private void dump_aa_linear(AAMap map, Returns returns) throws IOException
        {
	    dump_aa_linear_slice(map, returns, new double[start_p.length], "");
	    // dump_aa_linear_slice(map, returns, new double[]{0, 10000}, "10000");
        }

        private double get_path_value(List<PathElement> path, int i, String what, boolean change)
        {
	        if (change)
		{
		        if (i > 0)
			{
			        double prev_value = get_path_value(path, i - 1, what, false);
				double curr_value = get_path_value(path, i, what, false);
				if (prev_value == 0 && curr_value == 0)
				        return 0;
				else
			                return curr_value / prev_value - 1;
			}
			else
			        return 0;
		}
		else
		{
		        PathElement elem = path.get(i);
			if (what.equals("p"))
				return elem.p;
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
			for (int i = start; i < path.size() - 1; i++)
			{
				double value = get_path_value(path, i, what, change);
				double weight;
				if (what.equals("inherit"))
				        weight = ss.vital_stats.dying[period];
				else
				        weight = (ss.vital_stats.alive[period] + ss.vital_stats.alive[period + 1]) / 2;
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
			for (int i = start; i < path.size() - 1; i++)
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
		dump_distribution(paths, "consume", false, true);
	        dump_distribution(paths, "inherit", false, false);

	        dump_distribution(paths, "p", true, false);
	        dump_distribution(paths, "consume", true, true);
	}

        private void dump_pct_path(List<List<PathElement>> paths, String what, boolean change) throws IOException
        {
	        PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-pct-" + (change ? "change-" : "") + what + ".csv"));

	        int pathlen = paths.get(0).size() - 1;
		double age_period = config.start_age * config.generate_time_periods;
		for (int i = 0; i < pathlen; i++)
		{
		        double[] vals = new double[config.max_pct_paths];
		        for (int j = 0; j < config.max_pct_paths; j++)
			{
			        List<PathElement> path = paths.get(j);
			        vals[j] = get_path_value(path, i, what, change);
			}
			Arrays.sort(vals);
			double pctl = 0.05 / 2;
			double low = vals[(int) (pctl * vals.length)];
			double median = vals[(int) (0.5 * vals.length)];
			double high = vals[(int) ((1 - pctl) * vals.length)];
			out.println(f2f.format(age_period / config.generate_time_periods) + "," + f4f.format(median) + "," + f4f.format(low) + "," + f4f.format(high));
			age_period++;
		}
		out.close();
	}

        private void dump_pct_paths(List<List<PathElement>> paths) throws IOException
        {
	    dump_pct_path(paths, "p", false);
	    dump_pct_path(paths, "consume", false);
	    for (int i = 0; i < normal_assets; i++)
		    dump_pct_path(paths, asset_classes.get(i), false);

	    dump_pct_path(paths, "p", true);
	    dump_pct_path(paths, "consume", true);
	}

	// Dump the paths taken.
	private void dump_paths(List<List<PathElement>> paths) throws IOException
	{
		PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-paths.csv"));

		double initial_period = config.start_age * config.generate_time_periods;
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

        // Only useful if invariant over portfolio size.
        private void dump_average(AAMap map) throws IOException
        {
		PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-average.csv"));

		for (int period = 0; period < map.map.length; period++)
		{
		        double age = config.start_age + period / config.generate_time_periods;
		        double ria = 0;
		        double nia = 0;
			double[] aa = new double[normal_assets];
			for (int step = 1; step <= config.gnuplot_steps; step++)
			        // step = 0 results in division by zero.
			{
			        double curr_pf = step * config.pf_gnuplot / (double) config.gnuplot_steps;
				double[] p = new double[start_p.length];
				p[tp_index] = curr_pf;
				MapElement fpb = map.lookup_interpolate(p, period);
				double ria_purchase = fpb.ria_purchase(this);
				double nia_purchase = fpb.nia_purchase(this);
				//double spend = fpb.spend;
				//ria += ria_purchase / spend;
				//nia += nia_purchase / spend;
				ria += ria_purchase / curr_pf;
				nia += nia_purchase / curr_pf;
				for (int a = 0; a < aa.length; a++)
				        aa[a] += fpb.aa[a];
			}
			ria /= config.gnuplot_steps;
			nia /= config.gnuplot_steps;
			for (int a = 0; a < aa.length; a++)
			        aa[a] /= config.gnuplot_steps;
			out.println(f2f.format(age) + "," + f3f.format(ria) + "," + f3f.format(nia) + "," + stringify_aa(aa));
		}
		out.close();
        }

        private void dump_annuity_price() throws IOException
        {
		PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-annuity_price.csv"));

		for (int i = 0; i < ss.annuity_stats.actual_real_annuity_price.length; i++)
		{
		        double age = config.start_age + i / config.generate_time_periods;
			out.println(f2f.format(age) + "," + f3f.format(ss.annuity_stats.actual_real_annuity_price[i]) + "," + f3f.format(ss.annuity_stats.period_real_annuity_price[i]) + "," + f3f.format(ss.annuity_stats.synthetic_real_annuity_price[i]) + "," + f3f.format(ss.annuity_stats.actual_nominal_annuity_price[i]) + "," + f3f.format(ss.annuity_stats.period_nominal_annuity_price[i]) + "," + f3f.format(ss.annuity_stats.synthetic_nominal_annuity_price[i]));
		}
		out.close();
        }

        private void dump_annuity_yield_curve() throws IOException
        {
		PrintWriter out = new PrintWriter(new File(ss.cwd + "/" + config.prefix + "-yield_curve.csv"));

	        for (int i = 0; i <= 30; i++)
		{
		        out.println(i + "," + (config.annuity_real_yield_curve == null ? config.annuity_real_rate : ss.annuity_stats.rcmt_get(i)) + "," + (config.annuity_nominal_yield_curve == null ? config.annuity_nominal_rate : ss.annuity_stats.hqm_get(i)));
		}

		out.close();
        }

	// Dump the data files.
	private void dump(AAMap map, Metrics[] retirement_number, List<List<PathElement>> paths, Returns returns) throws IOException
	{
 	        dump_utility(utility_consume, "consume");
	        dump_utility(utility_consume_time, "consume_time");
	        dump_utility(utility_inherit, "inherit");
		//dump_cw();
		if (returns != null)
		{
		        dump_aa_linear(map, returns);
			dump_average(map);
			dump_annuity_price();
			dump_annuity_yield_curve();
		}
		if (!config.skip_retirement_number)
		{
		        dump_retirement_number(retirement_number);
		}
		if (!config.skip_validate)
		{
		        dump_distributions(paths);
		        dump_pct_paths(paths);
			dump_paths(paths);
			// Delta paths breaks when validate using validate dump because guaranteed_safe_aa relies on MVO tangency.
			//dump_delta_paths(paths, 1);
			//dump_delta_paths(paths, 5);
		}
	}

	// Dump retirement number values.
	private void dump_retirement_number(Metrics[] retirement_number) throws IOException
	{
		// Success probability percentile lines versus age and wr
		PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-number.csv")));
		for (int i = retirement_number.length - 1; i >= 0; i--)
		{
		        double pf = i * config.pf_retirement_number / config.retirement_number_steps;
		        double failure_chance = retirement_number[i].fail_chance();
		        double failure_length = retirement_number[i].fail_length() * ss.vital_stats.le.get(config.retirement_age);
			double invutil = 0.0;
			invutil = utility_consume.inverse_utility(retirement_number[i].get(MetricsEnum.CONSUME) / ss.vital_stats.metric_divisor(MetricsEnum.CONSUME, config.validate_age));
			out.print(pf + "," + failure_chance + "," + failure_length + "," + invutil + "\n");
		}
		out.close();
	}

        private void dump_initial_aa(double[] aa) throws IOException
        {
		PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-initial_aa.csv")));
		out.println("asset class,allocation");
		List<String> names = (config.asset_class_names == null ? asset_classes : config.asset_class_names);
		for (int i = 0; i < aa.length; i++)
		        out.println(names.get(i) + "," + aa[i]);
		out.close();
        }

 	// // Dump success probability percentile lines.
	// private void dump_success_lines(Metrics[][] success_lines, double[] goal_range, MetricsEnum metric) throws IOException
	// {
	// 	// Success probability percentile lines versus age and wr
	// 	PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-success-" + metric.toString().toLowerCase() + ".csv")));
	// 	for (int period = 0; period < ss.max_years * config.generate_time_periods; period++)
	// 	{
	// 		List<Double> prob_range = new ArrayList<Double>();
	// 		for (int i = goal_range.length - 1; i >= 0; i--)
	// 		{
	// 			prob_range.add(goal_range[i]);
	// 		}
	// 		prob_range.add(0.0);

	// 		List<String> percentile = new ArrayList<String>();
	// 		boolean seen_upper_range = false;
	// 		Double prev_min_pf = null;
	// 		Metrics[] metrics_period = success_lines[period];
	// 		for (int bucket = metrics_period.length - 1; bucket >= 0; bucket--)
	// 		{
	// 			double candidate_prob = metrics_period[bucket].get(metric);
	// 			assert (0.0 <= candidate_prob && candidate_prob <= 1.0);
	// 			if (prev_min_pf != null)
	// 			{
	// 				if (candidate_prob >= prob_range.get(0))
	// 					seen_upper_range = true;
	// 				while (candidate_prob < prob_range.get(0))
	// 				{
	// 					if (seen_upper_range)
	// 						percentile.add(0, f2f.format(prev_min_pf));
	// 					else
	// 						percentile.add(0, "");
	// 					prob_range.remove(0);
	// 				}
	// 			}
	// 			prev_min_pf = bucket * config.success_lines_scale_size;
	// 		}
	// 		prob_range.remove(prob_range.size() - 1);
	// 		while (true)
	// 		{
	// 			if (prob_range.size() == 0)
	// 				break;
	// 			prob_range.remove(0);
	// 			percentile.add(0, "");
	// 		}
	// 		out.print(f2f.format((period + config.start_age * config.generate_time_periods) / config.generate_time_periods));
	// 		for (String perc : percentile)
	// 		{
	// 			out.print("," + perc);
	// 		}
	// 		out.print("\n");
	// 	}
	// 	out.close();
	// }

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
				// 	if (val < minval)
				// 	{
				// 	        minval = val;
				// 		minloc = i;
				// 	}
				// }
				// System.err.println((config.generate_start_year + minloc) + " " + (minval - 1));
			}
			// System.out.println(Arrays.deepToString(Utils.covariance_returns(returns)));
			// System.out.println(Arrays.deepToString(Utils.correlation_returns(returns)));
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
			// System.out.println(Arrays.deepToString(Utils.correlation_returns(ac_returns)));

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
				PathMetricsResult pm = map_compare.path_metrics(config.validate_age, start_p, config.num_sequences_validate, config.validate_seed, returns_validate);
				System.out.printf("Compare %s/%s: %f\n", aa, vw, pm.mean(success_mode_enum));
			}
		}
		double elapsed = (System.currentTimeMillis() - start) / 1000.0;
		System.out.println("Compare done: " + f1f.format(elapsed) + " seconds");
		System.out.println();
        }

	public void run_main() throws ExecutionException, IOException, InterruptedException
	{
		AAMap map_validate = null;
		AAMap map_loaded = null;
		AAMap map_precise = null;

		Metrics[] retirement_number = null;

		if (do_generate)
		{
			long start = System.currentTimeMillis();
			map_precise = AAMap.factory(this, config.aa_strategy, returns_generate);
			MapElement fpb = map_precise.lookup_interpolate(start_p, (int) Math.round((config.validate_age - config.start_age) * config.generate_time_periods));
			String metric_str;
			double metric_sm = fpb.metric_sm / ss.vital_stats.metric_divisor(success_mode_enum, config.start_age);
			if (!Arrays.asList(MetricsEnum.TW, MetricsEnum.NTW).contains(success_mode_enum))
			{
			        if (config.utility_epstein_zin)
				        metric_sm = utility_consume.inverse_utility(metric_sm);
			        else if (Arrays.asList(MetricsEnum.CONSUME, MetricsEnum.COMBINED).contains(success_mode_enum))
				        metric_sm = utility_consume_time.inverse_utility(metric_sm);
			        else if (success_mode_enum == MetricsEnum.INHERIT)
			                metric_sm = utility_inherit.inverse_utility(metric_sm);
			        metric_str = Double.toString(metric_sm);
			}
		        else
			{
			        metric_str = f2f.format(metric_sm * 100) + "%";
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
			map_loaded = new AAMapDumpLoad(this, map_precise);
			elapsed = (System.currentTimeMillis() - start) / 1000.0;
			if (!config.skip_dump_load)
			{
			        System.out.println("Reload done: " + f1f.format(elapsed) + " seconds");
				System.out.println();
			}

			// if (!config.skip_smooth)
			// {
			//      start = System.currentTimeMillis();
			// 	((AAMapDumpLoad) map_loaded).smooth_map();
			// 	elapsed = (System.currentTimeMillis() - start) / 1000.0;
			// 	System.out.println("Smoothed done: " + f1f.format(elapsed) + " seconds");
			// 	System.out.println();
			// }
		}
		else if (config.validate != null)
		{
		        map_validate = new AAMapDumpLoad(this, config.validate);
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
		// 	long start = System.currentTimeMillis();
		// 	success_lines = map_loaded.simulate_success_lines(returns_validate);
		// 	double elapsed = (System.currentTimeMillis() - start) / 1000.0;
		// 	System.out.println("Success probability lines done: " + f1f.format(elapsed) + " seconds");
		// 	System.out.println();
		// }

		List<List<PathElement>> paths = new ArrayList<List<PathElement>>();
		if (do_target)
		{
			long start = System.currentTimeMillis();
			ss.vital_stats.compute_stats(ss, config.target_time_periods, config.target_life_table);
			ss.annuity_stats.compute_stats(ss, config.target_time_periods, config.annuity_table);
			for (String scheme : config.target_schemes)
			{
			        AAMap map_compare = AAMap.factory(this, scheme, null);
				double keep_rebalance_band = config.rebalance_band_hw;
				if (config.target_rebalance)
					config.rebalance_band_hw = 0.0;
				AAMap baseline_map = (config.target_sdp_baseline ? map_loaded : map_compare);
				AAMap target_map = (config.target_sdp_baseline ? map_compare : map_loaded);
				PathMetricsResult pm = baseline_map.path_metrics(config.validate_age, start_p, config.num_sequences_target, 0, returns_target);
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
				        TargetResult t = target_map.rcr_target(config.validate_age, means.get(success_mode_enum), config.target_sdp_baseline, returns_generate, returns_target, config.target_sdp_baseline);
					//if (!config.target_sdp_baseline)
					//	map_loaded = t.map;
				        target_result = t.target_result;
					target_rcr = t.target;
					location_str = "RCR " + f4f.format(target_rcr);
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
					        savings = (target_rcr - config.rcr) / target_rcr;
					else
					        savings = (config.rcr - target_rcr) / config.rcr;
					savings_str = f1f.format(savings * 100) + "%";
				}
				System.out.printf("Target %-21s %s found at %s savings %s\n", scheme, target_str, location_str, savings_str);
                        }
			double elapsed = (System.currentTimeMillis() - start) / 1000.0;
			System.out.println("Target done: " + f1f.format(elapsed) + " seconds");
			System.out.println();
		}

		if (!config.skip_validate)
		{
			long start = System.currentTimeMillis();
			ss.vital_stats.compute_stats(ss, config.validate_time_periods, config.validate_life_table);
			ss.annuity_stats.compute_stats(ss, config.validate_time_periods, config.annuity_table);
			if (!config.skip_validate_all)
			{
			        PrintWriter out = new PrintWriter(new FileWriter(new File(ss.cwd + "/" + config.prefix + "-ce.csv")));
			        for (int age = config.start_age; age < config.start_age + ss.max_years; age++)
				{
				        PathMetricsResult pm = map_loaded.path_metrics(age, start_p, config.num_sequences_validate, config.validate_seed, returns_validate);
					double ce = utility_consume.inverse_utility(pm.means.get(MetricsEnum.CONSUME) / ss.vital_stats.metric_divisor(MetricsEnum.CONSUME, age));
					out.println(age + "," + f7f.format(ce));

				}
				out.close();
			}
			PathMetricsResult pm = map_loaded.path_metrics(config.validate_age, start_p, config.num_sequences_validate, config.validate_seed, returns_validate);
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
				this.dump(null, retirement_number, paths, null);
				double elapsed = (System.currentTimeMillis() - start) / 1000.0;
				System.out.println("Dump done: " + f1f.format(elapsed) + " seconds");
				System.out.println();
			}
		}
		else
		{
		        long start = System.currentTimeMillis();
			this.dump(map_precise, retirement_number, paths, returns_generate);
			double elapsed = (System.currentTimeMillis() - start) / 1000.0;
			System.out.println("Dump done: " + f1f.format(elapsed) + " seconds");
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

        public Scenario(ScenarioSet ss, Config config, HistReturns hist, List<String> asset_classes, Double start_ria, Double start_nia) throws IOException, InterruptedException
	{
	        this.ss = ss;
	        this.config = config;
	        this.hist = hist;
		this.asset_classes = asset_classes;
 
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

		// Set up the scales.
		scale = new Scale[start_p.length];
		if (tp_index != null)
		        scale[tp_index] = Scale.scaleFactory(config.zero_bucket_size, config.scaling_factor);
		if (ria_index != null)
		        scale[ria_index] = Scale.scaleFactory(config.annuity_zero_bucket_size, config.annuity_scaling_factor);
		if (nia_index != null)
		        scale[nia_index] = Scale.scaleFactory(config.annuity_zero_bucket_size, config.annuity_scaling_factor);

		// Calculated parameters.

		generate_bottom_bucket = this.scale[tp_index].pf_to_bucket(config.pf_guaranteed);
		generate_top_bucket = this.scale[tp_index].pf_to_bucket(config.pf_fail);
		validate_bottom_bucket = this.scale[tp_index].pf_to_bucket(config.pf_validate);
		validate_top_bucket = this.scale[tp_index].pf_to_bucket(0.0);
		success_mode_enum = Metrics.to_enum(config.success_mode);

		vw_strategy = config.vw_strategy;

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
		assert(!config.utility_join || config.consume_discount_rate <= config.upside_discount_rate);
                        // Ensures able to add upside utility to floor utility without exceeding u_inf.
		assert(!config.utility_join || config.utility_age <= config.start_age);
		        // Ditto.
		assert(!config.utility_epstein_zin || (success_mode_enum == MetricsEnum.COMBINED)); // Other success modes not Epstein-Zinized.

		// More internal parameters.

		do_tax = config.tax_rate_cg != 0 || config.tax_rate_div != null || config.tax_rate_div_default != 0 || config.tax_rate_annuity != 0;
		do_target = !config.skip_target && config.target_mode != null;
		do_generate = (config.validate == null) || (do_target && (config.target_sdp_baseline || config.target_mode.equals("rps")));

		normal_assets = asset_classes.size();
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
		cpi_index = -1;
		if (do_tax || nia_index != null)
		{
		        cpi_index = asset_classes.size();
		        asset_classes.add("[cpi]");
		}
		ef_index = -1;
		if (!config.ef.equals("none"))
		{
		        ef_index = asset_classes.size();
		        asset_classes.add("[ef_index]");
		}

		// Set up utility functions.

		Double eta = (config.utility_epstein_zin ? (Double) config.utility_gamma : config.utility_eta);
		Utility utility_consume_risk = Utility.utilityFactory(config, config.utility_consume_fn, eta, config.utility_beta, config.utility_alpha, 0, config.withdrawal, config.utility_ce, config.utility_ce_ratio, 2 * config.withdrawal, 1 / config.utility_slope_double_withdrawal, config.withdrawal, 1, config.public_assistance, config.public_assistance_phaseout_rate, config.withdrawal * 2);
		eta = (config.utility_epstein_zin ? (Double) (1 / config.utility_psi) : config.utility_eta);
		utility_consume_time = Utility.utilityFactory(config, config.utility_consume_fn, eta, config.utility_beta, config.utility_alpha, 0, config.withdrawal, config.utility_ce, config.utility_ce_ratio, 2 * config.withdrawal, 1 / config.utility_slope_double_withdrawal, config.withdrawal, 1, config.public_assistance, config.public_assistance_phaseout_rate, config.withdrawal * 2);

		if (config.utility_join)
		{
		        Utility utility_consume_risk_2 = Utility.utilityFactory(config, "power", config.utility_eta_2, 0, 0.0, 0, config.withdrawal, 0.0, 0, 0, 0, config.utility_join_required, config.utility_join_slope_ratio * utility_consume_risk.slope(config.utility_join_required), 0, 0, config.withdrawal * 2);
		        utility_consume_risk = Utility.joinFactory(config, config.utility_join_type, utility_consume_risk, utility_consume_risk_2, config.utility_join_required, config.utility_join_required + config.utility_join_desired);
                        Utility utility_consume_time_2 = Utility.utilityFactory(config, "power", config.utility_eta_2, 0, 0.0, 0, config.withdrawal, 0.0, 0, 0, 0, config.utility_join_required, config.utility_join_slope_ratio * utility_consume_time.slope(config.utility_join_required), 0, 0, config.withdrawal * 2);
		        utility_consume_time = Utility.joinFactory(config, config.utility_join_type, utility_consume_time, utility_consume_time_2, config.utility_join_required, config.utility_join_required + config.utility_join_desired);
		}
	        utility_consume = utility_consume_risk;

		// Model: Bequest to 1 person for utility_inherit_years or utility_inherit_years people for 1 year who are currently consuming bequest_consume
		// and share the same utility function as you sans utility_join.
		double bequest_consume = (config.utility_bequest_consume == null ? config.withdrawal : config.utility_bequest_consume);
		utility_inherit = new UtilityScale(config, utility_consume_time, 0, 1 / config.utility_inherit_years, config.utility_inherit_years * config.utility_dead_limit, - bequest_consume);
		utility_inherit.range = config.withdrawal * 100;

		// Set up returns.

		returns_generate = null;
		if (do_generate || do_target  || do_tax)
		    returns_generate = new Returns(this, hist, config, config.generate_seed, config.time_varying, config.generate_start_year, config.generate_end_year, config.num_sequences_generate, config.generate_time_periods, config.generate_ret_equity, config.generate_ret_bonds, config.ret_risk_free, config.generate_ret_inflation, config.management_expense, config.generate_shuffle, config.ret_reshuffle, config.generate_draw, config.ret_random_block_size, config.ret_pair, config.ret_short_block, config.generate_all_adjust, config.generate_equity_vol_adjust);

		returns_target = null;
		if (do_target)
		    returns_target = new Returns(this, hist, config, config.target_seed, false, config.target_start_year, config.target_end_year, config.num_sequences_target, config.target_time_periods, config.validate_ret_equity, config.validate_ret_bonds, config.ret_risk_free, config.validate_ret_inflation, config.management_expense, config.target_shuffle, config.ret_reshuffle, config.target_draw, config.ret_random_block_size, config.ret_pair, config.target_short_block, config.validate_all_adjust, config.validate_equity_vol_adjust);

		returns_validate = new Returns(this, hist, config, config.validate_seed, false, config.validate_start_year, config.validate_end_year, config.num_sequences_validate, config.validate_time_periods, config.validate_ret_equity, config.validate_ret_bonds, config.ret_risk_free, config.validate_ret_inflation, config.management_expense, config.validate_shuffle, config.ret_reshuffle, config.validate_draw, config.ret_random_block_size, config.ret_pair, config.ret_short_block, config.validate_all_adjust, config.validate_equity_vol_adjust);

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
