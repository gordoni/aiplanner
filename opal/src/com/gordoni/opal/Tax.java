package com.gordoni.opal;

import java.util.ArrayList;
import java.util.List;

abstract class Tax
{
        protected Scenario scenario;
        protected Config config;

        protected boolean cg_carry_allowed = true;
        protected double tax_adjust = 1;

        abstract void initial(double p, double[] aa);

        abstract double total_pending(double p, double p_preinvest, double[] aa, double[] returns);

        abstract double tax(double p, double p_preinvest, double[] aa, double[] returns);

        protected double cg_carry = 0;
        private double dividends = 0;
        private double tax_dividends = 0;

        protected double dividend_tax(int a, double invest_final)
        {
	        double dividend = scenario.dividend_yield[a] * invest_final;
		dividends += dividend;
		double tax_rate = (config.tax_rate_div == null ? config.tax_rate_div_default : config.tax_rate_div[a]);
		tax_dividends += tax_rate * dividend;
		return dividend;
	}

        protected double total_tax(double income, double cpi_delta, boolean do_it)
        {
	        double cg = cg_carry / cpi_delta + income - dividends;
		double tax_cg = 0;
		if (cg >= 0 || !cg_carry_allowed)
		{
		    tax_cg = config.tax_rate_cg * cg;
			cg = 0;
		}
		double tax = tax_adjust * (tax_dividends + tax_cg);
		if (do_it)
		        cg_carry = cg;
		dividends = 0;
		tax_dividends = 0;
		return tax;
	}

        public static Tax taxFactory(Scenario scenario, String method)
        {
		if (method.equals("immediate"))
		        return new TaxImmediate(scenario, 1);
		else if (method.equals("avgcost"))
		        return new TaxAvgCost(scenario);
		else if (method.equals("hifo"))
		        return new TaxHifo(scenario, false);
		else if (method.equals("fifo"))
		        return new TaxHifo(scenario, true);
		else
		        assert(false);
		return null;
         }

        public Tax(Scenario scenario)
        {
	        this.scenario = scenario;
		this.config = scenario.config;

		assert(config.tax_rate_div == null || config.tax_rate_div.length == scenario.normal_assets);
	}
}
