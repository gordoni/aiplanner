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

import java.util.EnumMap;

public class Metrics implements Cloneable
{
        // Setting an EnumMap is slow, so we use an array.
        //private EnumMap<MetricsEnum, Double> metrics = new EnumMap<MetricsEnum, Double>(MetricsEnum.class);
        public double[] metrics = new double[MetricsEnum.values().length];

        public Metrics()
        {
        }

        public Metrics(double tw_goal, double ntw_goal, double floor_goal, double upside_goal, double consume_goal, double inherit_goal, double combined_goal, double tax_goal, double wer, double cost)
        {
                metrics[MetricsEnum.TW.ordinal()] = tw_goal;
                metrics[MetricsEnum.NTW.ordinal()] = ntw_goal;
                metrics[MetricsEnum.FLOOR.ordinal()] = floor_goal;
                metrics[MetricsEnum.UPSIDE.ordinal()] = upside_goal;
                metrics[MetricsEnum.CONSUME.ordinal()] = consume_goal;
                metrics[MetricsEnum.INHERIT.ordinal()] = inherit_goal;
                metrics[MetricsEnum.COMBINED.ordinal()] = combined_goal;
                metrics[MetricsEnum.TAX.ordinal()] = tax_goal;
                metrics[MetricsEnum.WER.ordinal()] = wer;
                metrics[MetricsEnum.COST.ordinal()] = cost;
        }

        public Metrics clone()
        {
                Metrics res = null;
                try
                {
                        res = (Metrics) super.clone();
                }
                catch (CloneNotSupportedException e)
                {
                        assert(false);
                }
                res.metrics = metrics.clone();

                return res;
        }

        public double get(MetricsEnum e)
        {
                //return metrics.get(e);
                return metrics[e.ordinal()];
        }

        public void set(MetricsEnum e, double v)
        {
                //metrics.put(e, v);
                metrics[e.ordinal()] = v;
        }

        public double fail_chance()
        {
                return 1.0 - get(MetricsEnum.NTW);
        }

        public double fail_length()
        {
                if (1.0 - get(MetricsEnum.NTW) < 1e-9)
                        return 0.0;
                else
                        return (1.0 - get(MetricsEnum.TW)) / (1.0 - get(MetricsEnum.NTW));
        }

        public String toString()
        {
                StringBuilder sb = new StringBuilder();
                sb.append('{');
                for (MetricsEnum m : MetricsEnum.values())
                {
                        if (m.ordinal() > 0)
                                sb.append(", ");
                        sb.append(m + ": " + get(m));
                }
                sb.append('}');
                return sb.toString();
        }

        public static MetricsEnum to_enum(String s)
        {
                return MetricsEnum.valueOf(s.toUpperCase());
        }
}
