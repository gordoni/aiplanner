package com.gordoni.opal;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SearchCache
{
        private Config config;

        // HashMap probably uses more memory and is slower than ArrayList for small caches.

        private Map<String, SimulateResult> cache_map;

        private List<SearchCacheElement> cache_list;

        public void put(String key, SimulateResult results)
        {
                if (config.search_cache_map)
                        cache_map.put(key, results);
                else
                        cache_list.add(new SearchCacheElement(key, results));
        }

        public SimulateResult get(String key)
        {
                if (config.search_cache_map)
                        return cache_map.get(key);
                else
                        for (SearchCacheElement e : cache_list)
                        {
                                if (key.equals(e.key))
                                        return e.results;
                        }
                        return null;
        }

        public void clear()
        {
                if (config.search_cache_map)
                        cache_map.clear();
                else
                        cache_list.clear();
        }

        public SearchCache(Scenario scenario)
        {
                config = scenario.config;

                if (config.search_cache_map)
                        cache_map = new HashMap<String, SimulateResult>();
                else
                        cache_list = new ArrayList<SearchCacheElement>();
        }
}
