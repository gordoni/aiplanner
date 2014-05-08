package com.gordoni.opal;

public class SearchCacheElement
{
        String key;
        SimulateResult results;

        SearchCacheElement(String key, SimulateResult results)
        {
	        this.key = key;
	        this.results = results;
	}
}