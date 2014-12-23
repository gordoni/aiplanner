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

public class SearchBucket implements Comparable<SearchBucket>
{
        int[] bucket;
        double[] aa;

        public SearchBucket(int[] bucket, double[] aa)
        {
                this.bucket = bucket;
                this.aa = aa;
        }

        public int compareTo(SearchBucket that)
        {
                for (int i = 0; i < bucket.length; i++)
                {
                        int compare = this.bucket[i] - that.bucket[i];
                        if (compare != 0)
                                return compare;
                }
                for (int i = 0; i < aa.length; i++)
                {
                        double compare = this.aa[i] - that.aa[i];
                        if (compare > 0)
                                return 1;
                        else if (compare < 0)
                                return -1;
                }
                return 0;
        }
}

