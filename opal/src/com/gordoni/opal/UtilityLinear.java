package com.gordoni.opal;

public class UtilityLinear extends Utility
{
        private double public_assistance;
        private double public_assistance_phaseout_rate;
        private double slope;
        private double zero;

        public double utility(double c)
        {
	        assert(c >= 0);
	       return (c - zero) * slope;
        }

        public double inverse_utility(double u)
	{
	        if (slope == 0)
		{
		        assert(u == 0);
		        return zero;
		}
		else
		        return zero + u / slope;
	}

        public double slope(double c)
        {
	        assert(c >= 0);
		return slope;
	}

        public double inverse_slope(double s)
        {
	        assert(s == slope);
		return 0;
	}

        public UtilityLinear(double c_zero, double s, double range)
        {
	        this.range = range;
		this.public_assistance = public_assistance;
		this.public_assistance_phaseout_rate = public_assistance_phaseout_rate;
		this.slope = s;
		this.zero = c_zero;

		set_constants();
	}
}
