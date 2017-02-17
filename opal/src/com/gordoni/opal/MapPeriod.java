/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2016 Gordon Irlam
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

import java.util.Arrays;
import java.util.Iterator;

interface MapPeriodIterator<T> extends Iterator<T>
{
        public int[] nextIndex();
}

class MapPeriod implements Iterable<MapElement>
{
        public Config config;
        public Scenario scenario;
        public AAMap map;
        public int period;
        public double age;

        private MapElement[] mp;

        public int total_length;

        public int[] bottom;
        public int[] length;

        public double[] floor;
        public double[] ceiling;

        //private int tp_stride;

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

        private Interpolator metric_interp;
        private Interpolator ce_interp;
        private Interpolator consume_interp;
        private Interpolator spend_interp;
        private Interpolator first_payout_interp;
        private Interpolator[] aa_interp;

        private boolean generate_interpolator = true;

        public void interpolate(boolean generate)
        {
                if (scenario.interpolation_ce)
                        ce_interp = Interpolator.factory(this, generate, Interpolator.ce_interp_index);
                else
                        metric_interp = Interpolator.factory(this, generate, Interpolator.metric_interp_index);
                aa_interp = new Interpolator[scenario.all_alloc];
                for (int i = 0; i < scenario.all_alloc; i++)
                        aa_interp[i] = Interpolator.factory(this, generate, i);
        }

        public MapElement lookup_interpolate(double[] p, boolean fast_path, boolean generate, MapElement li_me)
        {
                MapElement me = li_me;
                double[] aa = li_me.aa;

                double metric_sm = Double.NaN;
                double spend = Double.NaN;
                double consume = Double.NaN;
                double annuitize = 0;
                double first_payout = 0;

                if (!fast_path || generate)
                {
                        if (scenario.interpolation_ce)
                        {
                                double ce = ce_interp.value(p);
                                double utility = map.uc_time.utility(ce);
                                metric_sm = utility / ce_interp.divisor;
                        }
                        else
                                metric_sm = metric_interp.value(p);
                }
                if (!fast_path || !generate)
                {
                        for (int i = 0; i < scenario.all_alloc; i++)
                                aa[i] = aa_interp[i].value(p);
                        // Keep bounded and summed to one as exactly as possible.
                        boolean in_range = true;
                        double sum = 0;
                        for (int i = 0; i < scenario.normal_assets; i++)
                        {
                                if (!((config.min_aa < aa[i]) && (aa[i] < config.max_aa)))
                                        in_range = false;
                                sum += aa[i];
                        }
                        if (Math.abs(sum - 1) > 1e-9 * Math.max(Math.abs(config.min_aa), Math.abs(config.max_aa)))
                        {
                                in_range = false;
                        }
                        if (!in_range)
                                aa = scenario.inc_dec_aa_raw(aa, -1, 0, p, period);
                        for (int i = scenario.normal_assets; i < scenario.all_alloc; i++)
                        {
                                double alloc = aa[i];
                                if (alloc <= 0)
                                        alloc = 1;
                                if (alloc > 1)
                                        alloc = 1;
                                aa[i] = alloc;
                        }
                }

                if (!fast_path)
                {
                        if ((spend_interp == null) || (generate_interpolator && !generate))
                        {
                                // Avoid constructing interpolators if not needed. Consumes RAM.
                                spend_interp = Interpolator.factory(this, generate, Interpolator.spend_interp_index);
                                consume_interp = Interpolator.factory(this, generate, Interpolator.consume_interp_index);
                                if ((config.start_ria != null) || (config.start_nia != null))
                                        first_payout_interp = Interpolator.factory(this, generate, Interpolator.first_payout_interp_index);
                                generate_interpolator = generate;
                        }
                        spend = spend_interp.value(p);
                        consume = consume_interp.value(p);
                        //if (-1e-12 * scenario.consume_max_estimate < consume && consume < 0)
                        //        consume = 0;
                        if ((config.start_ria != null) || (config.start_nia != null))
                                first_payout = first_payout_interp.value(p);

                        if (spend < 0)
                        {
                                System.err.println("lookup_interpolate(): negative interpolated spend: " + spend);
                                assert(false);
                        }
                        if (consume < 0)
                        {
                                System.err.println("lookup_interpolate(): negative interpolated consume: " + consume);
                                assert(false);
                        }
                }

                me.results.metrics.metrics[scenario.success_mode_enum.ordinal()] = metric_sm; // Needed by maintain_all.
                me.metric_sm = metric_sm;
                me.spend = spend;
                me.consume = consume;
                me.first_payout = first_payout;

                me.rps = p;

                return me;
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

        public MapPeriod(AAMap map, int period)
        {
                this.config = map.config;
                this.scenario = map.scenario;
                this.map = map;
                this.period = period;
                this.age = config.start_age + period / config.generate_time_periods;

                bottom = new int[scenario.start_p.length];
                length = new int[scenario.start_p.length];
                if (scenario.tp_index != null)
                {
                        bottom[scenario.tp_index] = scenario.scale[scenario.tp_index].pf_to_bucket(scenario.tp_high);
                        length[scenario.tp_index] = scenario.scale[scenario.tp_index].pf_to_bucket(config.pf_fail) - bottom[scenario.tp_index] + 1;
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

                floor = new double[scenario.start_p.length];
                ceiling = new double[scenario.start_p.length];
                for (int i = 0; i < scenario.start_p.length; i++)
                {
                        floor[i] = scenario.scale[i].bucket_to_pf(bottom[i] + length[i] - 1);
                        ceiling[i] = scenario.scale[i].bucket_to_pf(bottom[i]);
                }

                int len = 1;
                for (int i = 0; i < length.length; i++)
                        len *= length[i];
                total_length = len;
                mp = new MapElement[total_length];

                //tp_stride = 1;
                //for (int i = scenario.tp_index + 1; i < length.length; i++)
                //        tp_stride *= length[i];

        }
}
