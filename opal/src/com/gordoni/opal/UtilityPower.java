package com.gordoni.opal;

public class UtilityPower extends Utility
{
        private Config config;
        private double public_assistance;
        private double public_assistance_phaseout_rate;
        private double offset;
        private double eta;
        private double scale;
        private double zero = 0;

        private boolean cache = false;
        private double[] utility_cache = null;  // Lookup is slow so we use a cache. Cache effective utility since it is smooth.

        public double effective_utility(double c)
        {
	        if (eta == 1)
		        return scale * Math.log((c - offset)) - zero;
		else
		        return scale * Math.pow((c - offset), 1 - eta) / (1 - eta) - zero;
        }

        public double utility(double c)
        {
		// if (c < 0)
		// {
		//         if (config.trace)
		// 	    System.out.println("Negative consumption.");
		//         return Double.NEGATIVE_INFINITY; // Helpful when generating negative buckets.
		// }
	        assert(c >= 0);
		double effective_c;
		if (c * public_assistance_phaseout_rate < public_assistance)
		        effective_c = public_assistance + c * (1 - public_assistance_phaseout_rate);
		else
		        effective_c = c;
		double u;
		if (!cache || effective_c >= range)
		        u = effective_utility(effective_c);
		else
		{
		        double i_double = effective_c / range * config.utility_steps;
			int i = (int) i_double;
			double i_fract = i_double - i;
			u = utility_cache[i] * (1 - i_fract) + utility_cache[i + 1] * i_fract;
		}
		return u;
        }

        public double inverse_utility(double u)
	{
	        assert((eta <= 1) || ((zero + u) <= 0));
	        double c;
		if (scale == 0)
		{
		        assert(u == - zero);
		        c = 0;
		}
	        else if (eta == 1)
		        c = offset + Math.exp((zero + u) / scale);
		else
		        c = offset + Math.pow((zero + u) * (1 - eta) / scale, 1 / (1 - eta));
		if (Math.abs(c) < 1e-15 * config.withdrawal)
		        // Floating point rounding error.
		        // Treat it nicely because we want utility_donate.inverse_utility(0)=0, otherwise we run into problems when donation is disabled.
		        c = 0;
	        if (c * public_assistance_phaseout_rate < public_assistance)
		        return (c - public_assistance) / (1 - public_assistance_phaseout_rate);
	        else
		        return c;
	}

        public double slope(double c)
        {
	        assert(c >= 0);
	        boolean assist = c * public_assistance_phaseout_rate < public_assistance;
		if (assist)
		        c = public_assistance + c * (1 - public_assistance_phaseout_rate);
		double slope = scale * Math.pow((c - offset), - eta);
		if (assist)
		        return (1 - public_assistance_phaseout_rate) * slope;
		else
		        return slope;
	}

        public double inverse_slope(double s)
        {
	        // Bug: need to adjust s for public assistance; but method only used for testing so OK.
	        double c;
	        if (scale == 0)
		{
		        assert(s == 0);
		        c = 0;
		}
		else
		        c = offset + Math.pow(s / scale, - 1 / eta);
	        if (c * public_assistance_phaseout_rate < public_assistance)
		        return (c - public_assistance) / (1 - public_assistance_phaseout_rate);
	        else
		        return c;
	}

    public UtilityPower(Config config, Double force_eta, double c_shift, double c_zero, Double ce, double ce_ratio, double c1, double s1, double c2, double s2, double public_assistance, double public_assistance_phaseout_rate, double range)
        {
	        double c1_adjust = c1;
	        double s1_adjust = s1;
	        if (c1 * public_assistance_phaseout_rate < public_assistance)
		{
		        c1_adjust = public_assistance + c1 * (1 - public_assistance_phaseout_rate);
		}
	        double c2_adjust = c2;
	        double s2_adjust = s2;
	        if (c2 * public_assistance_phaseout_rate < public_assistance)
		{
		        c2_adjust = public_assistance + c2 * (1 - public_assistance_phaseout_rate);
		}
		this.config = config;
	        this.range = range;
		this.public_assistance = public_assistance;
		this.public_assistance_phaseout_rate = public_assistance_phaseout_rate;
		this.offset = c_shift;
		if (force_eta != null)
		        this.eta = force_eta;
		else if (ce != null)
		{
		        double low = 0;
		        double high = 100;
			double mid;
		        while (true)
			{
			        mid = (low + high) / 2;
				if ((mid == low) || (mid == high))
				        break;
				double res = (mid == 1 ? Math.sqrt(ce_ratio) : Math.pow((1 + Math.pow(ce_ratio, 1 - mid)) / 2, 1 / (1 - mid)));
				if (res < ce)
				        high = mid;
				else
				        low = mid;
			}
			this.eta = mid;
		}
		else
		{
		        assert(c1_adjust > offset); // public_assistance must be positive unless force_eta.
		        assert(c2_adjust > offset);
			if (s1_adjust == s2_adjust)
			{
			        this.eta = 0;
			}
			else
			        this.eta = Math.log(s1_adjust / s2_adjust) / Math.log((c2_adjust - offset) / (c1_adjust - offset));
		}
	        this.scale = s2_adjust * Math.pow(c2_adjust - offset, eta);
		this.zero = utility(c_zero);
		assert(utility(c_zero) == 0);
		//assert(Math.abs(slope(c1) - s1) < 1e-6);
		//assert(Math.abs(slope(c2) - s2) < 1e-6);

		final boolean enable_cache = false;
		// Cache is disabled for now. A bug once meant consumption lookups are all very close. The cache makes them linear.
		// This makes the nearby consume utility constant for different contrib values as lower target_consume_utility values have higher solvencies.
		// This makes aa_search_dir walk much further than it should.  Whether other parts of the system generate close lookups is unclear.
		// Play it safe, and employ a local cache inside simulate().
		if (enable_cache && config.utility_steps > 0)
		{
		        utility_cache = new double[config.utility_steps + 1];
			for (int i = 0; i <= config.utility_steps; i++)
			{
			        utility_cache[i] = effective_utility(range * i / config.utility_steps);
			}
			cache = true;
		}

		set_constants();
	}
}
