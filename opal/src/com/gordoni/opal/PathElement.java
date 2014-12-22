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
