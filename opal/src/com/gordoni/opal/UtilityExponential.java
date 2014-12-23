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

public class UtilityExponential extends Utility
{
        private Config config;
        private double public_assistance;
        private double public_assistance_phaseout_rate;
        private double offset;
        private double alpha;
        private double scale;
        private double zero = 0;

        public double utility(double c)
        {
                assert(c >= 0);
                double effective_c;
                if (c * public_assistance_phaseout_rate < public_assistance)
                        effective_c = public_assistance + c * (1 - public_assistance_phaseout_rate);
                else
                        effective_c = c;
                return - scale * Math.exp(- alpha * effective_c) - zero;
        }

        public double inverse_utility(double u)
        {
                double c;
                if (scale == 0)
                {
                        assert(u == - zero);
                        c = 0;
                }
                else if (- u - zero <= 0)
                        c = Double.POSITIVE_INFINITY;
                else
                        c = - Math.log((- u - zero) / scale) / alpha;
                if (c * public_assistance_phaseout_rate < public_assistance)
                        return (c - public_assistance) / (1 - public_assistance_phaseout_rate);
                else
                        return c;
        }

        public double slope(double c)
        {
                assert(c >= 0);
                boolean assist = c * public_assistance_phaseout_rate < public_assistance;
                if (assist)
                        c = public_assistance + c * (1 - public_assistance_phaseout_rate);
                double slope = scale * alpha * Math.exp(- alpha * c);
                if (assist)
                        return (1 - public_assistance_phaseout_rate) * slope;
                else
                        return slope;
        }

        public double inverse_slope(double s)
        {
                // Bug: need to adjust s for public assistance; but method only used for testing so OK.
                double c;
                if (scale == 0)
                {
                        assert(s == 0);
                        c = 0;
                }
                else
                        c = - Math.log(s / (scale * alpha)) / alpha;
                if (c * public_assistance_phaseout_rate < public_assistance)
                        return (c - public_assistance) / (1 - public_assistance_phaseout_rate);
                else
                        return c;
        }

        public double slope2(double c)
        {
                assert(c >= 0);
                boolean assist = c * public_assistance_phaseout_rate < public_assistance;
                if (assist)
                        c = public_assistance + c * (1 - public_assistance_phaseout_rate);
                double slope2 = - scale * alpha * alpha * Math.exp(- alpha * c);
                if (assist)
                        return (1 - public_assistance_phaseout_rate) * (1 - public_assistance_phaseout_rate) * slope2;
                else
                        return slope2;
        }

        public UtilityExponential(Config config, Double force_alpha, double c_shift, double c_zero, double c1, double s1, double c2, double s2, double public_assistance, double public_assistance_phaseout_rate)
        {
                double c1_adjust = c1;
                double s1_adjust = s1;
                if (c1 * public_assistance_phaseout_rate < public_assistance)
                {
                        c1_adjust = public_assistance + c1 * (1 - public_assistance_phaseout_rate);
                }
                double c2_adjust = c2;
                double s2_adjust = s2;
                if (c2 * public_assistance_phaseout_rate < public_assistance)
                {
                        c2_adjust = public_assistance + c2 * (1 - public_assistance_phaseout_rate);
                }
                this.config = config;
                this.public_assistance = public_assistance;
                this.public_assistance_phaseout_rate = public_assistance_phaseout_rate;
                this.offset = c_shift; // Irrelevant.
                if (force_alpha != null)
                    this.alpha = force_alpha;
                else
                {
                        if (s1_adjust == s2_adjust)
                        {
                                assert(s1_adjust == 0);
                                this.alpha = 0;
                        }
                        else
                                assert(s1_adjust != Double.POSITIVE_INFINITY);
                                        // public_assistance must be positive if utility_consume_fn="power" and utility_inherit_fn="exponential" unless force_alpha.
                                this.alpha = Math.log(s1_adjust / s2_adjust) / (c2_adjust - c1_adjust);
                }
                if (this.alpha == 0)
                        this.scale = 0;
                else
                        this.scale = s2_adjust / (alpha * Math.exp(- alpha * c2_adjust));
                // Intentionally don't set zero. Having a zero other than 0 causes floating point precision problems. See test in simulate().
                // this.zero = utility(c_zero);
                // assert(utility(c_zero) == 0);

                set_constants();
        }
}
