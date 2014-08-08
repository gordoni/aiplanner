package com.gordoni.opal;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class HistReturns
{
        private String data = "data"; // Prefix to use for data files.

	public int initial_year;

	// Real monthly S&P Composite, GS10, and inflation data from Shiller:
	// http://www.econ.yale.edu/~shiller/data.htm
	private String shiller_file = "ie_data.csv";
	private int shiller_initial = 1872; // Initial year of the Shiller dataset
										// (1871 is only used to produce deltas
										// for 1872).

	// Real annual US equity, and high-grade long term corporate bond, and
	// inflation data from Stocks, Bills, Bonds, and Inflation Yearbook Classic
	// Edition.
	private String sbbi_file = "sbbi.csv";
	private int sbbi_initial = 1926;

	// Europe, Asia, Far East.
	public Integer eafe_initial = 1970;

	/// Fama/French Benchmark Portfolios data from http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html#Benchmarks
	public Integer ff_initial = null;

	// Real Estate Investment Trusts.
	public Integer reit_initial = 1972;

	// Real annual US 1-year Treasury note data (GS1) from http://research.stlouisfed.org/fred2/series/GS1/downloaddata?cid=115 .
	public Integer gs1_initial = null;

	// Real annual US 10-year Treasury inflation-indexed note data (FII10) from http://libertystreeteconomics.newyorkfed.org/2013/08/creating-a-history-of-us-inflation-expectations.html and FRED.
        // Former quotes are for end of month, later are beginning of month (or possibly month average), but discrepancy should be small.
	public Integer tips10_initial = null;

	// Real annual Moody's AAA and BAA corporate bond indexes from FRED.
	public Integer aaa_initial = null;
	public Integer baa_initial = null;

	// Real annual US 1-month Treasury note data from Fama/French Factors http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
	public Integer t1_initial = 1927;

	// Nominal annual US dollar prices for gold - http://www.nma.org/pdf/g_prices.pdf
	public Integer gold_initial = 1833;

	public List<Double> stock = new ArrayList<Double>();
	public List<Double> bond = new ArrayList<Double>();
        public List<Double> eafe = new ArrayList<Double>();
        public List<Double> ff_bl = new ArrayList<Double>();
        public List<Double> ff_bm = new ArrayList<Double>();
        public List<Double> ff_bh = new ArrayList<Double>();
        public List<Double> ff_sl = new ArrayList<Double>();
        public List<Double> ff_sm = new ArrayList<Double>();
        public List<Double> ff_sh = new ArrayList<Double>();
        public List<Double> reits_equity = new ArrayList<Double>();
        public List<Double> reits_mortgage = new ArrayList<Double>();
	public List<Double> gold = new ArrayList<Double>();
        public List<Double> gs1 = new ArrayList<Double>();
        public List<Double> tips10 = new ArrayList<Double>();
        public List<Double> aaa = new ArrayList<Double>();
        public List<Double> baa = new ArrayList<Double>();
        public List<Double> t1 = new ArrayList<Double>();
	public List<Double> cpi_index = new ArrayList<Double>();
        public List<Double> ssa_death_m = new ArrayList<Double>();
        public List<Double> ssa_death_f = new ArrayList<Double>();
        public Map<Integer, List<Double>> ssa_cohort_death_m = new HashMap<Integer, List<Double>>();
        public Map<Integer, List<Double>> ssa_cohort_death_f = new HashMap<Integer, List<Double>>();
        public List<Double> soa_iam2000_unloaded_death_m = new ArrayList<Double>();
        public List<Double> soa_iam2000_unloaded_death_f = new ArrayList<Double>();
        public List<Double> soa_iam2000_loaded_death_m = new ArrayList<Double>();
        public List<Double> soa_iam2000_loaded_death_f = new ArrayList<Double>();
        public List<Double> soa_iam2012_basic_death_m = null;
        public List<Double> soa_iam2012_basic_death_f = null;
        public List<Double> soa_projection_g2_m = null;
        public List<Double> soa_projection_g2_f = null;

        double bond_npv(double discount_rate, double interest_rate, double maturity)
        {
	        // http://www.bogleheads.org/forum/viewtopic.php?f=10&t=130068
		// http://www.cfiresim.com/phpbb/viewtopic.php?f=2&t=119
		// http://en.wikipedia.org/wiki/Bond_valuation
		// http://pages.stern.nyu.edu/~adamodar/ ... histretSP.xls
		// Bodie, Kane, and Marcus: Investments
	        double coupon_npv;
		if (discount_rate == 0)
		        coupon_npv = interest_rate * maturity;
		else
			coupon_npv = interest_rate * (1 - Math.pow(1 + discount_rate, - maturity)) / discount_rate;
		double principal_npv = Math.pow(1 + discount_rate, - maturity);
		return coupon_npv + principal_npv;
	}

	// Returns processing.
	private void load_shiller_data(BufferedReader in) throws IOException
	{
	        int time_periods = 12;
		        // Able to load non-monthly returns, but we keep it simple and load monthly returns.
		        // Then in Returns we reduce_returns() to non-monthly.

		List<Double> recent_interest_rate_plus_1 = new ArrayList<Double>();
		List<Double> recent_d_plus_1 = new ArrayList<Double>();

		String line = null;
		Integer start_year = null;
		boolean first_time = true;
		boolean first_period = true;
		int first_period_year = 0;
		double old_cpi = Double.NaN;
		double old_nominal_interest_rate = Double.NaN;
		double old_cpi_period = Double.NaN;
		double old_p_period = Double.NaN;
		while ((line = in.readLine()) != null)
		{
			String fields[] = line.split(",", -1);

			double year_month;
			try
			{
				year_month = Double.parseDouble(fields[0]);
			}
			catch (NumberFormatException e)
			{
				continue;
			}
			int year = (int) year_month;
			int month = (int) Math.round((year_month - year) * 100);
			if (fields[1].equals("") || fields[2].equals(""))
				continue;
			double nominal_p = Double.parseDouble(fields[1]);
			double nominal_d = Double.parseDouble(fields[2]);
			double cpi = Double.parseDouble(fields[4]);
			double nominal_interest_rate = Double.parseDouble(fields[6]) / 100;
			double p = nominal_p / cpi;
			double d = nominal_d / cpi;
			// System.out.println("year month nominal_p nominal_d p d cpi nominal_interest_rate");

			nominal_interest_rate = Math.pow(1 + nominal_interest_rate / 2, 2) - 1; // Quoted GS10 payments are semi-annual.

			if (first_time)
			{
			        if (month != 12)
			                continue;
				first_time = false;
			}
			else
			{
				recent_d_plus_1.add(1 + (d / 12) / p);
				double bond_sale_price = bond_npv(nominal_interest_rate, old_nominal_interest_rate, 10 - 1 / 12.0);
				double monthly_rate = Math.pow(1 + old_nominal_interest_rate, 1 / 12.0) - 1;
				recent_interest_rate_plus_1.add((bond_sale_price + monthly_rate) / (cpi / old_cpi));
			}

			if (recent_d_plus_1.size() > Math.round(12 / time_periods))
			{
				recent_d_plus_1.remove(0);
				recent_interest_rate_plus_1.remove(0);
			}

			cpi_index.add(cpi);
			if (first_period)
			{
			        first_period = false;
				first_period_year = year + 1;
				old_p_period = p;
				old_cpi_period = cpi;
			}
			else // if (((year - first_period_year) * 12 + month) % (Math.round(12 / time_periods)) == 0)
			{
			        if (recent_d_plus_1.size() == Math.round(12 / time_periods))
			        {
				        if (start_year == null)
					{
					        start_year = year;
					        if (time_periods < 1)
						    start_year -= (int) Math.round(1 / time_periods) - 1;
					}
					stock.add(p / old_p_period * Utils.reduceMul(recent_d_plus_1, 1.0) - 1);
					bond.add(Utils.reduceMul(recent_interest_rate_plus_1, 1.0) - 1);
				}
				old_p_period = p;
				old_cpi_period = cpi;
			}
			old_cpi = cpi;
			old_nominal_interest_rate = nominal_interest_rate;
		}
		in.close();
		assert (start_year == shiller_initial);
	}

	private void load_sbbi_data(BufferedReader in) throws IOException
	{
		String line = null;
		while ((line = in.readLine()) != null)
		{
			if (line.contains("#"))
				continue;

  			String[] fields = line.split(",", -1);
			// int year = Integer.parseInt(fields[0]);
			double cpi_d = Double.parseDouble(fields[1]);
			double nominal_b_delta = Double.parseDouble(fields[4]);
			double nominal_e_delta = Double.parseDouble(fields[5]);

			double e = (1 + nominal_e_delta / 100) / (1 + cpi_d / 100) - 1;
			double b = (1 + nominal_b_delta / 100) / (1 + cpi_d / 100) - 1;

			assert(false);
			//cpi_delta.add(cpi_d / 100);
			stock.add(e);
			bond.add(b);
		}
		in.close();
	}

        private int load_returns(String filename, int initial, List<Double> l, boolean price_level) throws IOException
	{
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		String line = in.readLine();
		double prev_price = Double.NaN;
		for (int year = initial; (line = in.readLine()) != null; year++)
		{
		        double rate;
		        if (price_level)
			{
			        double price = Double.parseDouble(line);
				rate = price / prev_price - 1;
				prev_price = price;
				if (year == initial)
				        continue;
			}
			else
			        rate = Double.parseDouble(line) / 100;
		        int i = (year - initial_year) * 12 + 12;
			if (12 <= i && i < cpi_index.size())
			{
			        double cpi_d = cpi_index.get(i) / cpi_index.get(i - 12);
		        	l.add((1 + rate) / cpi_d - 1);
			}
		}
		in.close();
		return Math.max(initial, initial_year);
	}

	private int load_ff(String filename) throws IOException
	{
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		Integer init_year = null;
		String line;
		for (line = in.readLine(); !line.trim().equals("Average Value Weighted Returns -- Annual"); line = in.readLine())
		{
		        ;
		}
		line = in.readLine();
		String me[] = line.trim().split(" +", -1);
		assert(me[0].equals("Small"));
		assert(me[1].equals("Big"));
		line = in.readLine();
		String be[] = line.trim().split(" +", -1);
		assert(be[0].equals("Low"));
		assert(be[1].equals("2"));
		assert(be[2].equals("High"));
		assert(be[3].equals("Low"));
		assert(be[4].equals("2"));
		assert(be[5].equals("High"));
		for (line = in.readLine(); !line.trim().equals(""); line = in.readLine())
		{
  			String[] fields = line.trim().split(" +", -1);
			assert(fields.length == 7);
			int year = Integer.parseInt(fields[0]);
			if (init_year == null)
			        init_year = year;
			for (int i = 0; i < 6; i++)
			{
				double rate = Double.parseDouble(fields[1 + i]) / 100;
		        	int j = (year - initial_year) * 12 + 12;
				assert(j >= 12);
				if (j < cpi_index.size())
				{
				        double cpi_d = cpi_index.get(j) / cpi_index.get(j - 12);
		        		rate = (1 + rate) / cpi_d - 1;
					if (i == 0)
					        ff_sl.add(rate);
					else if (i == 1)
					        ff_sm.add(rate);
					else if (i == 2)
					        ff_sh.add(rate);
					else if (i == 3)
					        ff_bl.add(rate);
					else if (i == 4)
					        ff_bm.add(rate);
					else if (i == 5)
					        ff_bh.add(rate);
					else
					        assert(false);
				}
			}
		}
		in.close();
		return init_year;
	}

        private int load_fred_interest_rate(String prefix, List<Double> l, int maturity, int coupon_freq, boolean nominal) throws IOException
	{
	        int time_periods = 12;

		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + prefix + ".csv")));
		String line = in.readLine();
		Integer init_year = null;
		double old_rate = Double.NaN;
		while ((line = in.readLine()) != null)
		{
  			String[] fields = line.split(",", -1);
			String date = fields[0];
			double rate = Double.parseDouble(fields[1]) / 100;

			String[] ymd = date.split("-", -1);
			int year = Integer.parseInt(ymd[0]);
			int month = Integer.parseInt(ymd[1]);
			int day = Integer.parseInt(ymd[2]);

			double annual_rate = Math.pow(1 + rate / coupon_freq, coupon_freq) - 1;
			double period_rate = Math.pow(1 + annual_rate, 1.0 / time_periods) - 1;

			if (month % (int) Math.round(12 / time_periods) == 0)
			{
				if (init_year != null)
				{
				        int i = (year - initial_year) * 12 + month;
					assert(i >= (int) Math.round(12.0 / time_periods));
					if (i < cpi_index.size())
					{
					        double bond_sale_price = bond_npv(annual_rate, old_rate, maturity - 1.0 / time_periods);
					        double cpi_d;
						if (nominal)
						        cpi_d = cpi_index.get(i) / cpi_index.get(i - (int) Math.round(12.0 / time_periods));
						else
						        cpi_d = 1;
						l.add((bond_sale_price + period_rate) / cpi_d - 1);
					}
				}
				if ((init_year == null) && (month == 12))
				       init_year = year + 1;
				old_rate = annual_rate;
			}
		}
		in.close();
		return init_year;
	}

        // From:
        // http://www.ssa.gov/oact/STATS/table4c6.html
        private void load_ssa_period(String filename) throws IOException
	{
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		String line = in.readLine();
		for (int l = 0; (line = in.readLine()) != null; l++)
		{
  			String[] fields = line.split(" +", -1);
			int age = Integer.parseInt(fields[0]);
			double m_death = Double.parseDouble(fields[1]);
			double f_death = Double.parseDouble(fields[4]);
			assert(age == l);
			ssa_death_m.add(m_death);
			ssa_death_f.add(f_death);
		}
		in.close();
	}

        // From:
        // http://www.ssa.gov/oact/NOTES/as120/TOC.html
        // http://www.ssa.gov/oact/NOTES/as120/LifeTables_Tbl_7.html
        private void load_ssa_cohort() throws IOException
	{
	        for (int birth_year = 1900; birth_year <= 2100; birth_year += 10)
		{
		        BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + "as120/LifeTables_Tbl_7_" + birth_year + ".html")));
			List<Double> death_list_m = new ArrayList<Double>();
			List<Double> death_list_f = new ArrayList<Double>();
			String line;
			while (!(line = in.readLine()).contains("Year of Birth"))
			{
			}
			for (int age = 0; age < 120; age++)
			{
			        while (!(line = in.readLine()).contains("<tr>"))
				{
				}
				while ((line = in.readLine()).contains("<"))
				{
				}
				assert(Integer.parseInt(line) == age);
				while ((line = in.readLine()).contains("<"))
				{
				}
				double death_m = Double.parseDouble(line);
				for (int i = 2; i < 8; i++)
				{
				        while ((line = in.readLine()).contains("<"))
					{
					}
				}
				assert(Integer.parseInt(line) == age);
				while ((line = in.readLine()).contains("<"))
				{
				}
				double death_f = Double.parseDouble(line);
				death_list_m.add(death_m);
				death_list_f.add(death_f);
		        }
			ssa_cohort_death_m.put(birth_year, death_list_m);
			ssa_cohort_death_f.put(birth_year, death_list_f);
		in.close();
		}
	}

        private void load_soa_iam2000(List<Double> death_m, List<Double> death_f, String filename) throws IOException
        {
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		String line = in.readLine();
		double prev_m = 0;
		double prev_f = 0;
		while ((line = in.readLine()) != null)
		{
  			String[] fields = line.split(",", -1);
			int age = Integer.parseInt(fields[0]);
			double m_death = Double.parseDouble(fields[1]) / 1000;
			double f_death = Double.parseDouble(fields[2]) / 1000;
			while (death_m.size() < age - 1)
			{
				death_m.add(0.0);
				death_f.add(0.0);
			}
			double avg_m = (prev_m + m_death) / 2; // SOA is age nearest birthday, so approximately convert to age
			double avg_f = (prev_f + f_death) / 2;
			death_m.add(avg_m);
			death_f.add(avg_f);
			prev_m = m_death;
			prev_f = f_death;
		}
		death_m.add(prev_m);
		death_f.add(prev_f);
		in.close();
	}

    private List<Double> load_soa_iam2012(String filename, boolean q1000) throws IOException
        {
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
	        Map<Integer, Double> death_map = new HashMap<Integer, Double>();
		String line = in.readLine();
		while ((line = in.readLine()) != null)
		{
			int age = Integer.parseInt(line);
			line = in.readLine();
			double q = Double.parseDouble(line);
			if (q1000)
			        q = q / 1000;
			death_map.put(age, q);
		}
		in.close();

		List<Double> death = new ArrayList<Double>();
		Double q;
		for (int age = 0; (q = death_map.get(age)) != null; age++)
		        death.add(q);

		return death;
	}

        public Map<String, double[]> real_annuity_price = new HashMap<String, double[]>();

        private void load_incomesolutions(String filename) throws IOException
        {
	        int max_age = 120;
		double[] real_annuity_price_male = new double[max_age + 1];
		double[] real_annuity_price_female = new double[max_age + 1];
		for (int i = 0; i <= max_age; i++)
		{
		        real_annuity_price_male[i] = Double.POSITIVE_INFINITY;
		        real_annuity_price_female[i] = Double.POSITIVE_INFINITY;
		}
	        BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + "incomesolutions.com/" + filename)));
		String line = in.readLine();
		while ((line = in.readLine()) != null)
		{
  			String[] fields = line.split(",", -1);
			int age = Integer.parseInt(fields[0]);
			double payout_male = fields[1].equals("") ? 0 : Double.parseDouble(fields[1]);
			double payout_female = fields[2].equals("") ? 0 : Double.parseDouble(fields[2]);
			real_annuity_price_male[age] = 100000 / (12 * payout_male);
			real_annuity_price_female[age] = 100000 / (12 * payout_female);
		}
		in.close();
		String date = filename.substring(0, filename.lastIndexOf(".csv"));
		real_annuity_price.put(date + "-male", real_annuity_price_male);
		real_annuity_price.put(date + "-female", real_annuity_price_female);
	}

        public Map<String, double[]> nominal_annuity_price = new HashMap<String, double[]>();

	// From immediateannuities.com (add -state=CA to get state):
	//   AGE=40
	//   while [ $AGE -le 90 ]; do
	//     echo $AGE
	//     curl -d passed=start -d age=$AGE -d gender=M -d joint_age=$AGE -d joint_gender=F -d deposit=1000000 -d income= -d sub2= http://www.immediateannuities.com/information/rates.html > $AGE.html
	//     sleep 10
	//     AGE=`expr $AGE + 1`
	//   done
        private void load_immediateannuities(String quote) throws IOException
        {
	        int min_age = 40;
	        int max_age = 90;
		double[] nominal_annuity_price_male = new double[max_age + 1];
		double[] nominal_annuity_price_female = new double[max_age + 1];
		for (int age = 0; age <= max_age; age++)
		{
		        nominal_annuity_price_male[age] = Double.POSITIVE_INFINITY;
		        nominal_annuity_price_female[age] = Double.POSITIVE_INFINITY;
		}
		for (int age = min_age; age <= max_age; age++)
		{
		        BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + "immediateannuities.com/" + quote + "/" + age + ".html")));
			String line;
			while (!(line = in.readLine()).contains("<li><span>Male " + age + "</span></li>"))
			{
			}
			while(!(line = in.readLine()).contains("SL"))
			{
			}
			assert((line = in.readLine()).startsWith("You receive"));
			line = in.readLine();
			String monthly_payout = line.replaceAll("<td class=\"average row1\">\\$(.*)</td>", "$1");
			monthly_payout = monthly_payout.replaceAll(",", "");
			nominal_annuity_price_male[age] = 1000000.0 / (12 * Double.parseDouble(monthly_payout));
			while (!(line = in.readLine()).contains("<li><span>Female " + age + "</span></li>"))
			{
			}
			while(!(line = in.readLine()).contains("SL"))
			{
			}
			assert((line = in.readLine()).startsWith("You receive"));
			line = in.readLine();
			monthly_payout = line.replaceAll("<td class=\"average row1\">\\$(.*)</td>", "$1");
			monthly_payout = monthly_payout.replaceAll(",", "");
			nominal_annuity_price_female[age] = 1000000.0 / (12 * Double.parseDouble(monthly_payout));
			// Make sure we aren't pulling from the final table by seeking to it's header.
			while (!(line = in.readLine()).contains("<li><span>Male " + age + " &amp; Female " + age + "</span></li>"))
			{
			}
			in.close();
		}
		nominal_annuity_price.put(quote + "-male", nominal_annuity_price_male);
		nominal_annuity_price.put(quote + "-female", nominal_annuity_price_female);
	}

        public Map<String, Map<Double, Double>> hqm = new HashMap<String, Map<Double, Double>>();

        // http://www.treasury.gov/resource-center/economic-policy/corp-bond-yield/Pages/Corp-Yield-Bond-Curve-Papers.aspx
        private void load_hqm(String filename) throws IOException
        {
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		String line = in.readLine();
		line = in.readLine();
		line = in.readLine();
		line = in.readLine();
		String[] years = line.split(",", -1);
		line = in.readLine();
		String[] months = line.split(",", -1);
		line = in.readLine();
		while ((line = in.readLine()) != null)
		{
		        String[] fields = line.split(",", -1);
			double maturity = Double.parseDouble(fields[0]);
			for (int i = 2; i < fields.length; i++)
			        if (!fields[i].equals(""))
				{
				        String date = years[(i - 2) / 12 * 12 + 2] + "-" + months[i];
				        double yield = Double.parseDouble(fields[i]) / 100;
					Map<Double, Double> curve = hqm.get(date);
					if (curve == null)
					{
					        curve = new HashMap<Double, Double>();
					        hqm.put(date, curve);
					}
					curve.put(maturity, yield);
				}
		}
		in.close();
	}

        public double[] annuity_le;

        // http://www.irs.gov/pub/irs-pdf/p939.pdf - Table V-ORDINARY LIFE ANNUITIES - ONE LIFE—EXPECTED RETURN MULTIPLES
        private void load_annuity_multiples(String filename) throws IOException
        {
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		String line = in.readLine();
		List<Double> multiples = new ArrayList<Double>();
		int next = 0;
		while ((line = in.readLine()) != null)
		{
		        String[] fields = line.split(",", -1);
			assert(fields.length == 2);
			while (Integer.parseInt(fields[0]) >= next)
			{
			        multiples.add(Double.parseDouble(fields[0]) + Integer.parseInt(fields[0]) - next);
			        next++;
			}
		}
		annuity_le = Utils.DoubleTodouble(multiples);
		in.close();
        }

        public double[] rmd_le;

        private int rmd_start = 30;

        private void load_rmd_le(String filename) throws IOException
        {
		BufferedReader in = new BufferedReader(new FileReader(new File(data + "/" + filename)));
		String line = in.readLine();
		List<Double> le_list = new ArrayList<Double>();
		for (int i = 0; i < rmd_start; i++)
		        le_list.add(Double.NaN);
		while ((line = in.readLine()) != null)
		{
		        String[] fields = line.split(",", -1);
			assert(fields.length == 1);
			double le = Double.parseDouble(fields[0]);
			le_list.add(le);
		}
		rmd_le = Utils.DoubleTodouble(le_list);
		in.close();
        }

        public HistReturns() throws IOException
        {
		// Set up returns and initial_year based on data_source.
		if (Config.data_source.equals("sbbi"))
		{
			load_sbbi_data(new BufferedReader(new FileReader(new File(data + "/" + sbbi_file))));
			initial_year = sbbi_initial;
		}
		else
		{
			load_shiller_data(new BufferedReader(new FileReader(new File(data + "/" + shiller_file))));
			initial_year = shiller_initial;
		}

	        eafe_initial = load_returns("eafe.csv", eafe_initial, eafe, false);
	        ff_initial = load_ff("6_Portfolios_2x3.txt");
		reit_initial = load_returns("reit-all_equity.csv", reit_initial, reits_equity, false);
		reit_initial = load_returns("reit-mortgage.csv", reit_initial, reits_mortgage, false);
		gs1_initial = load_fred_interest_rate("GS1", gs1, 1, 2, true);
		tips10_initial = load_fred_interest_rate("FII10", tips10, 10, 2, false);
		        // pre-2003 may not be semi-annual coupon, but difference here is only 1-2 basis points.
                // "Moody's tries to include bonds with remaining maturities as close as possible to 30 years.
		// Moody's drops bonds if the remaining life falls below 20 years, if the bond is susceptible to redemption, or if the rating changes."
		// So we take the mid-point as a rough estimate of the average maturity.
		aaa_initial = load_fred_interest_rate("AAA", aaa, 25, 1, true); // Coupon frequency believed to be annual.
		baa_initial = load_fred_interest_rate("BAA", baa, 25, 1, true);
	        t1_initial = load_returns("cash.csv", t1_initial, t1, false);
	        gold_initial = load_returns("gold.csv", gold_initial, gold, true);
		load_ssa_period("ssa-table4c6.txt");
		load_ssa_cohort();
		load_soa_iam2000(soa_iam2000_unloaded_death_m, soa_iam2000_unloaded_death_f, "soa-iam2000-unloaded.csv");
		load_soa_iam2000(soa_iam2000_loaded_death_m, soa_iam2000_loaded_death_f, "soa-iam2000-loaded.csv");
		soa_iam2012_basic_death_m = load_soa_iam2012("soa-iam2012-basic-male.csv", true);
		soa_iam2012_basic_death_f = load_soa_iam2012("soa-iam2012-basic-female.csv", true);
		soa_projection_g2_m = load_soa_iam2012("soa-projection-g2-male.csv", false);
		soa_projection_g2_f = load_soa_iam2012("soa-projection-g2-female.csv", false);
                File dir = new File(data + "/" + "incomesolutions.com");
		for (File file : dir.listFiles())
		        if (file.getName().endsWith(".csv"))
			        load_incomesolutions(file.getName());
                dir = new File(data + "/" + "immediateannuities.com");
		for (File file : dir.listFiles())
		        if (file.isDirectory())
			        load_immediateannuities(file.getName());
		load_hqm("hqm/hqm_84_88.csv");
		load_hqm("hqm/hqm_89_93.csv");
		load_hqm("hqm/hqm_94_98.csv");
		load_hqm("hqm/hqm_99_03.csv");
		load_hqm("hqm/hqm_04_08.csv");
		load_hqm("hqm/hqm_09_13.csv");
		load_hqm("hqm/hqm_14_18.csv");
		load_annuity_multiples("irs-pub939-table_v-2013.csv");
		load_rmd_le("irs-pub590-appendix_c-table_ii-2013.csv");
        }
}
