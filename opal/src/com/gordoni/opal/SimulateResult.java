package com.gordoni.opal;

import java.util.List;

public class SimulateResult implements Cloneable
{
        public Metrics metrics;
        public double spend;
        public double consume;
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

        public SimulateResult(Metrics metrics, double spend, double consume, List<List<PathElement>> paths, String metrics_str)
        {
                this.metrics = metrics;
                this.spend = spend;
                this.consume = consume;
                this.paths = paths;
                this.metrics_str = metrics_str;
        }
}
