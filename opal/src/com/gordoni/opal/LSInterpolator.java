package com.gordoni.opal;

import java.util.Arrays;

import org.apache.commons.math3.analysis.UnivariateFunction;
import org.apache.commons.math3.analysis.interpolation.SplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.UnivariateInterpolator;

class LSInterpolator extends Interpolator
{
        MapPeriod mp;
        boolean linear_spline;

        double xval[];
        double yval[];
        double fval[][];

        UnivariateFunction f[];

        public double value(double[] p)
        {
                double x = p[0];
                x = Math.max(x, mp.floor[0]);
                x = Math.min(x, mp.ceiling[0]);
                double y = p[1];
                y = Math.max(y, mp.floor[1]);
                y = Math.min(y, mp.ceiling[1]);
                if (!linear_spline)
                {
                        // spline-linear.
                        double tmp = x;
                        x = y;
                        y = tmp;
                }
                int xindex = Arrays.binarySearch(xval, x);
                if (xindex < 0)
                        xindex = - xindex - 2;
                int x1;
                int x2;
                if (xindex + 1 > xval.length - 1)
                {
                        x1 = xindex;
                        x2 = xindex - 1;
                }
                else
                {
                        x1 = xindex;
                        x2 = xindex + 1;
                }
                double v1 = f[x1].value(y);
                double v2 = f[x2].value(y);
                double v = v1 + (x - xval[x1]) / (xval[x2] - xval[x1]) * (v2 - v1);
                int yindex = Arrays.binarySearch(yval, y);
                if (yindex < 0)
                        yindex = - yindex - 2;
                double fmin = Math.min(fval[x1][yindex], fval[x2][yindex]);
                double fmax = Math.max(fval[x1][yindex], fval[x2][yindex]);
                if (yindex + 1 < yval.length)
                {
                        fmin = Math.min(fmin, fval[x1][yindex + 1]);
                        fmin = Math.min(fmin, fval[x2][yindex + 1]);
                        fmax = Math.max(fmax, fval[x1][yindex + 1]);
                        fmax = Math.max(fmax, fval[x2][yindex + 1]);
                }
                v = Math.max(v, fmin);
                v = Math.min(v, fmax);
                return v;
        }

        public LSInterpolator(MapPeriod mp, int what, boolean linear_spline)
        {
                this.mp = mp;
                this.linear_spline = linear_spline;

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
                if (!linear_spline)
                {
                        // spline-linear.
                        double tmp[] = xval;
                        xval = yval;
                        yval = tmp;
                        fval = Utils.zipDoubleArrayArray(fval);
                }

                this.f = new UnivariateFunction[fval.length];
                for (int i = 0; i < fval.length; i++)
                {
                        UnivariateInterpolator interpolator;
                        interpolator = new SplineInterpolator();
                        this.f[i] = interpolator.interpolate(yval, fval[i]);
                }
        }
}
