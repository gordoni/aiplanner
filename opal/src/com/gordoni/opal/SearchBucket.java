package com.gordoni.opal;

public class SearchBucket implements Comparable<SearchBucket>
{
        int[] bucket;
        double[] aa;

        public SearchBucket(int[] bucket, double[] aa)
        {
	        this.bucket = bucket;
	        this.aa = aa;
	}

	public int compareTo(SearchBucket that)
	{
		for (int i = 0; i < bucket.length; i++)
		{
			int compare = this.bucket[i] - that.bucket[i];
			if (compare != 0)
				return compare;
		}
		for (int i = 0; i < aa.length; i++)
		{
			double compare = this.aa[i] - that.aa[i];
			if (compare > 0)
				return 1;
			else if (compare < 0)
			        return -1;
		}
		return 0;
	}
}