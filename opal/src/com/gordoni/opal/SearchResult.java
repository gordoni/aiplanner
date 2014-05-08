package com.gordoni.opal;

import java.util.Arrays;

public class SearchResult
{
        private double[] aa;
        private double metric;
        private String note;

        public SearchResult(double[] aa, double metric, String note)
        {
	        this.aa = aa;
		this.metric = metric;
		this.note = note;
	}

        public String toString()
	{
	        if (aa == null)
		        return note;
	        else
	                return Arrays.toString(aa) + ", " + metric + ", " + note;
	}
}
