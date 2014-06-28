package com.gordoni.opal;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.Arrays;
import java.util.HashMap;
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
		while ((line = in.readLine()) != null)
		{
  			String[] fields = line.split(",", -1);
			double years = Double.parseDouble(fields[0]);
			double yield = Double.parseDouble(fields[1]) / 100;
			real_yield_curve.put(years, yield);
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
		return real_yield_curve.get(maturity);
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
		return nominal_rate / matches;
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
			double ra_price = 0;
			double na_price = 0;
			double period_ra_price = 0;
			double period_na_price = 0;
			Double[] period_death = vital_stats.death.clone();
			// double cohort_to_cohort = Math.pow(1 - config.mortality_reduction_rate, - i / time_periods);
			for (int j = 0; j < period_death.length; j++)
			{
			        assert(config.sex2 == null);
			        double rate = vital_stats.mortality_projection(config.sex, (int) (j / time_periods));
			        double cohort_to_cohort = Math.pow(1 - rate, - i / time_periods);
				period_death[j] = Math.min(cohort_to_cohort * period_death[j], 1);
			}
			double[] period_alive = new double[vital_stats.alive.length];
			vital_stats.pre_compute_alive_dying(period_death, period_alive, null, null, null, time_periods, 0);
			for (int j = i + (config.annuity_payout_immediate ? 0 : 1); j < vital_stats.alive.length - 1; j++)
			{
			        double maturity = (j - i + 0.5) / time_periods;
				double avg_alive = (vital_stats.raw_alive[j] + vital_stats.raw_alive[j + 1]) / 2;
				double period_avg_alive = (period_alive[j] + period_alive[j + 1]) / 2;
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
			this.synthetic_real_annuity_price[i] = ra_price / (vital_stats.raw_alive[i] * time_periods * config.annuity_real_mwr);
			this.synthetic_nominal_annuity_price[i] = na_price / (vital_stats.raw_alive[i] * time_periods * config.annuity_nominal_mwr);
			this.period_real_annuity_price[i] =  period_ra_price / (period_alive[i] * time_periods * config.annuity_real_mwr);
			this.period_nominal_annuity_price[i] = period_na_price / (period_alive[i] * time_periods * config.annuity_nominal_mwr);
			double real_annuity_price_male[] = hist.real_annuity_price.get(config.annuity_real_quote + "-male");
			double real_annuity_price_female[] = hist.real_annuity_price.get(config.annuity_real_quote + "-female");
			if (config.sex.equals("male") && config.start_age + (int) (i / time_periods) < real_annuity_price_male.length)
			        this.actual_real_annuity_price[i] = real_annuity_price_male[config.start_age + (int) (i / time_periods)];
			else if (config.sex.equals("female") && config.start_age + (int) (i / time_periods) < real_annuity_price_female.length)
			        this.actual_real_annuity_price[i] = real_annuity_price_female[config.start_age + (int) (i / time_periods)];
			else
			        this.actual_real_annuity_price[i] = Double.POSITIVE_INFINITY;
			double nominal_annuity_price_male[] = hist.nominal_annuity_price.get(config.annuity_nominal_quote + "-male");
			double nominal_annuity_price_female[] = hist.nominal_annuity_price.get(config.annuity_nominal_quote + "-female");
			if (config.sex.equals("male") && config.start_age + (int) (i / time_periods) < nominal_annuity_price_male.length)
			        this.actual_nominal_annuity_price[i] = nominal_annuity_price_male[config.start_age + (int) (i / time_periods)];
			else if (config.sex.equals("female") && config.start_age + (int) (i / time_periods) < nominal_annuity_price_female.length)
			        this.actual_nominal_annuity_price[i] = nominal_annuity_price_female[config.start_age + (int) (i / time_periods)];
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
