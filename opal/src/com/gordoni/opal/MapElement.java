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

import java.util.Arrays;
import java.util.List;

public class MapElement implements Cloneable
{
        public double[] rps;

        public double[] aa;

        public double mean; // Reward.
        public double std_dev; // Risk.

        public SimulateResult results;

        // Copy of results.* because results gets deleted to save RAM.
        public double spend;
        public double consume;
        public double first_payout;
        public double metric_sm;

        public List<SearchResult> simulate;

        public SearchCache cache;

        public MapElement(double[] rps, double[] aa, SimulateResult results, List<SearchResult> simulate, SearchCache cache)
        {
                this.rps = rps;
                this.aa = aa;
                this.results = results;
                this.simulate = simulate;
                this.cache = cache;
        }

        public MapElement clone()
        {
                MapElement res = null;
                try
                {
                        res = (MapElement) super.clone();
                }
                catch (CloneNotSupportedException e)
                {
                        assert(false);
                }

                if (res.results != null)
                        res.results = res.results.clone();

                return res;
        }

        public double ria_purchase(Scenario scenario)
        {
                double consume = spend;
                double ria_purchase = 0;
                if (scenario.ria_index != null)
                {
                        ria_purchase = consume * aa[scenario.ria_aa_index];
                }
                return ria_purchase;
        }

        public double nia_purchase(Scenario scenario)
        {
                double consume = spend;
                consume -= ria_purchase(scenario);
                double nia_purchase = 0;
                if (scenario.nia_index != null)
                {
                        nia_purchase = consume * aa[scenario.nia_aa_index];
                }
                return nia_purchase;
        }

        public String toString()
        {
                String sim_string = null;
                if (simulate != null)
                {
                        StringBuilder sb = new StringBuilder();
                        for (SearchResult res : simulate)
                                sb.append("\n    " + res);
                        sim_string = sb.toString();
                }
                return "========" +
                        "\n  rps: " + Arrays.toString(rps) +
                        "\n  aa: " + Arrays.toString(aa) +
                        "\n  spendable: " + spend +
                        "\n  consume: " + consume +
                        "\n  first_payout: " + first_payout +
                        "\n  metric_sm: " + metric_sm +
                        (results == null ? "" : "\n  metrics: " + results.metrics) +
                        (sim_string == null ? "" : "\n  simulate: " + sim_string) +
                        "\n";
        }
}
