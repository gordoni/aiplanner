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

public class Exp_offset_scale extends Scale
{
        private double log_scaling_factor;
        private double scaling_factor;
        private double offset;
        private double zero_bucket;

        public Exp_offset_scale(double zero_bucket_size, double scaling_factor)
        {
                super(zero_bucket_size);
                this.scaling_factor = scaling_factor;
                this.log_scaling_factor = Math.log(scaling_factor); // Minor speedup.
                this.offset = zero_bucket_size / (scaling_factor - 1.0);
                this.zero_bucket = Math.log(offset) / log_scaling_factor;
        }

        public double bucket_to_pf(int bucket)
        {
                if (bucket < 0.0)
                        return Math.pow(scaling_factor, zero_bucket - bucket) - offset;
                else if (bucket == 0)
                        return 0;
                else
                        return offset - Math.pow(scaling_factor, zero_bucket + bucket);
        }

        public double pf_to_fractional_bucket(double pf)
        {
                if (pf > 0.0)
                        return - Math.log(offset + pf) / log_scaling_factor + zero_bucket;
                else
                        return Math.log(offset - pf) / log_scaling_factor - zero_bucket;
        }
}
