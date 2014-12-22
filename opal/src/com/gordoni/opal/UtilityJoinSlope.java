package com.gordoni.opal;

import org.apache.commons.math3.linear.RealMatrix;
import org.apache.commons.math3.linear.RealVector;
import org.apache.commons.math3.linear.Array2DRowRealMatrix;
import org.apache.commons.math3.linear.ArrayRealVector;
import org.apache.commons.math3.linear.DecompositionSolver;
import org.apache.commons.math3.linear.LUDecomposition;

public class UtilityJoinSlope extends Utility
{
        // Join with linear or cubic poynomial interpolation of slope across the join region.

        private Config config;
        private Utility utility1;
        private Utility utility2;
        private double c1;
        private double c2;
        private double w; // u'(c) = w * c^3 + x * c^2 + y * c + z
        private double x;
        private double y;
        private double z;
        private double zero1 = 0;
        private double zero2 = 0;
        private double u1;
        private double u2;

        public double utility(double c)
        {
                assert(c >= 0);
                if (c < c1)
                        return utility1.utility(c);
                else if (c > c2)
                        return utility2.utility(c) - zero2;
                else
                        return (((w / 4 * c + x / 3) * c + y / 2) * c + z) * c - zero1;
        }

        public double inverse_utility(double u)
        {
                if (u < u1)
                        return utility1.inverse_utility(u);
                else if (u >= u2)
                        return utility2.inverse_utility(u + zero2);
                else
                {
                        double lo = c1;
                        double hi = c2;
                        while (true)
                        {
                                double mid = (lo + hi) / 2;
                                if (mid == lo || mid == hi)
                                        break;
                                if (u < utility(mid))
                                        hi = mid;
                                else
                                        lo = mid;
                        }
                        return lo;
                }
        }

        public double slope(double c)
        {
                assert(c >= 0);
                if (c < c1)
                        return utility1.slope(c);
                else if (c >= c2)
                        return utility2.slope(c);
                else
                        return ((w * c + x) * c + y) * c + z;
        }

        public double inverse_slope(double s)
        {
                // Bug: Not implemented. Method only used for testing so OK.
                return 0;
        }

        public double slope2(double c)
        {
                assert(c >= 0);
                if (c < c1)
                        return utility1.slope2(c);
                else if (c >= c2)
                        return utility2.slope2(c);
                else
                        return (3 * w * c + 2 * x) * c + y;
        }

        /*
         * http://en.wikipedia.org/wiki/Monotone_cubic_interpolation
         * Cited paper is currently at: http://www.ams.sunysb.edu/~jiao/teaching/ams527_spring13/lectures/SNA000238.pdf
         */
        private boolean monotone(double alpha, double beta)
        {
                if (2 * alpha + beta - 3 <= 0)
                        return true;
                if (alpha + 2 * beta - 3 <= 0)
                        return true;
                if (3 * alpha * (alpha + beta - 2) - Math.pow(2 * alpha + beta - 3, 2) >= 0)
                        return true;

                return false;
        }

        public UtilityJoinSlope(Config config, String join_function, Utility utility1, Utility utility2, double c1, double c2)
        {
                this.config = config;
                this.utility1 = utility1;
                this.utility2 = utility2;

                this.c1 = c1;
                this.c2 = c2;

                if (c1 < c2)
                {
                        if (join_function.equals("slope-cubic-monotone") || join_function.equals("slope-cubic-smooth"))
                        {
                                RealMatrix a = new Array2DRowRealMatrix(new double[][] {
                                        { c1 * c1 * c1, c1 * c1, c1, 1 },
                                        { c2 * c2 * c2, c2 * c2, c2, 1 },
                                        { 3 * c1 * c1, 2 * c1, 1, 0 },
                                        { 3 * c2 * c2, 2 * c2, 1, 0 }
                                });
                                double s1 = utility1.slope(c1);
                                double s2 = utility2.slope(c2);
                                double s2_1 = utility1.slope2(c1);
                                double s2_2 = utility2.slope2(c2);
                                double secant = (s2 - s1) / (c2 - c1);
                                assert(secant < 0);
                                double alpha = s2_1 / secant;
                                double beta = s2_2 / secant;
                                if (!monotone(alpha, beta)) {
                                        assert(!join_function.equals("slope-cubic-smooth"));
                                        // Guarantee monotonicity at the cost of a discontinuity in slope2 space.
                                        s2_1 = Math.max(s2_1, 3 * secant); // Can do better (see paper), but this is good enough.
                                        alpha = s2_1 / secant;
                                        if (!monotone(alpha, beta)) {
                                                s2_2 = 3 * secant;
                                                beta = s2_2 / secant;
                                        }
                                }
                                RealVector b = new ArrayRealVector(new double[] { s1, s2, s2_1, s2_2 });
                                DecompositionSolver solver = new LUDecomposition(a).getSolver();
                                RealVector solution = solver.solve(b);
                                this.w = solution.getEntry(0);
                                this.x = solution.getEntry(1);
                                this.y = solution.getEntry(2);
                                this.z = solution.getEntry(3);
                        }
                        else if (join_function.equals("slope-linear"))
                        {
                                this.w = 0;
                                this.x = 0;
                                this.y = (utility2.slope(c2) - utility1.slope(c1)) / (c2 - c1);
                                this.z = utility1.slope(c1) - this.y * c1;
                        }
                        else
                                assert(false);
                }
                else
                {
                        this.w = 0;
                        this.x = 0;
                        this.y = 0;
                        this.z = 0;
                }

                this.zero1 = utility(c1) - utility1.utility(c1);
                this.zero2 = utility2.utility(c2) - utility(c2);

                this.u1 = utility(c1);
                this.u2 = utility(c2);

                set_constants();
        }
}
