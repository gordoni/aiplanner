package com.gordoni.opal;

import java.util.Arrays;

import org.apache.commons.math3.analysis.UnivariateFunction;
import org.apache.commons.math3.analysis.interpolation.LinearInterpolator;
import org.apache.commons.math3.analysis.interpolation.SplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.UnivariateInterpolator;

class UniInterpolator extends Interpolator
{
        MapPeriod mp;

        double xval[];
        double fval[];

        UnivariateFunction f;

        public double value(double[] p)
        {
                double x = p[0];
                x = Math.max(x, mp.floor[0]);
                x = Math.min(x, mp.ceiling[0]);
                double v = f.value(x);
                // Bound value by surrounding knot values. Otherwise get bad results if metric_sm is non-monotone in p.
                int xindex = Arrays.binarySearch(xval, x);
                if (xindex < 0)
                        xindex = - xindex - 2;
                double fmin = fval[xindex];
                double fmax = fval[xindex];
                if (xindex + 1 < xval.length)
                {
                        fmin = Math.min(fmin, fval[xindex + 1]);
                        fmax = Math.max(fmax, fval[xindex + 1]);
                }
                v = Math.max(v, fmin);
                v = Math.min(v, fmax);
                return v;
        }

        public UniInterpolator(MapPeriod mp, int what)
        {
                this.mp = mp;

                Scenario scenario = mp.scenario;
                Config config = scenario.config;

                xval = new double[mp.length[0]];
                for (int i = 0; i < xval.length; i++)
                        xval[(xval.length - 1) - i] = scenario.scale[0].bucket_to_pf(mp.bottom[0] + i);

                fval = new double[mp.length[0]];
                MapPeriodIterator<MapElement> mpitr = mp.iterator();
                while (mpitr.hasNext())
                {
                        int[] bucket = mpitr.nextIndex().clone();
                        MapElement me = mpitr.next();
                        int xindex = (fval.length - 1) - (bucket[0] - mp.bottom[0]);
                        fval[xindex] = getWhat(me, what);
                }

                UnivariateInterpolator interpolator;
                if (config.interpolation1.equals("linear"))
                        interpolator = new LinearInterpolator();
                else if (config.interpolation1.equals("spline"))
                        interpolator = new SplineInterpolator();
                else
                {
                        assert(false);
                        return;
                }

                this.f = interpolator.interpolate(xval, fval);
        }
}
