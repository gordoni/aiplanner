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
import org.apache.commons.math3.analysis.interpolation.LinearInterpolator;
import org.apache.commons.math3.analysis.interpolation.SplineInterpolator;
import org.apache.commons.math3.analysis.interpolation.UnivariateInterpolator;

class UniInterpolator extends Interpolator
{
        double before = 0;
        double after = 0;
        double xval[];
        double fval[];

        PolynomialSplineFunction f;
        UnivariateFunction s;

        public double value(double[] p)
        {
                double x_init = p[0];
                double xmin = xval[0];
                double xmax = xval[xval.length - 1];
                boolean in_range = xmin <= x_init && x_init <= xmax;
                double x = Math.max(x_init, xmin);
                x = Math.min(x, xmax);
                double v = f.value(x);
                if (in_range)
                {
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
                }
                else if (x_init < xmin && before != 0)
                {
                        v = before;
                }
                else if (x_init > xmax && after != 0)
                {
                        v = after;
                }
                else if (config.interpolation_extrapolate)
                {
                        // We don't extrapolate oversize metric values as this would cause the metrics to appear larger than they actually are.
                        // This would result in upwardly sloping utility as a function of portfolio size plots.
                        // We don't extrapolate oversize asset allocations (or spend/purchases) as they could become seriously wrong.
                        if ((x < x_init) && (this.what != metric_interp_index) && !(this.what >= 0))
                        {
                                // Extrapolate based on end point derivative.
                                double slope = s.value(x);
                                v += (x_init - x) * slope;
                        }
                }

                return v;
        }

        public UniInterpolator(MapPeriod mp, int what)
        {
                super(mp, what);

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
                        double val = getWhat(me, what);
                        // Spline blows up into NaNs if it contains infinities.
                        // This can occur for utility metrics, which we set to -Infinity when consume <= 0.
                        // We want to continue to interpolate the other splines as the aa values may still reflect min_safe constraints.
                        if ((what != metric_interp_index) || (getWhat(me, what) != Double.NEGATIVE_INFINITY))
                        {
                                fval[xindex] = val;
                        }
                        else
                        {
                                fval[xindex] = Double.NEGATIVE_INFINITY;
                                if (what == metric_interp_index) // Currently always true.
                                        if ((xindex <= 1) && (xval[xindex] != 0))
                                                before = Double.NEGATIVE_INFINITY;
                                        else if ((xindex >= xval.length - 2) && (xval[xindex] != 0))
                                                after = Double.NEGATIVE_INFINITY;
                        }
                }

                int skip_low;
                for (skip_low = (xval[0] != 0 ? 0 : 1); fval[skip_low] == Double.NEGATIVE_INFINITY; skip_low++)
                {
                }
                int skip_high;
                for (skip_high = (xval[fval.length - 1] != 0 ? fval.length - 1 : fval.length - 2); fval[skip_high] == Double.NEGATIVE_INFINITY; skip_high--)
                {
                }
                assert(skip_low <= skip_high);
                xval = Arrays.copyOfRange(xval, skip_low, skip_high + 1);
                fval = Arrays.copyOfRange(fval, skip_low, skip_high + 1);

                if (config.interpolation1.equals("linear"))
                {
                        LinearInterpolator interpolator = new LinearInterpolator();
                        this.f = interpolator.interpolate(xval, fval);
                }
                else if (config.interpolation1.equals("spline"))
                {
                        SplineInterpolator interpolator = new SplineInterpolator();
                        this.f = interpolator.interpolate(xval, fval);
                }
                else
                {
                        assert(false);
                        return;
                }

                this.s = this.f.derivative();
        }
}
