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

public class AAMapStatic extends AAMap
{
        public AAMapStatic(Scenario scenario, String aa_strategy, AAMap aamap1, AAMap aamap2, VitalStats validate_stats, Utility uc_time, Utility uc_risk, double guaranteed_income)
        {
                super(scenario, aamap1, aamap2, null, validate_stats, uc_time, uc_risk, guaranteed_income);

                assert(scenario.start_p.length == 1 && scenario.tp_index != null);

                map = new MapPeriod[(int) (scenario.ss.max_years * config.generate_time_periods)];

                for (int pi = 0; pi < map.length; pi++)
                {
                        double age = (double) (pi + config.start_age * config.generate_time_periods) / config.generate_time_periods;
                        map[pi] = new MapPeriod(this, pi);
                        for (int bi = 0; bi < map[pi].length[scenario.tp_index]; bi++)
                        {
                                int[] bucket = new int[scenario.start_p.length];
                                bucket[scenario.tp_index] = map[pi].bottom[scenario.tp_index] + bi;
                                double[] p = scenario.bucketToP(bucket);
                                double[] aa = generate_aa(aa_strategy, age, p);
                                MapElement me = new MapElement(p, aa, null, null, null);
                                map[pi].set(bucket, me);
                        }
                        map[pi].interpolate(false);
                }
        }
}
