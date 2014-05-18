package com.gordoni.opal;

import org.apache.commons.math3.special.Erf;

public class UtilityJoinAra extends Utility
{
        // Join with linear interpolation of ARA across the join region.

        private Config config;
        private Utility utility1;
        private Utility utility2;
        private double c1;
        private double c2;
        private double a; // - ARA = u'' / u' = a c + b.
        private double b;
        private double scale = 1;
        private double u_scale;
        private double zero1 = 0;
        private double zero2 = 0;
        private double u1;
        private double u2;

        public double utility(double c)
        {
	        assert(c >= 0);
		if (c < c1 || (c == c1 && c1 == c2))
		        return utility1.utility(c);
		else if (c > c2)
		        return utility2.utility(c) - zero2;
		else
		        return u_scale * Erf.erf((a * c + b) / Math.sqrt(2 * a)) - zero1;
        }

        public double inverse_utility(double u)
	{
	        if (u < u1)
		        return utility1.inverse_utility(u);
		else if (u >= u2)
		        return utility2.inverse_utility(u + zero2);
		else
		        return (Erf.erfInv((u + zero1) / u_scale) * Math.sqrt(2 * a) - b) / a;
	}

        public double slope(double c)
        {
	        assert(c >= 0);
		if (c < c1)
		        return utility1.slope(c);
		else if (c >= c2)
		        return utility2.slope(c);
		else
		        return scale * Math.exp(a * c * c / 2 + b * c);
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
		else if (c >= c2)
		        return utility2.slope2(c);
		else
		        return (a * c + b) * slope(c);
	}

        public UtilityJoinAra(Config config, Utility utility1, Utility utility2, double c1, double c2)
        {
		this.config = config;
		this.utility1 = utility1;
		this.utility2 = utility2;
	        this.range = utility1.range;

		this.c1 = c1;
		this.c2 = c2;

		if (c1 < c2)
	        {
			double neg_ara1 = utility1.slope2(c1) / utility1.slope(c1);
			double neg_ara2 = utility2.slope2(c2) / utility2.slope(c2);
			this.a = (neg_ara1 - neg_ara2) / (c1 - c2);
			this.b = neg_ara1 - a * c1;
			this.scale = utility1.slope(c1) / slope(c1);
			this.u_scale = scale * Math.sqrt(Math.PI / (2 * a)) * Math.exp(- b * b / (2 * a));
			this.zero1 = utility(c1) - utility1.utility(c1);
		}
		this.zero2 = utility2.utility(c2) - utility(c2);

		this.u1 = utility(c1);
		this.u2 = utility(c2);

		set_constants();
	}
}
