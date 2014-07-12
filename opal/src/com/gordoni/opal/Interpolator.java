package com.gordoni.opal;

abstract class Interpolator
{
        // What to interpolate:
        public static final int metric_interp_index = -1;
        public static final int spend_interp_index = -2;
        public static final int consume_interp_index = -3;
        // 0..normal_assets-1 - asset class allocation fractions
        // ria_aa_index - ria purchase fraction
        // ria_aa_index - nia purchase fraction
        // spend_fract_index - spend fraction

        protected double getWhat(MapElement me, int what)
        {
	        if (what >= 0)
		        return me.aa[what];
		else if (what == metric_interp_index)
		        return me.metric_sm;
		else if (what == spend_interp_index)
		        return me.spend;
		else if (what == consume_interp_index)
		        return me.consume;

		assert(false);
		return 0;
	}

        abstract double value(double[] p);

        public static Interpolator factory(MapPeriod mp, int what)
        {
	        if (mp.config.interpolation_linear)
		        return null;
		if (mp.length.length == 1)
		        return new UniInterpolator(mp, what);
		else if (mp.length.length == 2)
		{
		        if (mp.config.interpolation2.equals("linear-spline"))
			        return new LSInterpolator(mp, what, true);
		        else if (mp.config.interpolation2.equals("spline-linear"))
			        return new LSInterpolator(mp, what, false);
			else
			        return new BiInterpolator(mp, what);
		}
		else if (mp.length.length == 3)
		        return new TriInterpolator(mp, what);
		else
			assert(false);

		return null;
        }
}
