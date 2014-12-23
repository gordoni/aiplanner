/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2015 Gordon Irlam
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

public class UtilityLinear extends Utility
{
        private double public_assistance;
        private double public_assistance_phaseout_rate;
        private double slope;
        private double zero;

        public double utility(double c)
        {
                assert(c >= 0);
               return (c - zero) * slope;
        }

        public double inverse_utility(double u)
        {
                if (slope == 0)
                {
                        assert(u == 0);
                        return zero;
                }
                else
                        return zero + u / slope;
        }

        public double slope(double c)
        {
                assert(c >= 0);
                return slope;
        }

        public double inverse_slope(double s)
        {
                assert(s == slope);
                return 0;
        }

        public double slope2(double c)
        {
                assert(c >= 0);
                return 0;
        }

        public UtilityLinear(double c_zero, double s)
        {
                this.public_assistance = public_assistance;
                this.public_assistance_phaseout_rate = public_assistance_phaseout_rate;
                this.slope = s;
                this.zero = c_zero;

                set_constants();
        }
}
