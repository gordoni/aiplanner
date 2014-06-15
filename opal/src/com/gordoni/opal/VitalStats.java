package com.gordoni.opal;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.List;
import java.util.Map;
import java.util.Random;

public class VitalStats
{
        public double time_periods = Double.NaN;
        public String table = null;

        public VitalStats vital_stats1;
        public VitalStats vital_stats2;

	public Double[] death = null;
	public List<Double> le;
	public double[] raw_alive;
	public double[] raw_dying;
	public double[] raw_sum_avg_alive;
	public double[] alive;
	public double[] dying;
	public double[] sum_avg_alive;
        public double[] bounded_sum_avg_alive;
        public double[] upside_alive;
        public double[] bounded_sum_avg_upside_alive;

        private ScenarioSet ss;
        private Config config;
        private HistReturns hist;

	/**
	 * We use arrays instead of Collections here due to performance
	 */

	// Actuarial data.

	// Combined, male, and female probability of dying during a given year of
	// age.
	// National Vital Statistics Reports: United States Life Tables, 2007
	//
	// (Source: http://www.cdc.gov/nchs/products/life_tables.htm )

	private static Double person[] = { //
                	0.006761, 0.000460, 0.000286, 0.000218, 0.000176, 0.000164, 0.000151, 0.000140, 0.000124, 0.000105,//
			0.000091, 0.000094, 0.000132, 0.000209, 0.000314, 0.000426, 0.000529, 0.000627, 0.000715, 0.000796,//
			0.000881, 0.000963, 0.001017, 0.001034, 0.001023, 0.001003, 0.000990, 0.000983, 0.000988, 0.001005,//
			0.001030, 0.001060, 0.001099, 0.001146, 0.001201, 0.001264, 0.001340, 0.001434, 0.001548, 0.001685,//
			0.001836, 0.002000, 0.002188, 0.002400, 0.002629, 0.002864, 0.003107, 0.003369, 0.003661, 0.003984,//
			0.004337, 0.004709, 0.005091, 0.005474, 0.005863, 0.006275, 0.006726, 0.007220, 0.007773, 0.008389,//
			0.009081, 0.009839, 0.010657, 0.011534, 0.012491, 0.013600, 0.014722, 0.015959, 0.017288, 0.018755,//
			0.020424, 0.022385, 0.024679, 0.027320, 0.030299, 0.033636, 0.037216, 0.041160, 0.045503, 0.050281,//
			0.055531, 0.061293, 0.067611, 0.074528, 0.082091, 0.090346, 0.099341, 0.109125, 0.119744, 0.131244,//
			0.143668, 0.157056, 0.171442, 0.186853, 0.203309, 0.220822, 0.239389, 0.258999, 0.279625, 0.301225,//
			0.301225, 0.301225, 0.301225, 0.301225, 0.301225, 0.301225, 0.301225, 0.301225, 0.301225, 0.301225,// 100-109 conservatively extrapolated
	};
	private static Double male[] = { //
	                0.007390, 0.000490, 0.000316, 0.000242, 0.000201, 0.000182, 0.000170, 0.000156, 0.000134, 0.000107,//
			0.000085, 0.000089, 0.000143, 0.000256, 0.000411, 0.000573, 0.000725, 0.000873, 0.001014, 0.001149,//
			0.001292, 0.001427, 0.001512, 0.001529, 0.001497, 0.001448, 0.001409, 0.001382, 0.001376, 0.001390,//
			0.001412, 0.001437, 0.001474, 0.001516, 0.001570, 0.001634, 0.001716, 0.001821, 0.001956, 0.002120,//
			0.002303, 0.002505, 0.002735, 0.002992, 0.003270, 0.003556, 0.003855, 0.004187, 0.004570, 0.005001,//
			0.005474, 0.005969, 0.006473, 0.006971, 0.007469, 0.007995, 0.008567, 0.009179, 0.009843, 0.010571,//
			0.011378, 0.012264, 0.013227, 0.014275, 0.015434, 0.016771, 0.018156, 0.019682, 0.021327, 0.023144,//
			0.025204, 0.027616, 0.030417, 0.033598, 0.037153, 0.041097, 0.045315, 0.049944, 0.055019, 0.060576,//
			0.066655, 0.073296, 0.080542, 0.088435, 0.097021, 0.106343, 0.116446, 0.127371, 0.139160, 0.151850,//
			0.165475, 0.180063, 0.195635, 0.212205, 0.229779, 0.248348, 0.267897, 0.288394, 0.309795, 0.332043,//
			0.332043, 0.332043, 0.332043, 0.332043, 0.332043, 0.332043, 0.332043, 0.332043, 0.332043, 0.332043,// 100-109 conservatively extrapolated
	};
	private static Double female[] = { //
                	0.006103, 0.000430, 0.000255, 0.000193, 0.000149, 0.000145, 0.000132, 0.000122, 0.000112, 0.000103,//
			0.000096, 0.000100, 0.000120, 0.000160, 0.000212, 0.000271, 0.000325, 0.000369, 0.000400, 0.000422,//
			0.000443, 0.000467, 0.000488, 0.000504, 0.000518, 0.000532, 0.000548, 0.000565, 0.000583, 0.000605,//
			0.000634, 0.000670, 0.000714, 0.000767, 0.000824, 0.000887, 0.000959, 0.001040, 0.001137, 0.001248,//
			0.001367, 0.001495, 0.001644, 0.001812, 0.001994, 0.002182, 0.002373, 0.002569, 0.002775, 0.002995,//
			0.003236, 0.003494, 0.003763, 0.004041, 0.004330, 0.004639, 0.004981, 0.005372, 0.005826, 0.006347,//
			0.006942, 0.007595, 0.008293, 0.009029, 0.009826, 0.010753, 0.011692, 0.012722, 0.013830, 0.015062,//
			0.016484, 0.018170, 0.020151, 0.022445, 0.025056, 0.028016, 0.031215, 0.034767, 0.038707, 0.043073,//
			0.047907, 0.053254, 0.059160, 0.065676, 0.072854, 0.080749, 0.089416, 0.098914, 0.109300, 0.120630,//
			0.132959, 0.146339, 0.160816, 0.176428, 0.193208, 0.211174, 0.230333, 0.250679, 0.272186, 0.294812,//
			0.294812, 0.294812, 0.294812, 0.294812, 0.294812, 0.294812, 0.294812, 0.294812, 0.294812, 0.294812,// 100-109 conservatively extrapolated
	};
	private static Double immortal[] = {
	                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, // # 100-109
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, // # 110-119
	};
        private static Double suicidal[] = {
	                1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, // # 100-109
			1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, // # 110-119
	};

        private int lcm(int a, int b)
        {
	        if (a == 0)
		        a = 1;
		if (b == 0)
		        b = 1;
		int v = a;
	        while (true)
		{
		        if (v % b == 0)
			        return v;
			v += a;
		}
        }

        private double get_birth_year(int age)
        {
	        Calendar now = Calendar.getInstance();
		if (config.birth_year == null)
		        return now.get(Calendar.YEAR) + (double) now.get(Calendar.MONTH) / 12 - age;  // Don't do finer grain, or introduce non-determinism.
		else
		        return config.birth_year;
        }

        private Double[] cohort(Map<Integer, List<Double>> cohort_death, int age)
        {
                double birth_year = get_birth_year(age);
		int min_year = Integer.MAX_VALUE;
		int max_year = Integer.MIN_VALUE;
		for (int year : cohort_death.keySet())
		{
		        if (year < min_year)
			        min_year = year;
		        if (year > max_year)
			        max_year = year;
		}
		if (birth_year < min_year)
		        birth_year = min_year;
		if (birth_year > max_year - 10)
		        birth_year = max_year - 10;
                int year_base = (int) (birth_year / 10) * 10;
		double year_fract = (birth_year - year_base) / 10;
                List<Double> cohort_base = cohort_death.get(year_base);
                List<Double> cohort_ceil = cohort_death.get(year_base + 10);
		Double[] death_cohort = new Double[cohort_base.size()];
		for (int i = 0; i < death_cohort.length; i++)
		{
		        death_cohort[i] = cohort_base.get(i) * (1 - year_fract) + cohort_ceil.get(i) * year_fract;
		}
		return death_cohort;
        }

        public double mortality_projection(String sex, int age)
        {
		if (config.mortality_projection_method.equals("g2"))
		        if ("male".equals(sex))
			        return hist.soa_projection_g2_f.get(age);
			else
			        return hist.soa_projection_g2_f.get(age);
		else if (config.mortality_projection_method.equals("rate"))
		        return config.mortality_reduction_rate;
		else
		        assert(false);
		return Double.NaN;
	}

        private Double[] get(String table, String sex, int age)
	{
	        Double[] death_cohort = null;
		if ("immortal".equals(sex) || "immortal".equals(table))
		{
		        death_cohort = immortal;
		}
		else if ("suicidal".equals(sex) || "suicidal".equals(table))
		{
		        death_cohort = suicidal;
		}
		else if ("ssa-cohort".equals(table))
		{
		        if ("male".equals(sex))
			        death_cohort = cohort(hist.ssa_cohort_death_m, age);
			else if ("female".equals(sex))
			        death_cohort = cohort(hist.ssa_cohort_death_f, age);
		}
		else
		{
			int period_base = 0;
		        Double[] death_period = null;
			if ("ssa-period".equals(table))
		        {
				period_base = 2009;
			        if ("male".equals(sex))
				        death_period = hist.ssa_death_m.toArray(new Double[0]);
				else if ("female".equals(sex))
				        death_period = hist.ssa_death_f.toArray(new Double[0]);
			}
			else if ("cdc-period".equals(table))
		        {
			        period_base = 2007;
			        if ("person".equals(sex))
				        death_period = person;
				else if ("male".equals(sex))
				        death_period = male;
				else if ("female".equals(sex))
				        death_period = female;
			}
			else if ("iam2000-unloaded-period".equals(table))
		        {
				period_base = 2000;
				if ("male".equals(sex))
				        death_period = hist.soa_iam2000_unloaded_death_m.toArray(new Double[0]);
				else if ("female".equals(sex))
				        death_period = hist.soa_iam2000_unloaded_death_f.toArray(new Double[0]);
			}
			else if ("iam2000-loaded-period".equals(table))
		        {
				period_base = 2000;
				if ("male".equals(sex))
				        death_period = hist.soa_iam2000_loaded_death_m.toArray(new Double[0]);
				else if ("female".equals(sex))
				        death_period = hist.soa_iam2000_loaded_death_f.toArray(new Double[0]);
			}
			else if ("iam2012-basic-period".equals(table))
		        {
				period_base = 2012;
				if ("male".equals(sex))
				        death_period = hist.soa_iam2012_basic_death_m.toArray(new Double[0]);
				else if ("female".equals(sex))
				        death_period = hist.soa_iam2012_basic_death_f.toArray(new Double[0]);
			}
			assert(death_period != null);
			double birth_year = get_birth_year(age);
			death_cohort = new Double[death_period.length];
			for (int i = 0; i < death_cohort.length; i++)
			        death_cohort[i] = Math.min(death_period[i] * Math.pow(1 - mortality_projection(sex, i), i - (period_base - birth_year)), 1.0);
		}
		for (int i = 0; i < death_cohort.length; i++)
		        death_cohort[i] *= (1 - config.mortality_load);
		return death_cohort;
	}

        private Double[] pre_compute_couple_death(Double[] death1, Double[] death2)
	{
	        int couple_len = config.start_age + Math.max(death1.length - config.start_age, death2.length - config.start_age2);
		Double[] couple = new Double[couple_len];
		double m_alive = 1.0;
		double f_alive = 1.0;
		double c_alive = 1.0;
		for (int age = 0; age < couple_len; age++)
		{
		        if (age < config.start_age)
			        couple[age] = Double.NaN;
			else
			{
			        int age2 = age - config.start_age + config.start_age2;
				double m_death = age < death1.length ? death1[age] : 1.0;
				double f_death = age2 < death2.length ? death2[age2] : 1.0;
				double m_dead = 1.0 - m_alive;
				double f_dead = 1.0 - f_alive;
				double c_death;
				if (c_alive > 0.0)
				{
				        double c_death_num = m_alive * f_dead * m_death + m_dead * f_alive * f_death + m_alive * f_alive * m_death * f_death;
				        c_death = c_death_num / c_alive;
				}
				else
				        c_death = 1.0;
				m_alive *= 1.0 - m_death;
				f_alive *= 1.0 - f_death;
				c_alive *= 1.0 - c_death;
				if (c_death > 1.0)
					c_death = 1.0; // Handle floating point precision limitations.
				couple[age] = c_death;
			}
		}
		return couple;
	}

        // NB: sum_avg_alive[i] / alive[i] = le.get(start_age + i) when time_periods==1 and consume_discount_rate==0.
	private void pre_compute_life_expectancy()
	{
	        this.le = new ArrayList<Double>();
		int limit = death.length;
	        for (int s = 0; s < limit; s++)
		{
		        double expectancy = 0.0;
			double alive = 1.0;
			int i = 0;
			int y = s + i;
			while (y < limit)
			{
				if (y >= config.start_age)
				        alive *= 1.0 - death[y];
				expectancy += alive;
				i += 1;
				y = s + i;
		        }
			this.le.add(expectancy);
		}
	}

        // Bounded_sum_avg_alive is like sum_avg_alive, but is constant until retirement_age and stops at max_years instead of death.length.
        public void pre_compute_alive_dying(Double[] death, double[] alive_array, double[] dying_array, double[] sum_avg_alive_array, double[] bounded_sum_avg_alive, double time_periods, double r)
	{
		double alive = 1.0;
		double dying = 0.0;
		double prev_alive = 1.0;

		int upside_age = config.utility_age;
		double discount = Math.pow(1 + r, - (config.start_age - upside_age));
		        // Initial discount is no longer arbitrary, even though we deal with ratios of values, because upside_alive must match alive at upside_age.

		if (alive_array != null)
		        alive_array[0] = alive * discount;

		int len = 0;
		if (alive_array != null)
		        len = Math.max(len, alive_array.length - 1);
		if (dying_array != null)
		        len = Math.max(len, dying_array.length);
		if (sum_avg_alive_array != null)
		        len = Math.max(len, sum_avg_alive_array.length);
		if (bounded_sum_avg_alive != null)
		        len = Math.max(len, bounded_sum_avg_alive.length);

		double[] avg_alive = new double[(int) Math.round (len * time_periods)];

		double death_period = 0.0;
		int index = 0;
		for (int y = 0; y < len; y++)
		{
			if (time_periods <= 1.0)
			{
			        death_period = 1.0 - (1.0 - death_period) * (1.0 - death[Math.min(config.start_age + y, death.length - 1)]);
			        if ((y + 1) % Math.round(1 / time_periods) != 0)
				        continue;
			}
			else
			{
			        death_period = 1.0 - Math.pow(1.0 - death[Math.min(config.start_age + y, death.length - 1)], 1.0 / time_periods);
			}
			for (int i = 0; i < time_periods; i++)
			{
				dying = alive * death_period;
				prev_alive = alive * discount;
				alive -= dying;
				if (alive_array != null)
				        alive_array[index + 1] = alive * discount;
				if (dying_array != null)
				        dying_array[index] = dying * discount * Math.pow(1 + r, - 0.5 / time_periods);
				avg_alive[index] = alive_array[index];
				discount *= Math.pow(1 + r, - 1.0 / time_periods);
				index++;
			}
			death_period = 0;
		}

		double sum_aa = 0;
		double bounded_sum_aa = 0;
		for (int i = avg_alive.length - 1; i >= 0; i--)
		{
		        sum_aa += avg_alive[i];
			double divisor = 0;
			if (bounded_sum_avg_alive != null && i < bounded_sum_avg_alive.length)
			        if (!config.utility_retire || i >= Math.round((config.retirement_age - config.start_age) * time_periods))
				        bounded_sum_aa += avg_alive[i];
			if (sum_avg_alive_array != null)
			        sum_avg_alive_array[i] = sum_aa;
			if (bounded_sum_avg_alive != null && i < bounded_sum_avg_alive.length)
			        bounded_sum_avg_alive[i] = bounded_sum_aa;
		}
	}

        public double metric_divisor(MetricsEnum metric, int age)
        {
	        if (metric != MetricsEnum.INHERIT)
		        return 1;

		int period = (int) Math.round((age - config.start_age) * time_periods);
		int total_periods = (int) Math.round(ss.max_years * time_periods);
	        double d = 0;
		for (int y = period; y < total_periods; y++)
		        if (!config.utility_retire || y >= Math.round((config.retirement_age - config.start_age) * time_periods))
			        d += dying[y];
		return d;
	}

        public VitalStats(ScenarioSet ss, Config config, HistReturns hist, double time_periods)
        {
		this.ss = ss;
	        this.config = config;
		this.hist = hist;
	        this.time_periods = time_periods;
        }

        private void pre_compute_stats(Double[] death, int death_len)
        {
		this.death = death;

		int vs_years = death_len - config.start_age;
		int actual_years = (config.years == null) ? death_len : config.years;
		this.raw_alive = new double[(int) Math.round(vs_years * time_periods) + 1];
		this.raw_dying = new double[(int) Math.round(vs_years * time_periods)];
		this.raw_sum_avg_alive = new double[(int) Math.round(vs_years * time_periods)];
 		pre_compute_alive_dying(death, raw_alive, raw_dying, raw_sum_avg_alive, null, time_periods, 0);
		this.alive = new double[(int) Math.round(vs_years * time_periods) + 1];
		this.dying = new double[(int) Math.round(vs_years * time_periods)];
		this.sum_avg_alive = new double[(int) Math.round(vs_years * time_periods)];
		this.bounded_sum_avg_alive = new double[Math.min(actual_years, (int) Math.round(vs_years * time_periods))];
 		pre_compute_alive_dying(death, alive, dying, sum_avg_alive, bounded_sum_avg_alive, time_periods, config.consume_discount_rate);
		this.upside_alive = new double[(int) Math.round(vs_years * time_periods) + 1];
		this.bounded_sum_avg_upside_alive = new double[Math.min(actual_years, (int) Math.round(vs_years * time_periods))];
 		pre_compute_alive_dying(death, upside_alive, null, null, bounded_sum_avg_upside_alive, time_periods, config.upside_discount_rate);

		if (ss.max_years == -1)
		{
			ss.max_years = Math.min(actual_years, death_len - config.start_age);
			ss.max_years -= ss.max_years % lcm((int) Math.round(1.0 / config.generate_time_periods), (int) Math.round(1.0 / config.validate_time_periods));
		}
		else
		{
		        ss.max_years = Math.min(ss.max_years, (int) (dying.length / config.validate_time_periods));
		}
        }

        private void joint_compute_stats(Double[] death1, Double[] death2)
        {
	        Double[] death_joint = pre_compute_couple_death(death1, death2);
		vital_stats1 = new VitalStats(ss, config, hist, time_periods);
		vital_stats2 = new VitalStats(ss, config, hist, time_periods);
		int death_len = Math.max(death1.length, death2.length);
		death_len = Math.max(death_len, death_joint.length);
		vital_stats1.pre_compute_stats(death1, death_len);
		vital_stats2.pre_compute_stats(death2, death_len);
		pre_compute_stats(death_joint, death_len);
	}

        public boolean compute_stats(String table)
        {
	        if (table.equals(this.table))
		        return false;

		this.table = table;

		Double[] death1 = get(table, config.sex, config.start_age);
		if (config.sex2 == null)
		{
		        pre_compute_stats(death1, death1.length);
		}
		else
		{
		        Double[] death2 = get(table, config.sex2, config.start_age2);
			joint_compute_stats(death1, death2);
		}

	        pre_compute_life_expectancy();

		return true;
	}

        private Double[] generate(VitalStats vital_stats, int start_age, Random random)
        {
	        Double[] death = new Double[vital_stats.death.length];
	        double longevity = random.nextDouble();
		for (int y = start_age; y < death.length; y++)
		        death[y] = (longevity < vital_stats.alive[y - start_age] ? 0.0 : 1.0);
		return death;
	}

        public VitalStats joint_generate(Random random)
        {
	        Double[] death1 = generate(vital_stats1, config.start_age, random);
	        Double[] death2 = generate(vital_stats2, config.start_age2, random);
		VitalStats generate_stats = new VitalStats(ss, config, hist, time_periods);
		generate_stats.joint_compute_stats(death1, death2);

		return generate_stats;
        }
}
