package com.gordoni.opal;

public class UtilityJoin extends Utility
{
        private Config config;
        private Utility utility1;
        private Utility utility2;
        private double u20;
        private double c1;
        private double u1c1;
        private double s1c1;

        // Attempted linear interpolation of slope, but result is too crude to be helpful.

        // Attempted spline interpolation of slope, but the cubic spline going through 2 point slopes and slope slopes need not be monotone.
        // And a monotone spline need not have a specified slope.

        // Now simply take the better of consume or gift.

        public double utility(double c)
        {
	        assert(c >= 0);
		if (c < c1)
		        return utility1.utility(c);
		else
		        return utility2.utility(c - c1) - (u20 - u1c1);
        }

        public double inverse_utility(double u)
	{
	        if (u < utility(c1))
		        return utility1.inverse_utility(u);
		else
		        return utility2.inverse_utility(u + (u20 - u1c1)) + c1;
	}

        public double slope(double c)
        {
	        assert(c >= 0);
		if (c < c1)
		        return utility1.slope(c);
		else
		        return utility2.slope(c - c1);
	}

        public double inverse_slope(double s)
        {
	        // Bug: Not implemented. Method only used for testing so OK.
	        return 0;
	}

        public UtilityJoin(Config config, Utility utility1, Utility utility2)
        {
		this.config = config;
		this.utility1 = utility1;
		this.utility2 = utility2;
	        this.range = utility1.range;

		u20 = utility2.utility(0);

		double s20 = utility2.slope(0);
		double low = 0;
		double high = config.pf_guaranteed;
		double mid;
		while (true)
		{
			mid = (low + high) / 2;
			if (mid == low || mid == high)
				break;
			if (s20 > utility1.slope(mid))
				high = mid;
			else
				low = mid;
		}
		c1 = mid;

		u1c1 = utility1.utility(c1);
		s1c1 = utility1.slope(c1);

		set_constants();
	}
}
