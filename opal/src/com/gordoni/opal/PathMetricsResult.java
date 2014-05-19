package com.gordoni.opal;

import java.text.DecimalFormat;
import java.util.Arrays;
import java.util.List;

public class PathMetricsResult
{
        private Scenario scenario;
        private Config config;

	public Metrics means;
	public Metrics standard_deviations;
	public List<List<PathElement>> paths;

        public PathMetricsResult(Scenario scenario, Metrics means, Metrics standard_deviations, List<List<PathElement>> paths)
	{
	        this.scenario = scenario;
		this.config = scenario.config;

		this.means = means;
		this.standard_deviations = standard_deviations;
		this.paths = paths;
	}

	private static DecimalFormat f3f = new DecimalFormat("0.000");
	private static DecimalFormat f7f = new DecimalFormat("0.0000000");

        public double mean(MetricsEnum metric)
        {
	        if (metric == MetricsEnum.JPMORGAN && config.skip_metric_jpmorgan)
		        return 0;
	        if (metric == MetricsEnum.COMBINED && config.utility_epstein_zin)
		        // Epstein-Zin utility can't be estimated by simulating paths. Only the combined metric is Epstein-Zinized.
		        return 0;
	        double div = scenario.ss.vital_stats.metric_divisor(metric, config.validate_age);
		if (div == 0)
		{
		        assert(means.get(metric) == 0);
		        assert(standard_deviations.get(metric) == 0);
			div = 1;
		}
		double mean = means.get(metric) / div;
		Utility utility = null;
		if (Arrays.asList(MetricsEnum.FLOOR, MetricsEnum.CONSUME, MetricsEnum.COMBINED, MetricsEnum.JPMORGAN).contains(metric) || (metric == MetricsEnum.UPSIDE && config.utility_join))
			utility = scenario.utility_consume_time;
		else if (metric == MetricsEnum.INHERIT)
			utility = scenario.utility_inherit;
		if (utility != null)
			mean = utility.inverse_utility(mean);
		if (metric == MetricsEnum.UPSIDE)
		        if (config.utility_join)
			        mean -= config.utility_join_required;
			else
			        mean = Double.NaN;
		return mean;
	}

        public double std_dev(MetricsEnum metric)
        {
	        if (metric == MetricsEnum.JPMORGAN && config.skip_metric_jpmorgan)
		        return 0;
	        double div = scenario.ss.vital_stats.metric_divisor(metric, config.validate_age);
		if (div == 0)
		{
		        assert(means.get(metric) == 0);
		        assert(standard_deviations.get(metric) == 0);
			div = 1;
		}
		double mean = means.get(metric) / div;
		double std_dev = standard_deviations.get(metric) / div;
		Utility utility = null;
		if (Arrays.asList(MetricsEnum.FLOOR, MetricsEnum.CONSUME, MetricsEnum.COMBINED, MetricsEnum.JPMORGAN).contains(metric) || (metric == MetricsEnum.UPSIDE && config.utility_join))
			utility = scenario.utility_consume_time;
		else if (metric == MetricsEnum.INHERIT)
			utility = scenario.utility_inherit;
		if (utility != null && !Double.isNaN(std_dev))
		        std_dev = (utility.inverse_utility(mean + std_dev) - utility.inverse_utility(mean - std_dev)) / 2;
		return std_dev;
	}

        public void print()
        {
		for (MetricsEnum metric : MetricsEnum.values())
		{
			double mean = mean(metric);
			double std_dev = std_dev(metric);
		        if (Double.isNaN(mean) || Double.isNaN(std_dev))
			{
			        mean = 0;
			        std_dev = 0;
			}
		        String flag = ((config.validate == null) && metric == scenario.success_mode_enum) ? " <= Goal" : "";
			if (Arrays.asList(MetricsEnum.TW, MetricsEnum.NTW).contains(metric))
			        System.out.printf("Metric %-18s %s\n", metric.toString().toLowerCase() + ": ", f3f.format(mean * 100) + "% +/- " + f3f.format(std_dev * 100) + "%" + flag);
			else
			        System.out.printf("Metric %-18s %s\n", metric.toString().toLowerCase() + ": ", f7f.format(mean) + " +/- " + f7f.format(std_dev) + flag);
		}
		double failure_chance = means.fail_chance() * 100;
		double failure_length = means.fail_length() * scenario.ss.vital_stats.le.get(config.validate_age);
		System.out.printf("%.2f%% chance of failure; %.1f years weighted failure length\n", failure_chance, failure_length);
	}
}
