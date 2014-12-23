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

public class PathElement
{
        public double weight;

        public double[] aa;
        public double p;
        public double consume_annual;
        public double ria;
        public double nia;
        public double real_annuitize;
        public double nominal_annuitize;
        public double tax_amount;

        public PathElement(double[] aa, double p, double consume_annual, double ria, double nia, double real_annuitize, double nominal_annuitize, double tax_amount, double weight)
        {
                this.weight = weight;

                if (aa == null)
                        this.aa = null;
                else
                {
                        this.aa = new double[aa.length];
                        System.arraycopy(aa, 0, this.aa, 0, aa.length);
                }
                this.p = p;
                this.consume_annual = consume_annual;
                this.ria = ria;
                this.nia = nia;
                this.real_annuitize = real_annuitize;
                this.nominal_annuitize = nominal_annuitize;
                this.tax_amount = tax_amount;
        }
}
