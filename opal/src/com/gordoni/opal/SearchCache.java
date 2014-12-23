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
