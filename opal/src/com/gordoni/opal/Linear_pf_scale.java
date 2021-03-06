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

public class Linear_pf_scale extends Scale
{
        public Linear_pf_scale(double zero_bucket_size, double min_value, double max_value)
        {
                super(zero_bucket_size);
                this.first_bucket = pf_to_bucket(max_value, "up");
                this.num_buckets = pf_to_bucket(min_value, "down") - this.first_bucket + 1;
        }

        public double bucket_to_pf(int bucket)
        {
                return - bucket * zero_bucket_size;
        }

        public double pf_to_fractional_bucket(double pf)
        {
                return - pf / zero_bucket_size;
        }
}
