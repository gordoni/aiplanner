package com.gordoni.opal;

public class UtilityScale extends Utility
{
        private Config config;
        private Utility utility;
        private double c_scale;
        private double scale;
        private double offset;
        private double zero = 0;

        public double utility(double c)
        {
	        assert(c >= 0);
		return scale * utility.utility(c_scale * c - offset) - zero;
        }

        public double inverse_utility(double u)
	{
	        if (scale == 0)
		{
		        assert(u == - zero);
		        return 0;
		}
		else
		        return (utility.inverse_utility((u + zero) / scale) + offset) / c_scale;
	}

        public double slope(double c)
        {
	        assert(c >= 0);
		return scale * c_scale * utility.slope(c_scale * c - offset);
	}

        public double inverse_slope(double s)
        {
	        if (scale == 0)
		{
		        assert(s == 0);
		        return 0;
		}
		else
		        return (utility.inverse_slope(s / (scale * c_scale)) + offset) / c_scale;
	}

        public double slope2(double c)
        {
	        assert(c >= 0);
		return scale * c_scale * c_scale * utility.slope2(c_scale * c - offset);
	}

        public UtilityScale(Config config, Utility utility, double c_zero, double c_scale, double scale, double offset)
        {
		this.config = config;
		this.utility = utility;
	        this.range = utility.range;
		this.c_scale = c_scale;
		this.scale = scale;
		this.offset = offset;
		this.zero = utility(c_zero);

		set_constants();
	}
}
