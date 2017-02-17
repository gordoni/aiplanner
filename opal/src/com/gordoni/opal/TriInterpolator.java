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

import org.apache.commons.math3.analysis.TrivariateFunction;
import org.apache.commons.math3.analysis.interpolation.TricubicInterpolator;
import org.apache.commons.math3.analysis.interpolation.TrivariateGridInterpolator;

class TriInterpolator extends Interpolator
{
        double xval[];
        double yval[];
        double zval[];
        double fval[][][];

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
                double v = f.value(x, y, z);
                int xindex = Arrays.binarySearch(xval, x);
                if (xindex < 0)
                        xindex = - xindex - 2;
                int yindex = Arrays.binarySearch(yval, y);
                if (yindex < 0)
                        yindex = - yindex - 2;
                int zindex = Arrays.binarySearch(zval, z);
                if (zindex < 0)
                        zindex = - zindex - 2;
                double fmin = fval[xindex][yindex][zindex];
                double fmax = fval[xindex][yindex][zindex];
                if (xindex + 1 < xval.length)
                {
                        fmin = Math.min(fmin, fval[xindex + 1][yindex][zindex]);
                        fmax = Math.max(fmax, fval[xindex + 1][yindex][zindex]);
                }
                if (yindex + 1 < yval.length)
                {
                        fmin = Math.min(fmin, fval[xindex][yindex + 1][zindex]);
                        fmax = Math.max(fmax, fval[xindex][yindex + 1][zindex]);
                }
                if (zindex + 1 < zval.length)
                {
                        fmin = Math.min(fmin, fval[xindex][yindex][zindex + 1]);
                        fmax = Math.max(fmax, fval[xindex][yindex][zindex + 1]);
                }
                if (xindex + 1 < xval.length && yindex + 1 < yval.length)
                {
                        fmin = Math.min(fmin, fval[xindex + 1][yindex + 1][zindex]);
                        fmax = Math.max(fmax, fval[xindex + 1][yindex + 1][zindex]);
                }
                if (xindex + 1 < xval.length && zindex + 1 < zval.length)
                {
                        fmin = Math.min(fmin, fval[xindex + 1][yindex][zindex + 1]);
                        fmax = Math.max(fmax, fval[xindex + 1][yindex][zindex + 1]);
                }
                if (yindex + 1 < yval.length && zindex + 1 < zval.length)
                {
                        fmin = Math.min(fmin, fval[xindex][yindex + 1][zindex + 1]);
                        fmax = Math.max(fmax, fval[xindex][yindex + 1][zindex + 1]);
                }
                if (xindex + 1 < xval.length && yindex + 1 < yval.length && zindex + 1 < zval.length)
                {
                        fmin = Math.min(fmin, fval[xindex + 1][yindex + 1][zindex + 1]);
                        fmax = Math.max(fmax, fval[xindex + 1][yindex + 1][zindex + 1]);
                }
                v = Math.max(v, fmin);
                v = Math.min(v, fmax);
                return v;
        }

        public TriInterpolator(MapPeriod mp, int what)
        {
                super(mp, what);

                Scenario scenario = mp.scenario;
                Config config = scenario.config;

                xval = new double[mp.length[0]];
                for (int i = 0; i < xval.length; i++)
                        xval[(xval.length - 1) - i] = scenario.scale[0].bucket_to_pf(mp.bottom[0] + i);
                yval = new double[mp.length[1]];
                for (int i = 0; i < yval.length; i++)
                        yval[(yval.length - 1) - i] = scenario.scale[1].bucket_to_pf(mp.bottom[1] + i);
                zval = new double[mp.length[2]];
                for (int i = 0; i < zval.length; i++)
                        zval[(zval.length - 1) - i] = scenario.scale[2].bucket_to_pf(mp.bottom[2] + i);

                fval = new double[mp.length[0]][mp.length[1]][mp.length[2]];
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
                if (config.interpolation3.equals("spline"))
		    interpolator = new TricubicInterpolator();
                else
                {
                        assert(false);
                        return;
                }

                this.f = interpolator.interpolate(xval, yval, zval, fval);
        }
}
