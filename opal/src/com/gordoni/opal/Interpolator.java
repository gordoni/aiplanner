/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2016 Gordon Irlam
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

abstract class Interpolator
{
        // What to interpolate:
        public static final int metric_interp_index = -1;
        public static final int spend_interp_index = -2;
        public static final int consume_interp_index = -3;
        public static final int first_payout_interp_index = -4;
        // 0..normal_assets-1 - asset class allocation fractions
        // ria_aa_index - ria purchase fraction
        // nia_aa_index - nia purchase fraction
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
                else if (what == first_payout_interp_index)
                        return me.first_payout;

                assert(false);
                return 0;
        }

        abstract double value(double[] p);

        public static Interpolator factory(MapPeriod mp, boolean generate, int what)
        {
                Scenario scenario = mp.scenario;
                Config config = scenario.config;

                if (mp.config.interpolation_linear)
                        return null;
                if (mp.length.length == 1)
                        return new UniInterpolator(mp, what);
                else if (mp.length.length == 2)
                {
                        if (!generate && !config.interpolation_validate)
                                return new BiNoInterpolator(mp, what);
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
