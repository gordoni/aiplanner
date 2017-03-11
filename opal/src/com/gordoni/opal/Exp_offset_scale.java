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

public class Exp_offset_scale extends Scale
{
        private double min_value;
        private boolean has_zero;
        private double log_scaling_factor;
        private double scaling_factor;
        private double offset;
        private double zero_bucket;

        public Exp_offset_scale(double zero_bucket_size, double min_value, double max_value, boolean has_zero, double scaling_factor)
        {
                super(zero_bucket_size);
                this.min_value = ((has_zero || min_value != 0) ? min_value : zero_bucket_size);
                this.has_zero = has_zero;
                this.scaling_factor = scaling_factor;
                this.log_scaling_factor = Math.log(scaling_factor);
                double zero_offset = zero_bucket_size / (scaling_factor - 1.0);
                this.zero_bucket = Math.log(zero_offset) / log_scaling_factor;
                this.offset = zero_offset - this.min_value;
                this.first_bucket = pf_to_bucket(max_value, "up");
                this.num_buckets = pf_to_bucket(this.min_value, ((has_zero || min_value != 0) ? "down" : "round")) - this.first_bucket + 1;
        }

        public double bucket_to_pf(int bucket)
        {
                // // Intersting things happen either side of portfolio size zero.
                // // So we need to iterpolate tightly on either side of this transition.
                // if (bucket > 0)
                //         return offset - Math.pow(scaling_factor, zero_bucket + bucket);
                // else if (has_zero && (bucket == 0))
                //         return 0;
                // else
                //         return Math.pow(scaling_factor, zero_bucket - bucket + (has_zero ? 0 : 1)) - offset;
                if (bucket < 0)
                        return Math.pow(scaling_factor, zero_bucket - bucket) - offset;
                else
                        return min_value;
        }

        public double pf_to_fractional_bucket(double pf)
        {
                // if (pf > 0)
                //         return - Math.log(offset + pf) / log_scaling_factor + zero_bucket + (has_zero ? 0 : 1);
                // else if (pf == 0)
                //         return 0;
                // else
                //         return Math.log(offset - pf) / log_scaling_factor - zero_bucket;
                return - Math.log(offset + pf) / log_scaling_factor + zero_bucket;
        }
}
