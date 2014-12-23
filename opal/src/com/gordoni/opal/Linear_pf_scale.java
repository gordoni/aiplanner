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

public class Linear_pf_scale extends Scale
{
        public Linear_pf_scale(double zero_buffer_size)
        {
                super(zero_buffer_size);
        }

        public double bucket_to_pf(int bucket)
        {
                return - bucket * zero_buffer_size;
        }

        public double pf_to_fractional_bucket(double pf)
        {
                return - pf / zero_buffer_size;
        }
}
