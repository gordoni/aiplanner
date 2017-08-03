/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2017 Gordon Irlam
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

package com.gordoni.opal;

import java.util.Arrays;

import org.apache.commons.math3.analysis.UnivariateFunction;
import org.apache.commons.math3.analysis.polynomials.PolynomialSplineFunction;
import org.apache.commons.math3.analysis.interpolation.SplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.UnivariateInterpolator;

class LSInterpolator extends Interpolator
{
        boolean linear_spline;

        double xval[];
        double yval[];
        double fval[][];

        PolynomialSplineFunction f[];
        UnivariateFunction s[];

        public double value(double[] p)
        {
                double x_init = p[0];
                double xmin = mp.floor[0];
                double xmax = mp.ceiling[0];
                boolean x_in_range = xmin <= x_init && x_init <= xmax;
                double x = Math.max(x_init, xmin);
                x = Math.min(x, xmax);
                double y_init = p[1];
                double ymin = mp.floor[1];
                double ymax = mp.ceiling[1];
                boolean y_in_range = ymin <= y_init && y_init <= ymax;
                double y = Math.max(y_init, ymin);
                y = Math.min(y, ymax);
                if (!linear_spline)
                {
                        // spline-linear.
                        double tmp = x;
                        x = y;
                        y = tmp;
                        double tmp_init = x_init;
                        x_init = y_init;
                        y_init = tmp_init;
                        boolean tmp_in_range = x_in_range;
                        x_in_range = y_in_range;
                        y_in_range = tmp_in_range;
                }
                int xindex = Arrays.binarySearch(xval, x_init);
                if (xindex < 0)
                        if (xindex == -1)
                                xindex = 0;
                        else
                                xindex = - xindex - 2;
                int x1;
                int x2;
                if (xindex + 1 > xval.length - 1)
                {
                        x1 = xindex - 1;
                        x2 = xindex;
                }
                else
                {
                        x1 = xindex;
                        x2 = xindex + 1;
                }
                double v1 = f[x1].value(y);
                double v2 = f[x2].value(y);
                double x_use;
                x_use = x;
                if (config.interpolation_extrapolate)
                        if (((x < x_init) && (what != metric_interp_index)) ||
                            (x_init < x))
                                x_use = x_init;
                double v = v1 + (x_use - xval[x1]) / (xval[x2] - xval[x1]) * (v2 - v1);
                if (y_in_range)
                {
                        if (x_in_range)
                        {
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
                        }
                }
                else if (config.interpolation_extrapolate)
                {
                        if (((y < y_init) && (what != metric_interp_index)) ||
                            (y_init < y))
                        {
                                double s1 = s[x1].value(y);
                                double s2 = s[x2].value(y);
                                double slope = s1 + (x_init - xval[x1]) / (xval[x2] - xval[x1]) * (s2 - s1);
                                v += (y_init - y) * slope;
                        }
                }
                assert(!Double.isNaN(v));
                return v;
        }

        public LSInterpolator(MapPeriod mp, int what, boolean linear_spline)
        {
                super(mp, what);

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
                        double val = getWhat(me, what);
                        // Spline maps infinities to nans, so we need to avoid them.
                        val = Math.max(-1e300, val);
                        // When interpolate_ce is true positive infinities may exist over a range of portfolio sizes.
                        // Capping them would result in a non-monotone spline which leads to allocation failure.
                        assert(!Double.isInfinite(val));
                        fval[xindex][yindex] = val;
                }
                if (!linear_spline)
                {
                        // spline-linear.
                        double tmp[] = xval;
                        xval = yval;
                        yval = tmp;
                        fval = Utils.zipDoubleArrayArray(fval);
                }

                this.f = new PolynomialSplineFunction[fval.length];
                this.s = new UnivariateFunction[fval.length];
                for (int i = 0; i < fval.length; i++)
                {
                        SplineInterpolator interpolator = new SplineInterpolator();
                        this.f[i] = interpolator.interpolate(yval, fval[i]);
                        this.s[i] = this.f[i].derivative();
                }
        }
}
