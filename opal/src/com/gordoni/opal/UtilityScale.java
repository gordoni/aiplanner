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

public class UtilityScale extends Utility
{
        private Config config;
        private Utility utility;
        private double c_scale;
        private double scale;
        private double offset;
        private double zero = 0;

        public double utility(double c)
        {
                assert(c >= 0);
                return scale * utility.utility(c_scale * c - offset) - zero;
        }

        public double inverse_utility(double u)
        {
                if (scale == 0)
                {
                        assert(u == - zero);
                        return 0;
                }
                else
                        return (utility.inverse_utility((u + zero) / scale) + offset) / c_scale;
        }

        public double slope(double c)
        {
                assert(c >= 0);
                return scale * c_scale * utility.slope(c_scale * c - offset);
        }

        public double inverse_slope(double s)
        {
                if (scale == 0)
                {
                        assert(s == 0);
                        return 0;
                }
                else
                        return (utility.inverse_slope(s / (scale * c_scale)) + offset) / c_scale;
        }

        public double slope2(double c)
        {
                assert(c >= 0);
                return scale * c_scale * c_scale * utility.slope2(c_scale * c - offset);
        }

        public UtilityScale(Config config, Utility utility, double c_zero, double c_scale, double scale, double offset)
        {
                this.config = config;
                this.utility = utility;
                this.c_scale = c_scale;
                this.scale = scale;
                this.offset = offset;
                this.zero = utility(c_zero);

                set_constants();
        }

        public UtilityScale(Config config, Utility utility, double c_scale)
        {
                this.config = config;
                this.utility = utility;
                this.c_scale = c_scale;
                this.scale = 1;
                this.offset = 0;
                this.zero = 0;

                set_constants();
        }
}
