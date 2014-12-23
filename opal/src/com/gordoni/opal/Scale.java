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

public abstract class Scale
{
        protected double zero_buffer_size;

        public Scale(double zero_buffer_size)
        {
                this.zero_buffer_size = zero_buffer_size;
        }

        public abstract double bucket_to_pf(int bucket);

        public abstract double pf_to_fractional_bucket(double pf);

        public int pf_to_bucket(double pf)
        {
                return pf_to_bucket(pf, "up");
        }

        public int pf_to_bucket(double pf, String dir)
        {
                double fractional_bucket = pf_to_fractional_bucket(pf);
                if (dir.equals("up"))
                        return (int) Math.ceil(fractional_bucket);
                else if (dir.equals("down"))
                        return (int) Math.floor(fractional_bucket);
                else
                        return (int) Math.floor(fractional_bucket + 0.5);
        }

        public static Scale scaleFactory(double zero_bucket_size, double scaling_factor)
        {
                if (scaling_factor == 1.0)
                        // Runs 15% faster by taking advantage of this special case.
                        return new Linear_pf_scale(zero_bucket_size);
                else
                        return new Exp_offset_scale(zero_bucket_size, scaling_factor);
        }
}
