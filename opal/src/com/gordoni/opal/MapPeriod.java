package com.gordoni.opal;

import java.util.Arrays;
import java.util.Iterator;

interface MapPeriodIterator<T> extends Iterator<T>
{
        public int[] nextIndex();
}

class MapPeriod implements Iterable<MapElement>
{
        private MapElement[] mp;

	public int[] bottom;
        public int[] length;

	private int tp_stride;

        public MapElement get(int[] p_index)
        {
		int offset = 0;
		for (int i = 0; i < length.length; i++)
		{
		        int offset0 = p_index[i] - bottom[i];
		        assert(0 <= offset0 && offset0 < length[i]);
		        offset = offset * length[i] + offset0;
		}
		return mp[offset];
	}

        public void set(int[] p_index, MapElement me)
        {
		int offset = 0;
		for (int i = 0; i < length.length; i++)
		{
		        int offset0 = p_index[i] - bottom[i];
		        assert(0 <= offset0 && offset0 < length[i]);
		        offset = offset * length[i] + offset0;
		}
		mp[offset] = me;
	}

        public Iterator<MapElement> iterator_unused()
        {
	        Iterator<MapElement> it = new Iterator<MapElement>()
		{
		        private int current = 0;

		        public boolean hasNext()
		        {
			        return current < mp.length;
			}

		        public MapElement next()
		        {
			        return mp[current++];
			}

		        public void remove()
		        {
			}
		};

		return it;
	}

        public MapPeriodIterator<MapElement> iterator()
        {
	        MapPeriodIterator<MapElement> it = new MapPeriodIterator<MapElement>()
		{
			private int[] next = bottom.clone();

		        public boolean hasNext()
		        {
			        return next[next.length - 1] < bottom[next.length - 1] + length[next.length - 1];
			}

		        public MapElement next()
		        {
			        MapElement curr = get(next);
				next[0]++;
				for (int i = 0; i < next.length - 1; i++)
				{
				        if (next[i] == bottom[i] + length[i])
					{
						next[i] = bottom[i];
						next[i + 1]++;
					}
					else
					        break;
				}
				return curr;
			}

			public int[] nextIndex()
			{
			        return next;
			}

		        public void remove()
		        {
			}
		};

		return it;
	}

        public MapPeriod(BaseScenario scenario, boolean generate)
        {
	        Config config = scenario.config;

	        bottom = new int[scenario.start_p.length];
	        length = new int[scenario.start_p.length];
		if (scenario.tp_index != null)
		{
			bottom[scenario.tp_index] = (generate ? config.generate_bottom_bucket : config.validate_bottom_bucket);
		        length[scenario.tp_index] = (generate ? config.generate_top_bucket : config.validate_top_bucket) - bottom[scenario.tp_index] + 1;
		}
		if (scenario.ria_index != null)
		{
			bottom[scenario.ria_index] = scenario.scale[scenario.ria_index].pf_to_bucket(config.ria_high);
		        length[scenario.ria_index] = scenario.scale[scenario.ria_index].pf_to_bucket(0) - bottom[scenario.ria_index] + 1;
		}
		if (scenario.nia_index != null)
		{
			bottom[scenario.nia_index] = scenario.scale[scenario.nia_index].pf_to_bucket(config.nia_high);
		        length[scenario.nia_index] = scenario.scale[scenario.nia_index].pf_to_bucket(0) - bottom[scenario.nia_index] + 1;
		}

		int len = 1;
		for (int i = 0; i < length.length; i++)
		        len *= length[i];
	        mp = new MapElement[len];

		//tp_stride = 1;
		//for (int i = scenario.tp_index + 1; i < length.length; i++)
		//        tp_stride *= length[i];

	}
}
