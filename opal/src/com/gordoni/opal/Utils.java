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
import java.util.List;

public class Utils
{
        public static double dot_product(double[] v, double[] w)
        {
                assert(v.length == w.length);
                double r = 0.0;
                for (int i = 0; i < v.length; i++)
                        r += v[i] * w[i];
                return r;
        }

        public static double[] vector_sum(double[] v, double[] w)
        {
                assert(v.length == w.length);
                double[] r = new double[v.length];
                for (int i = 0; i < v.length; i++)
                        r[i] = v[i] + w[i];
                return r;
        }

        public static double[] scalar_product(double s, double[] v)
        {
                double[] r = new double[v.length];
                for (int i = 0; i < v.length; i++)
                        r[i] = s * v[i];
                return r;
        }

        public static double[] vector_product(double[] v, double[] w)
        {
                assert(v.length == w.length);
                double[] r = new double[v.length];
                for (int i = 0; i < v.length; i++)
                        r[i] = v[i] * w[i];
                return r;
        }

        public static double[] matrix_vector_product(double[][] a, double[] v)
        {
                double[] r = new double[a.length];
                for (int i = 0; i < a.length; i++)
                        r[i] = dot_product(a[i], v);
                return r;
        }

        public static double reduceMul(List<Double> vars, double ini)
        {
                double x = ini;
                for (double var : vars)
                {
                        x *= var;
                }
                return x;
        }

        public static double[][] zipDoubleArrayArray(double[][] arrays)
        {
                int len0 = arrays[0].length;
                int len1 = arrays.length;
                double[][] result = new double[len0][len1];
                for (int i = 0; i < len0; i++)
                {
                        for (int j = 0; j < len1; j++)
                        {
                                result[i][j] = arrays[j][i];
                        }
                }
                return result;
        }

        public static List<double[]> zipDoubleArray(List<double[]> lists)
        {
                List<double[]> result = new ArrayList<double[]>();
                int len0 = lists.get(0).length;
                int len1 = lists.size();
                for (int i = 0; i < len0; i++)
                {
                        double[] array = new double[len1];
                        for (int j = 0; j < len1; j++)
                        {
                                array[j] = lists.get(j)[i];
                        }
                        result.add(array);
                }
                return result;
        }

        public static <T> List<List<T>> zip(List<List<T>> lists)
        {
                List<List<T>> result = new ArrayList<List<T>>();
                for (int i = 0; i < lists.get(0).size(); i++)
                {
                        List<T> l = new ArrayList<T>();
                        for (List<T> in : lists)
                        {
                                l.add(in.get(i));
                        }
                        result.add(l);
                }
                return result;
        }

        @SafeVarargs
        public static <T> List<List<T>> zip(List<T>... lists)
        {
                List<List<T>> result = new ArrayList<List<T>>();
                for (int i = 0; i < lists[0].size(); i++)
                {
                        List<T> l = new ArrayList<T>();
                        for (List<T> in : lists)
                        {
                                l.add(in.get(i));
                        }
                        result.add(l);
                }
                return result;
        }

        public static double[] DoubleTodouble(List<Double> l)
        {
                double[] res = new double[l.size()];
                for (int i = 0; i < res.length; i++)
                {
                        res[i] = l.get(i);
                }
                return res;
        }

        public static double sum(double... vals)
        {
                double x = 0.0;
                double floor = (vals.length == 0 || Double.isInfinite(vals[0]) ? 0 : vals[0]); // Avoid loss of precision summing many large nearby values.
                for (Double val : vals)
                {
                        x += val - floor;
                }
                return vals.length * floor + x;
        }

        public static double sum(List<Double> vals)
        {
                double x = 0.0;
                double floor = (vals.size() == 0 || Double.isInfinite(vals.get(0)) ? 0 : vals.get(0)); // Avoid loss of precision summing many large nearby values.
                for (double val : vals)
                {
                        x += val - floor;
                }
                return vals.size() * floor + x;
        }

        public static double mean(List<Double> vals)
        {
                return sum(vals) / vals.size();
        }

        public static double mean(double... a)
        {
                return sum(a) / a.length;
        }

        public static double weighted_sum(double[] vals, double[] weights)
        {
                assert(vals.length == weights.length);
                double x = 0.0;
                for (int i = 0; i < vals.length; i++)
                {
                    x += vals[i] * weights[i];
                }
                return x;
        }

        public static double plus_1_geomean(List<Double> a)
        {
                double sum = 0;
                for (Double i : a)
                {
                        sum += Math.log(1 + i);
                }
                return Math.exp(sum / a.size());
        }

        public static double plus_1_geomean(double[] a)
        {
                double sum = 0;
                for (int i = 0; i < a.length; i++)
                {
                        sum += Math.log(1 + a[i]);
                }
                return Math.exp(sum / a.length);
        }

        public static double weighted_plus_1_geo(double[] vals, double[] weights)
        {
                assert(vals.length == weights.length);
                double sum = 0;
                for (int i = 0; i < vals.length; i++)
                {
                        sum += Math.log(1 + vals[i]) * weights[i];
                }
                return Math.exp(sum);
        }

        public static double autocorrelation(double[] a, int offset)
        {
                double[] b;
                if (offset > 0)
                {
                        b = new double[a.length - offset];
                        System.arraycopy(a, 0, b, 0, a.length - offset);
                }
                else
                        b = a;
                double[] c = new double[a.length - offset];
                System.arraycopy(a, offset, b, 0, a.length - offset);
                double bm = mean(b);
                double cm = mean(c);
                double r = 0;
                for (int i = 0; i < b.length; i++)
                {
                        r += (b[i] - bm) * (c[i] - cm);
                }
                return r / (Utils.standard_deviation(a, false) * Utils.standard_deviation(b, false) * b.length);
        }

        public static double standard_deviation(List<Double> vals)
        {
                return standard_deviation(vals, true);
        }

        public static double standard_deviation(List<Double> vals, boolean sample)
        {
                double mean = mean(vals);
                double var = 0;
                for (double val : vals)
                {
                        var += Math.pow(val - mean, 2);
                }
                int len = sample ? (vals.size() - 1) : vals.size();
                if (len == 0)
                    return Double.NaN;
                else
                    return Math.sqrt(var / len);
        }

        public static double standard_deviation(double[] vals)
        {
                return standard_deviation(vals, true);
        }

        public static double standard_deviation(double[] vals, boolean sample)
        {
                double mean = mean(vals);
                double var = 0;
                for (double val : vals)
                {
                        var += Math.pow(val - mean, 2);
                }
                int len = sample ? (vals.length - 1) : vals.length;
                return Math.sqrt(var / len);
        }

        public static double weighted_standard_deviation(double[] vals, double[] weights)
        {
                return weighted_standard_deviation(vals, weights, true);
        }

        public static double weighted_standard_deviation(double[] vals, double[] weights, boolean sample)
        {
                double mean = weighted_sum(vals, weights) / sum(weights);
                double var = 0;
                for (int i = 0; i < vals.length; i++)
                {
                        var += Math.pow(vals[i] - mean, 2) * weights[i];
                }
                double len = sample ? (sum(weights) - weights[0]) : sum(weights);  // Hack: assumes weights[0] contains the sample increment.
                return Math.sqrt(var / len);
        }

        public static double covariance(double[] a, double[] b, boolean sample)
        {
                int samples = sample ? a.length - 1 : a.length;
                double am = mean(a);
                double bm = mean(b);
                double r = 0.0;
                for (int i = 0; i < a.length; i++)
                {
                        r += (a[i] - am) * (b[i] - bm);
                }
                return r / samples;
        }

        public static double[][] covariance_returns(List<double[]> returns)
        {
                double[][] a = new double[returns.size()][returns.size()];
                for (int i = 0; i < a.length; i++)
                {
                        for (int j = 0; j <= i; j++)
                        {
                                a[i][j] = covariance(returns.get(i), returns.get(j), true);
                        }
                }
                for (int i = 0; i < a.length; i++)
                {
                        for (int j = i + 1; j < a.length; j++)
                        {
                                a[i][j] = a[j][i];
                        }
                }
                return a;
        }

        public static double correlation(double[] a, double[] b, boolean sample)
        {
            double r = covariance(a, b, sample);
                double sda = standard_deviation(a, sample);
                double sdb = standard_deviation(b, sample);
                if (r == 0.0)
                        if (sda == 0.0 && sdb == 0.0)
                                return 1.0;
                        else
                                return 0.0;
                else
                        return r / (sda * sdb);
        }

        public static double[][] correlation_returns(double[][] returns)
        {
                double[][] a = new double[returns.length][returns.length];
                for (int i = 0; i < a.length; i++)
                {
                        for (int j = 0; j < i; j++)
                        {
                                a[i][j] = correlation(returns[i], returns[j], true);
                        }
                        a[i][i] = 1.0;
                }
                for (int i = 0; i < a.length; i++)
                {
                        for (int j = i + 1; j < a.length; j++)
                        {
                                a[i][j] = a[j][i];
                        }
                }
                return a;
        }

        public static double[][] cholesky_decompose(double[][] a)
        {
                double[][] l = new double[a.length][a.length];
                for (int i = 0; i < a.length; i++)
                {
                        for (int j = 0; j < i; j++)
                        {
                                double s = 0.0;
                                for (int k = 0; k < j; k++)
                                        s += l[i][k] * l[j][k];
                                l[i][j] = (a[i][j] - s) / l[j][j];
                        }
                        double s = 0.0;
                        for (int k = 0; k < i; k++)
                                s += l[i][k] * l[i][k];
                        l[i][i] = Math.sqrt(a[i][i] - s);
                }
                return l;
        }
}
