/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2016 Gordon Irlam
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

import java.util.List;

public class SimulateResult implements Cloneable
{
        public Metrics metrics;
        public double spend;
        public double consume;
        public double first_payout;
        public List<List<PathElement>> paths;
        public String metrics_str;

        public SimulateResult clone()
        {
                SimulateResult res = null;
                try
                {
                        res = (SimulateResult) super.clone();
                }
                catch (CloneNotSupportedException e)
                {
                        assert(false);
                }

                return res;
        }

    public SimulateResult(Metrics metrics, double spend, double consume, double first_payout, List<List<PathElement>> paths, String metrics_str)
        {
                this.metrics = metrics;
                this.spend = spend;
                this.consume = consume;
                this.first_payout = first_payout;
                this.paths = paths;
                this.metrics_str = metrics_str;
        }
}
