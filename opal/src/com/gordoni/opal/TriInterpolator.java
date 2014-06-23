package com.gordoni.opal;

import org.apache.commons.math3.analysis.TrivariateFunction;
import org.apache.commons.math3.analysis.interpolation.TricubicSplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.TrivariateGridInterpolator;

class TriInterpolator extends Interpolator
{
        MapPeriod mp;

        TrivariateFunction f;

        public double value(double[] p)
        {
	        double x = p[0];
		x = Math.max(x, mp.floor[0]);
		x = Math.min(x, mp.ceiling[0]);
	        double y = p[1];
		y = Math.max(y, mp.floor[1]);
		y = Math.min(y, mp.ceiling[1]);
	        double z = p[2];
		z = Math.max(z, mp.floor[2]);
		z = Math.min(z, mp.ceiling[2]);
	        return f.value(x, y, z);
        }

        public TriInterpolator(MapPeriod mp, int what)
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
		double[] zval = new double[mp.length[2]];
		for (int i = 0; i < zval.length; i++)
		        zval[(zval.length - 1) - i] = scenario.scale[2].bucket_to_pf(mp.bottom[2] + i);

		double[][][] fval = new double[mp.length[0]][mp.length[1]][mp.length[2]];
		MapPeriodIterator<MapElement> mpitr = mp.iterator();
		while (mpitr.hasNext())
		{
			int[] bucket = mpitr.nextIndex().clone();
			MapElement me = mpitr.next();
			int xindex = (xval.length - 1) - (bucket[0] - mp.bottom[0]);
			int yindex = (yval.length - 1) - (bucket[1] - mp.bottom[1]);
			int zindex = (zval.length - 1) - (bucket[2] - mp.bottom[2]);
		        fval[xindex][yindex][zindex] = getWhat(me, what);
		}

		TrivariateGridInterpolator interpolator;
		if (config.interpolation.equals("spline"))
		        interpolator = new TricubicSplineInterpolator();
		else
		{
		        assert(false);
			return;
		}

		this.f = interpolator.interpolate(xval, yval, zval, fval);
	}
}
