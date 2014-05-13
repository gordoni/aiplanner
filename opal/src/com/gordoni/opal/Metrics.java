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

        public Metrics(double tw_goal, double ntw_goal, double consume_goal, double inherit_goal, double combined_goal, double tax_goal, double cost)
        {
		metrics[MetricsEnum.TW.ordinal()] = tw_goal;
		metrics[MetricsEnum.NTW.ordinal()] = ntw_goal;
		metrics[MetricsEnum.CONSUME.ordinal()] = consume_goal;
		metrics[MetricsEnum.INHERIT.ordinal()] = inherit_goal;
		metrics[MetricsEnum.COMBINED.ordinal()] = combined_goal;
		metrics[MetricsEnum.TAX.ordinal()] = tax_goal;
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
