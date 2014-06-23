package com.gordoni.opal;

import org.apache.commons.math3.analysis.BivariateFunction;
import org.apache.commons.math3.analysis.interpolation.BicubicSplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.BivariateGridInterpolator;

class BiInterpolator extends Interpolator
{
        MapPeriod mp;

        BivariateFunction f;

        public double value(double[] p)
        {
	        double x = p[0];
		x = Math.max(x, mp.floor[0]);
		x = Math.min(x, mp.ceiling[0]);
	        double y = p[1];
		y = Math.max(y, mp.floor[1]);
		y = Math.min(y, mp.ceiling[1]);
	        return f.value(x, y);
        }

        public BiInterpolator(MapPeriod mp, int what)
        {
	        this.mp = mp;

	        Scenario scenario = mp.scenario;
		Config config = scenario.config;

		double[] xval = new double[mp.length[0]];
		for (int i = 0; i < xval.length; i++)
		        xval[(xval.length - 1) - i] = scenario.scale[0].bucket_to_pf(mp.bottom[0] + i);
		double[] yval = new double[mp.length[1]];
		for (int i = 0; i < yval.length; i++)
		        yval[(yval.length - 1) - i] = scenario.scale[1].bucket_to_pf(mp.bottom[1] + i);

		double[][] fval = new double[mp.length[0]][mp.length[1]];
		MapPeriodIterator<MapElement> mpitr = mp.iterator();
		while (mpitr.hasNext())
		{
			int[] bucket = mpitr.nextIndex().clone();
			MapElement me = mpitr.next();
			int xindex = (xval.length - 1) - (bucket[0] - mp.bottom[0]);
			int yindex = (yval.length - 1) - (bucket[1] - mp.bottom[1]);
		        fval[xindex][yindex] = getWhat(me, what);
		}

		BivariateGridInterpolator interpolator;
		if (config.interpolation.equals("spline"))
		        interpolator = new BicubicSplineInterpolator();
		else
		{
		        assert(false);
			return;
		}

		this.f = interpolator.interpolate(xval, yval, fval);
	}
}
