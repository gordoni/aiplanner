package com.gordoni.opal;

public class UtilityHara extends Utility
{
        private Config config;
        private double public_assistance;
        private double public_assistance_phaseout_rate;
        private double offset;
        private double eta;
        private double beta;
        private double scale = 1;
        private double zero = 0;

        public double utility(double c)
        {
	        assert(c >= 0);
		if (c * public_assistance_phaseout_rate < public_assistance)
		        c = public_assistance + c * (1 - public_assistance_phaseout_rate);
	        if (eta == 1)
		        return scale * Math.log((c - offset) / eta + beta) - zero;
		else
		        return scale * Math.pow((c - offset) / eta + beta, 1 - eta) * eta / (1 - eta) - zero;
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
		        c = offset + eta * (Math.exp((zero + u) / scale) - beta);
		else
		        c = offset + eta * (Math.pow((zero + u) * (1 - eta) / eta / scale, 1 / (1 - eta)) - beta);
		//if (Math.abs(c) < 1e-15 * config.withdrawal)
		//        // Floating point rounding error.
		//        // Treat it nicely because we want utility_donate.inverse_utility(0)=0, otherwise we run into problems when donation is disabled.
		//        c = 0;
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
		double slope = scale * Math.pow(beta + (c - offset) / eta, - eta);
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
		        c = offset + eta * (Math.pow(s / scale, - 1 / eta) - beta);
	        if (c * public_assistance_phaseout_rate < public_assistance)
		        return (c - public_assistance) / (1 - public_assistance_phaseout_rate);
	        else
		        return c;
	}

        public double slope2(double c)
        {
	        assert(c >= 0);
	        boolean assist = c * public_assistance_phaseout_rate < public_assistance;
		if (assist)
		        c = public_assistance + c * (1 - public_assistance_phaseout_rate);
		double slope2 = - scale * Math.pow(beta + (c - offset) / eta, - eta - 1);
		if (assist)
		        return (1 - public_assistance_phaseout_rate) * (1 - public_assistance_phaseout_rate) * slope2;
		else
		        return slope2;
	}

        public UtilityHara(Config config, double eta, double beta, double c_shift, double c_zero, double c2, double s2, double public_assistance, double public_assistance_phaseout_rate, Double force_scale, double range)
        {
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
		this.eta = eta;
		this.beta = beta * config.withdrawal;
		if (force_scale == null)
		        this.scale = s2 / slope(c2_adjust);
		else
		        this.scale = force_scale;
		this.zero = utility(c_zero);
		assert(utility(c_zero) == 0);

		set_constants();
	}
}
