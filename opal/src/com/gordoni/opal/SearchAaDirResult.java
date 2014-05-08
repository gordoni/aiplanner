package com.gordoni.opal;

public class SearchAaDirResult
{
        public double[] aa;
        public double contrib;
        public SimulateResult results;
        public boolean both_dir;
        public double biggest_step;

        public SearchAaDirResult(double[] aa, double contrib, SimulateResult results, boolean both_dir, double biggest_step)
	{
		this.aa = aa;
		this.contrib = contrib;
		this.results = results;
		this.both_dir = both_dir;
		this.biggest_step = biggest_step;
	}
}
