package com.gordoni.opal;

public class UtilityJoin extends Utility
{
        private Config config;
        private Utility utility1;
        private Utility utility2;
        private double c1;
        private double u1c1;
        private double u2c1;

        // Attempted linear interpolation of slope, but result is too crude to be helpful.

        // Attempted spline interpolation of slope, but the cubic spline going through 2 point slopes and slope slopes need not be monotone.
        // And a monotone spline need not have a specified slope.

        // Now simply take utility1 or utility2.

        public double utility(double c)
        {
	        assert(c >= 0);
		if (c < c1)
		        return utility1.utility(c);
		else
		        return utility2.utility(c) - (u2c1 - u1c1);
        }

        public double inverse_utility(double u)
	{
	        if (u < utility(c1))
		        return utility1.inverse_utility(u);
		else
		        return utility2.inverse_utility(u + (u2c1 - u1c1));
	}

        public double slope(double c)
        {
	        assert(c >= 0);
		if (c < c1)
		        return utility1.slope(c);
		else
		        return utility2.slope(c);
	}

        public double inverse_slope(double s)
        {
	        // Bug: Not implemented. Method only used for testing so OK.
	        return 0;
	}

        public double slope2(double c)
        {
	        assert(c >= 0);
		if (c < c1)
		        return utility1.slope2(c);
		else
		        return utility2.slope2(c);
	}

        public UtilityJoin(Config config, Utility utility1, Utility utility2, double join_point)
        {
		this.config = config;
		this.utility1 = utility1;
		this.utility2 = utility2;
	        this.range = utility1.range;

		c1 = join_point;
		u1c1 = utility1.utility(c1);
		u2c1 = utility2.utility(c1);

		set_constants();
	}
}
