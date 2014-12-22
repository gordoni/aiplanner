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
                        "\n  metric_sm: " + metric_sm +
                        (results == null ? "" : "\n  metrics: " + results.metrics) +
                        (sim_string == null ? "" : "\n  simulate: " + sim_string) +
                        "\n";
        }
}
