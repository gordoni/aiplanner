package com.gordoni.opal;

import java.util.Arrays;

class BiNoInterpolator extends Interpolator
{
        MapPeriod mp;

        double xval[];
        double yval[];
        double fval[][];

        public double value(double[] p)
        {
	        double x = p[0];
		x = Math.max(x, mp.floor[0]);
		x = Math.min(x, mp.ceiling[0]);
	        double y = p[1];
		y = Math.max(y, mp.floor[1]);
		y = Math.min(y, mp.ceiling[1]);
		int xindex = Arrays.binarySearch(xval, x);
		if (xindex < 0)
		        xindex = - xindex - 2;
		int yindex = Arrays.binarySearch(yval, y);
		if (yindex < 0)
		        yindex = - yindex - 2;
		double v = fval[xindex][yindex];
		return v;
        }

        public BiNoInterpolator(MapPeriod mp, int what)
        {
	        this.mp = mp;

	        Scenario scenario = mp.scenario;
		Config config = scenario.config;

		xval = new double[mp.length[0]];
		for (int i = 0; i < xval.length; i++)
		        xval[(xval.length - 1) - i] = scenario.scale[0].bucket_to_pf(mp.bottom[0] + i);
		yval = new double[mp.length[1]];
		for (int i = 0; i < yval.length; i++)
		        yval[(yval.length - 1) - i] = scenario.scale[1].bucket_to_pf(mp.bottom[1] + i);

		fval = new double[mp.length[0]][mp.length[1]];
		MapPeriodIterator<MapElement> mpitr = mp.iterator();
		while (mpitr.hasNext())
		{
			int[] bucket = mpitr.nextIndex().clone();
			MapElement me = mpitr.next();
			int xindex = (xval.length - 1) - (bucket[0] - mp.bottom[0]);
			int yindex = (yval.length - 1) - (bucket[1] - mp.bottom[1]);
		        fval[xindex][yindex] = getWhat(me, what);
		}
	}
}
