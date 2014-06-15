package com.gordoni.opal;

public class AAMapStatic extends AAMap
{
        public AAMapStatic(Scenario scenario, String aa_strategy, AAMap aamap1, AAMap aamap2, VitalStats validate_stats, Utility uc_time, Utility uc_risk, double guaranteed_income)
	{
	        super(scenario, aamap1, aamap2, null, validate_stats, uc_time, uc_risk, guaranteed_income);

		assert(scenario.start_p.length == 1 && scenario.tp_index != null);

	        int top_bucket = scenario.validate_top_bucket;
	        int bottom_bucket = scenario.validate_bottom_bucket;
	        map = new MapPeriod[(int) (scenario.ss.max_years * config.generate_time_periods)];

		for (int pi = 0; pi < map.length; pi++)
	        {
 		        double age = (double) (pi + config.start_age * config.generate_time_periods) / config.generate_time_periods;
			map[pi] = new MapPeriod(scenario, false);
			for (int bi = 0; bi < map[pi].length[scenario.tp_index]; bi++)
			{
				int[] bucket = new int[scenario.start_p.length];
				bucket[scenario.tp_index] = map[pi].bottom[scenario.tp_index] + bi;
				double[] p = scenario.bucketToP(bucket);
				double[] aa = generate_aa(aa_strategy, age, p);
				MapElement me = new MapElement(p, aa, null, null, null);
				map[pi].set(bucket, me);
		        }
	        }
        }
}
