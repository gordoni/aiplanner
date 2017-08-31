/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2017 Gordon Irlam
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
        public double min_feasible;

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
        private Interpolator spend_interp;
        private Interpolator first_payout_interp;
        private Interpolator[] aa_interp;
        private Interpolator human_capital_interp;

        private boolean generate_interpolator = true;

        public void interpolate(boolean generate)
        {
                double min_feasible;
                if (period + 1 < map.map.length)
                        min_feasible = map.map[period + 1].min_feasible;
                else
                        min_feasible = 0;
                min_feasible += mp[0].rps[scenario.tp_index] - mp[0].spend; // Compute negative of income, any bucket will do.
                this.min_feasible = min_feasible;

                if (generate)
                        if (scenario.interpolation_ce)
                                ce_interp = Interpolator.factory(this, generate, Interpolator.ce_interp_index);
                        else
                                metric_interp = Interpolator.factory(this, generate, Interpolator.metric_interp_index);
                aa_interp = new Interpolator[scenario.all_alloc];
                for (int i = 1; i < scenario.all_alloc; i++)
                        aa_interp[i] = Interpolator.factory(this, generate, i);
                spend_interp = Interpolator.factory(this, generate, Interpolator.spend_interp_index);
                human_capital_interp = Interpolator.factory(this, generate, Interpolator.human_capital_interp_index);
        }

        public MapElement lookup_interpolate(double[] p, boolean fast_path, boolean generate, MapElement li_me)
        {
                MapElement me = li_me;

                double metric_sm = Double.NaN;
                double spend = Double.NaN;
                double annuitize = 0;
                double first_payout = 0;

                if (!fast_path || generate)
                {
                        if (scenario.interpolation_ce)
                        {
                                double ce = ce_interp.value(p);
                                double utility;
                                if (ce >= 0)
                                        utility = map.uc_time.utility(ce);
                                else
                                        utility = Double.NEGATIVE_INFINITY;
                                metric_sm = utility / ce_interp.divisor;
                        }
                        else
                                metric_sm = metric_interp.value(p);
                }
                if (!fast_path || !generate)
                {
                        spend = spend_interp.value(p); // Only needed on non-generate fast path to compute aa[] below.
                        double consume = aa_interp[scenario.consume_index].value(p);
                        if (consume < 0)
                                consume = 0;

                        double[] aa = me.aa;
                        double allocatable = spend - consume; // Incorect if annuities are present, but OK since just used to improve interpolation.
                        if (allocatable != 0)
                        {
                                double sum = 0;
                                for (int i = 1; i < scenario.normal_assets; i++)
                                {
                                        // Smoother interpolation in absolute rather than aa space.
                                        // Important for sparse interpolation.
                                        // It would be cleaner if aa[] was in absolute space, but this would be a major code base change.
                                        aa[i] = aa_interp[i].value(p) / allocatable;
                                        sum += aa[i];
                                }
                                aa[0] = 1 - sum;
                        }
                        else
                                aa = scenario.guaranteed_safe_aa();
                        aa = scenario.inc_dec_aa_raw(aa, -1, 0, p, period); // Respect aa constraints.
                        for (int i = scenario.normal_assets; i < scenario.all_alloc; i++)
                        {
                                double alloc;
                                if (i == scenario.consume_index)
                                        alloc = consume;
                                else
                                {
                                        alloc = aa_interp[i].value(p);
                                        if (alloc > 1)
                                                alloc = 1;
                                        if (alloc < 0)
                                                alloc = 0;
                                }
                                aa[i] = alloc;
                        }
                        me.aa = aa;
                }

                if (!fast_path)
                {
                        if ((first_payout_interp == null) || (generate_interpolator && !generate))
                        {
                                // Avoid constructing interpolators if not needed. Consumes RAM.
                                if ((config.start_ria != null) || (config.start_nia != null))
                                        first_payout_interp = Interpolator.factory(this, generate, Interpolator.first_payout_interp_index);
                                generate_interpolator = generate;
                        }
                        if ((config.start_ria != null) || (config.start_nia != null))
                                first_payout = first_payout_interp.value(p);
                }

                me.results.metrics.metrics[scenario.success_mode_enum.ordinal()] = metric_sm; // Needed by maintain_all.
                me.metric_sm = metric_sm;
                me.spend = spend;
                me.first_payout = first_payout;

                if (scenario.hci_index != null)
                {
                        double human_capital = human_capital_interp.value(p);
                        me.metric_human_capital = human_capital;
                        me.results.metrics.metrics[MetricsEnum.HUMAN_CAPITAL.ordinal()] = human_capital;
                }

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
                        bottom[scenario.tp_index] = scenario.scale[scenario.tp_index].first_bucket;
                        length[scenario.tp_index] = scenario.scale[scenario.tp_index].num_buckets;
                }
                if (scenario.ria_index != null)
                {
                        bottom[scenario.ria_index] = scenario.scale[scenario.ria_index].first_bucket;
                        length[scenario.ria_index] = scenario.scale[scenario.ria_index].num_buckets;
                }
                if (scenario.nia_index != null)
                {
                        bottom[scenario.nia_index] = scenario.scale[scenario.nia_index].first_bucket;
                        length[scenario.nia_index] = scenario.scale[scenario.nia_index].num_buckets;
                }
                if (scenario.hci_index != null)
                {
                        bottom[scenario.hci_index] = scenario.scale[scenario.hci_index].first_bucket;
                        length[scenario.hci_index] = scenario.scale[scenario.hci_index].num_buckets;
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
