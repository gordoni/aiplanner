package com.gordoni.opal;

import org.apache.commons.math3.analysis.UnivariateFunction;
import org.apache.commons.math3.analysis.interpolation.LinearInterpolator;
import org.apache.commons.math3.analysis.interpolation.SplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.UnivariateInterpolator;

class UniInterpolator extends Interpolator
{
        MapPeriod mp;

        UnivariateFunction f;

        public double value(double[] p)
        {
	        double x = p[0];
		x = Math.max(x, mp.floor[0]);
		x = Math.min(x, mp.ceiling[0]);
	        return f.value(x);
        }

        public UniInterpolator(MapPeriod mp, int what)
        {
	        this.mp = mp;

	        Scenario scenario = mp.scenario;
		Config config = scenario.config;

		double[] xval = new double[mp.length[0]];
		for (int i = 0; i < xval.length; i++)
		        xval[(xval.length - 1) - i] = scenario.scale[0].bucket_to_pf(mp.bottom[0] + i);

		double[] fval = new double[mp.length[0]];
		MapPeriodIterator<MapElement> mpitr = mp.iterator();
		while (mpitr.hasNext())
		{
			int[] bucket = mpitr.nextIndex().clone();
			MapElement me = mpitr.next();
			int xindex = (fval.length - 1) - (bucket[0] - mp.bottom[0]);
			fval[xindex] = getWhat(me, what);
		}

		UnivariateInterpolator interpolator;
		if (config.interpolation.equals("linear-math3"))
		        interpolator = new LinearInterpolator();
		else if (config.interpolation.equals("spline"))
		        interpolator = new SplineInterpolator();
		else
		{
		        assert(false);
			return;
		}

		this.f = interpolator.interpolate(xval, fval);
	}
}
