package com.gordoni.opal;

import java.util.Arrays;

class TaxImmediate extends Tax
{
        private double[] prev_aa;

        void initial(double p, double[] aa)
        {
		prev_aa = aa;
        }

        private double try_tax(double p, double p_preinvest, double[] aa, double[] returns, boolean do_it)
        {
		if (p_preinvest < 0)
		        p_preinvest = 0;
	        double cpi_delta = 1 + returns[scenario.cpi_index];
		double income = 0;
	        for (int i = 0; i < scenario.normal_assets; i++)
		{
		        double ret = 1 + returns[i];
			double invest_start = prev_aa[i] * p_preinvest;
			double invest_final = invest_start * ret;
			income += invest_final - invest_start / cpi_delta;
		        dividend_tax(i, invest_final);
		}
		double tax = total_tax(income, cpi_delta, false);
		if (do_it)
		        prev_aa = aa;
	        return tax;
	}

        double total_pending(double p, double p_preinvest, double[] aa, double[] returns)
        {
	        return try_tax(0, p_preinvest, aa, returns, false);
        }

        double tax(double p, double p_preinvest, double[] aa, double[] returns)
        {
	        return try_tax(p, p_preinvest, aa, returns, true);
        }

        public TaxImmediate(Scenario scenario, double tax_immediate_adjust)
        {
	        super(scenario);
		this.cg_carry_allowed = false;
		this.tax_adjust = tax_immediate_adjust;
        }
}
