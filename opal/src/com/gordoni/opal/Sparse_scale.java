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

public class Sparse_scale extends Scale
{
        private double low;
        private double high;

        public Sparse_scale(double zero_bucket_size, double max_value)
        {
                super(zero_bucket_size);
                this.low = max_value / 100;
                this.high = max_value;
                this.first_bucket = 0;
                this.num_buckets = 2;
        }

        public double bucket_to_pf(int bucket)
        {
                if (bucket == 0)
                        return high;
                else
                        return low;
        }

        public double pf_to_fractional_bucket(double pf)
        {
                assert(false);
                return -1;
        }
}
