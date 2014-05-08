package com.gordoni.opal;

import java.util.Arrays;
import java.util.Comparator;

public class RiskReward
{
        public double[] aa;

        public double mean;

        public double std_dev;

        public RiskReward(double[] aa, double mean, double std_dev)
        {
	        this.aa = aa;
	        this.mean = mean;
	        this.std_dev = std_dev;
	}

        public static Comparator<RiskReward> MeanComparator = new Comparator<RiskReward>()
        {
	        public int compare(RiskReward a, RiskReward b)
		{
		    return a.mean < b.mean ? -1 : (a.mean == b.mean ? (a.std_dev > b.std_dev ? -1 : (a.std_dev == b.std_dev ? 0 : 1)) : 1);
		}
	};

        public String toString()
        {
	        return Arrays.toString(aa) + " " + mean + " +/- " + std_dev;
	}
}
