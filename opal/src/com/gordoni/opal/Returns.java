package com.gordoni.opal;

import java.util.Arrays;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

public class Returns implements Cloneable
{
        private Scenario scenario;
        private Config config;

	public List<double[]> data;
        public List<double[]> original_data;
        public double[][] returns_unshuffled;
        public double[] returns_unshuffled_probability;
        private List<double[][]> returns_cache = new ArrayList<double[][]>();

	private Random random;
        private int ret_seed;

	public double time_periods;
	public String ret_shuffle;
	public boolean reshuffle;
	public String draw;
	public int block_size;
	public boolean pair;
	public boolean short_block;

        public double[] am;
        public double[] sd;
        public double[][] corr;
        private double[][] cholesky;

	public double[] dividend_fract;

        private List<Double> adjust_returns(List<Double> l, double ret_adjust, double vol_adjust)
        {
	        double[] a = Utils.DoubleTodouble(l);
	        double plus_1_geomean = Utils.plus_1_geomean(a);
	        double mean = Utils.sum(a) / a.length;
		if (vol_adjust != 1)
		{
		        // Binary search on volatility adjustment.
			double vol_a = Utils.standard_deviation(a);
		        double[] b = new double[a.length];
		        double low = vol_adjust;
			double high = vol_adjust * 2;
                        while (high - low > 0.01)  // Finer resolution not needed as precise standard deviation is about to get messed up by the geomean adjust below.
			{
			        double mid = (low + high) / 2;
				for (int i = 0; i < a.length; i++)
					if (a[i] >= mean)
						b[i] = mean + (a[i] - mean) * mid;
					else
						// Inverses break mathematical cleanness, but prevent negative values.
						b[i] = 1 / (1 / (1 + mean) + (1 / (1 + a[i]) - 1 / (1 + mean)) * mid) - 1;
				double vol = Utils.standard_deviation(b);
				if (vol < vol_adjust * vol_a)
				        low = mid;
				else
				        high = mid;
			}
			a = b;
		}

		double new_plus_1_geomean = Utils.plus_1_geomean(a);
		double adjust = ret_adjust * plus_1_geomean / new_plus_1_geomean;
		for (int i = 0; i < a.length; i++)
		        a[i] = (1 + a[i]) * adjust - 1;
		List<Double> res = new ArrayList<Double>();
		for (int i = 0; i < a.length; i++)
		{
		    res.add(a[i]);
		}
		return res;
	}

        public Returns(Scenario scenario, HistReturns hist, Config config, int ret_seed, boolean cache_returns, int start_year, Integer end_year, Integer num_sequences, double time_periods, Double ret_equity, Double ret_bonds, double ret_risk_free, Double ret_inflation, double management_expense, String ret_shuffle, boolean reshuffle, String draw, int random_block_size, boolean pair, boolean short_block, double all_adjust, double equity_vol_adjust)
	{
	        this.scenario = scenario;
	        this.config = config;

	        this.ret_seed = ret_seed;
		this.time_periods = time_periods;
	        this.ret_shuffle = ret_shuffle;
		this.reshuffle = reshuffle;
		this.draw = draw;
		this.block_size = (random_block_size == 0 ? 1 : (int) Math.round(random_block_size * time_periods));
		assert(time_periods >= 1 || random_block_size == 0 || Math.round(1.0 / time_periods) * this.block_size == random_block_size);
		this.pair = pair;
		this.short_block = short_block;

                double adjust_management_expense = Math.pow(1.0 - management_expense, 1.0 / time_periods);
		double adjust_all = Math.pow(1 + all_adjust, 1.0 / time_periods);
		double adjust_equity_vol = equity_vol_adjust;

		int start = (int) Math.round((start_year - hist.initial_year) * 12);
		assert(start >= 0);
		int month_count = (end_year == null) ? (hist.stock.size() - start) : (int) ((end_year - start_year + 1) * 12);
		assert(month_count % Math.round(12 / time_periods) == 0);
		int count = month_count / (int) Math.round(12 / time_periods);
		assert(start + month_count <= hist.stock.size());

		List<Double> stock_returns = reduce_returns(hist.stock.subList(start, start + month_count), (int) Math.round(12 / time_periods));
		double stock_geomean = Utils.plus_1_geomean(stock_returns);
		double equity_adjust = 1.0;
		if (config.ret_equity_adjust == null)
		        equity_adjust = (ret_equity == null) ? 1 : (Math.pow(1 + ret_equity, 1 / time_periods) / stock_geomean);
		else
		{
		        assert(ret_equity == null);
		        equity_adjust = Math.pow(1.0 + config.ret_equity_adjust, 1.0 / time_periods);
		}
		List<Double> equity_returns = null;
		if (scenario.asset_classes.contains("stocks"))
		        equity_returns = adjust_returns(stock_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);

		List<Double> bond_returns = reduce_returns(hist.bond.subList(start, start + month_count), (int) Math.round(12 / time_periods));
		double bond_geomean = Utils.plus_1_geomean(bond_returns);
		double gs10_to_bonds_adjust = Math.pow(1.0 + config.ret_gs10_to_bonds, 1.0 / time_periods);
		double fixed_income_adjust = 1.0;
		if (config.ret_bonds_adjust == null)
		{
		        fixed_income_adjust = (ret_bonds == null) ? 1 : (Math.pow((1 + ret_bonds), 1 / time_periods) / bond_geomean) / gs10_to_bonds_adjust;
		}
		else
		{
		        assert(ret_bonds == null);
		        fixed_income_adjust = Math.pow(1.0 + config.ret_bonds_adjust, 1.0 / time_periods);
		}
		List<Double> fixed_income_returns = null;
		if (scenario.asset_classes.contains("bonds"))
		{
		        fixed_income_returns = adjust_returns(bond_returns, fixed_income_adjust * gs10_to_bonds_adjust * adjust_management_expense * adjust_all, config.ret_gs10_to_bonds_vol_adjust);
		}
		List<Double> gs10_returns = null;
		if (scenario.asset_classes.contains("gs10"))
		        gs10_returns = adjust_returns(bond_returns, fixed_income_adjust * adjust_management_expense * adjust_all, 1);

		List<Double> eafe_returns = null;
		if (scenario.asset_classes.contains("eafe"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.eafe_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.eafe.size());
			eafe_returns = hist.eafe.subList(offset, offset + count);
			eafe_returns = adjust_returns(eafe_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
		}

		List<Double> ff_bl_returns = null;
		List<Double> ff_bm_returns = null;
		List<Double> ff_bh_returns = null;
		List<Double> ff_sl_returns = null;
		List<Double> ff_sm_returns = null;
		List<Double> ff_sh_returns = null;
		if (scenario.asset_classes.contains("bl") || scenario.asset_classes.contains("bm") || scenario.asset_classes.contains("bh") || scenario.asset_classes.contains("sl") || scenario.asset_classes.contains("sm") || scenario.asset_classes.contains("sh"))
		{
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.ff_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.ff_bl.size());
			ff_bl_returns = hist.ff_bl.subList(offset, offset + count);
			ff_bl_returns = adjust_returns(ff_bl_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
			ff_bm_returns = hist.ff_bm.subList(offset, offset + count);
			ff_bm_returns = adjust_returns(ff_bm_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
			ff_bh_returns = hist.ff_bh.subList(offset, offset + count);
			ff_bh_returns = adjust_returns(ff_bh_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
			ff_sl_returns = hist.ff_sl.subList(offset, offset + count);
			ff_sl_returns = adjust_returns(ff_sl_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
			ff_sm_returns = hist.ff_sm.subList(offset, offset + count);
			ff_sm_returns = adjust_returns(ff_sm_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
			ff_sh_returns = hist.ff_sh.subList(offset, offset + count);
			double adjust_sh = Math.pow(1 + config.ret_sh_adjust, 1.0 / time_periods);
			ff_sh_returns = adjust_returns(ff_sh_returns, equity_adjust * adjust_sh * adjust_management_expense * adjust_all, adjust_equity_vol);
		}

		List<Double> reits_equity_returns = null;
		if (scenario.asset_classes.contains("equity_reits"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.reit_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.reits_equity.size());
			reits_equity_returns = hist.reits_equity.subList(offset, offset + count);
			reits_equity_returns = adjust_returns(reits_equity_returns, equity_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
		}

		List<Double> reits_mortgage_returns = null;
		if (scenario.asset_classes.contains("mortgage_reits"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.reit_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.reits_mortgage.size());
			reits_mortgage_returns = hist.reits_mortgage.subList(offset, offset + count);
			reits_mortgage_returns = adjust_returns(reits_mortgage_returns, fixed_income_adjust * adjust_management_expense * adjust_all, adjust_equity_vol);
		}

		List<Double> gs1_returns = null;
		if (scenario.asset_classes.contains("gs1"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.gs1_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.gs1.size());
			gs1_returns = hist.gs1.subList(offset, offset + count);
			gs1_returns = adjust_returns(gs1_returns, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
		}

		List<Double> aaa_returns = null;
		if (scenario.asset_classes.contains("aaa"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.aaa_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.aaa.size());
			aaa_returns = hist.aaa.subList(offset, offset + count);
			aaa_returns = adjust_returns(aaa_returns, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
		}

		List<Double> baa_returns = null;
		if (scenario.asset_classes.contains("baa"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.baa_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.baa.size());
			baa_returns = hist.baa.subList(offset, offset + count);
			baa_returns = adjust_returns(baa_returns, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
		}

		List<Double> t1_returns = null;
		if (scenario.asset_classes.contains("cash"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.t1_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.t1.size());
			t1_returns = hist.t1.subList(offset, offset + count);
			t1_returns = adjust_returns(t1_returns, fixed_income_adjust * adjust_management_expense * adjust_all, 1);
		}

		List<Double> gold_returns = null;
		if (scenario.asset_classes.contains("gold"))
	        {
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.gold_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.gold.size());
			gold_returns = hist.gold.subList(offset, offset + count);
			gold_returns = adjust_returns(gold_returns, adjust_management_expense * adjust_all, 1);
		}

		List<Double> margin_returns = null;
		if (scenario.asset_classes.contains("margin"))
		{
		        assert(time_periods == 1);
		        int offset = (int) Math.round((start_year - hist.t1_initial) * time_periods);
			assert(offset >= 0);
			assert(offset + count <= hist.t1.size());
		        List<Double> margin = new ArrayList<Double>();
		        for (double ret : hist.t1)
		                margin.add(ret + config.margin_premium);
			margin_returns = margin.subList(offset, offset + count);
			margin_returns = adjust_returns(margin_returns, adjust_all, 1);
                }

		List<Double> risk_free_returns = new ArrayList<Double>();
		double risk_free_return = (Math.pow(1.0 + ret_risk_free, 1.0 / time_periods) - 1.0);
		double perturb = 1e-5;  // Prevent MVO dying on risk free asset class.
		for (int i = 0; i < count; i++)
		{
			risk_free_returns.add(risk_free_return + perturb);
			perturb = - perturb;
		}
		risk_free_returns = adjust_returns(risk_free_returns, adjust_management_expense * adjust_all, 1);

		List<Double> cpi_returns = new ArrayList<Double>();
		for (int year = start_year; year <= end_year; year++)
		{
			int i = (year - hist.initial_year) * 12 + 12;
			double cpi_d = hist.cpi_index.get(i) / hist.cpi_index.get(i - 12);
			cpi_returns.add(cpi_d - 1.0);
		}
		double cpi_geomean = Utils.plus_1_geomean(cpi_returns);
		double cpi_adjust = (ret_inflation == null) ? 1 : (Math.pow(1.0 + ret_inflation, 1.0 / time_periods) / cpi_geomean);
		cpi_returns = adjust_returns(cpi_returns, cpi_adjust, 1);

		List<Double> ef_returns = new ArrayList<Double>();
		for (int i = 0; i < count; i++)
		{
			ef_returns.add(0.0);
		}

		List<double[]> returns = new ArrayList<double[]>();
		dividend_fract = new double[scenario.asset_classes.size()];
		for (int a = 0; a < scenario.asset_classes.size(); a++)
		{
		        String asset_class = scenario.asset_classes.get(a);

		        List<Double> rets = null;
			double divf = Double.NaN;

			if ("stocks".equals(asset_class))
			{
			        rets = equity_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("bonds".equals(asset_class))
			{
				rets = fixed_income_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("gs10".equals(asset_class))
			{
				rets = gs10_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("eafe".equals(asset_class))
			{
				rets = eafe_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("bl".equals(asset_class))
			{
				rets = ff_bl_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("bm".equals(asset_class))
			{
				rets = ff_bm_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("bh".equals(asset_class))
			{
				rets = ff_bh_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("sl".equals(asset_class))
			{
				rets = ff_sl_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("sm".equals(asset_class))
			{
				rets = ff_sm_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("sh".equals(asset_class))
			{
				rets = ff_sh_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("equity_reits".equals(asset_class))
			{
				rets = reits_equity_returns;
				divf = config.dividend_fract_equity;
			}
			else if ("mortgage_reits".equals(asset_class))
			{
				rets = reits_mortgage_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("gs1".equals(asset_class))
			{
				rets = gs1_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("aaa".equals(asset_class))
			{
				rets = aaa_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("baa".equals(asset_class))
			{
				rets = baa_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("cash".equals(asset_class))
			{
				rets = t1_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("margin".equals(asset_class))
			{
				rets = margin_returns;
				divf = 0.0;
			}
			else if ("risk_free".equals(asset_class))
			{
				rets = risk_free_returns;
				divf = config.dividend_fract_fixed_income;
			}
			else if ("gold".equals(asset_class))
			{
				rets = gold_returns;
				divf = 0.0;
			}
			else if ("[cpi]".equals(asset_class))
			{
				rets = cpi_returns;
			}
			else if (Arrays.asList("[ria]", "[nia]", "[spend_fract]", "[ef_index]").contains(asset_class))
			{
				rets = ef_returns;
			}

			returns.add(Utils.DoubleTodouble(rets));

			dividend_fract[a] = divf;
		}

		am = new double[returns.size()];
		sd = new double[returns.size()];
		for (int a = 0; a < returns.size(); a++)
                {
		        double[] rets = returns.get(a);
		        am[a] = Utils.mean(rets);
			sd[a] = Utils.standard_deviation(rets);
                }
                corr = Utils.correlation_returns(returns);
		cholesky = Utils.cholesky_decompose(corr);

		returns = Utils.zipDoubleArray(returns);
		this.original_data = returns;

		if (num_sequences == null)
		        num_sequences = returns.size();

	        this.data = returns;
	        random = new Random(ret_seed);
		if (ret_shuffle.equals("once"))
		{
		        this.data = Arrays.asList(shuffle_returns(num_sequences));
		}
		else if (cache_returns && ret_shuffle.equals("all") && !reshuffle)
		{
			int total_periods = (int) (scenario.ss.max_years * time_periods);
			for (int i = 0; i < num_sequences; i++)
				returns_cache.add(shuffle_returns(total_periods));
		}
		random = null;

		this.returns_unshuffled = this.data.toArray(new double[0][]);

		this.returns_unshuffled_probability = new double[returns_unshuffled.length];
		for (int i = 0; i < returns_unshuffled_probability.length; i++)
		        returns_unshuffled_probability[i] = (short_block ? 1 : Math.min(Math.min(block_size, i + 1), returns_unshuffled.length - i));
		double sum = Utils.sum(returns_unshuffled_probability);
		for (int i = 0; i < returns_unshuffled_probability.length; i++)
		        returns_unshuffled_probability[i] /= sum;
	}

        public Returns clone()
        {
	        assert(random == null);

		Returns returns = null;
		try
		{
		        returns = (Returns) super.clone();
		}
		catch (CloneNotSupportedException e)
		{
		        assert(false);
		}

		returns.random = new Random(ret_seed);

	        return returns;
	}

        public void setSeed(long i)
	{
	        random.setSeed(i);
        }

	public double[][] shuffle_returns(int length)
	{
	        List<double[]> returns = this.data;

		int len_returns = returns.size();

		double[][] new_returns = new double[length][];

		if (draw.equals("random"))
		{
			int len_available;
			int bs1;
			if (short_block)
			{
				len_available = len_returns;
				bs1 = block_size - 1;
			}
			else
			{
				len_available = len_returns - block_size + 1;
				bs1 = 0;
			}

			if (pair)
			{
			        int offset = short_block ? random.nextInt(block_size) : 0;
				int index = random.nextInt(len_available);
				for (int y = 0; y < length; y++)
				{
					if ((y + offset) % block_size == 0 || index == len_returns)
					{
					        index = random.nextInt(len_available + bs1) - bs1;
						if (index < 0)
						{
						        offset = - index - y;
						        index = 0;
						}
						else
						        offset = - y;
					}
					new_returns[y] = returns.get(index);
					index++;
				}
			}
			else
			{
			        int ret0Len = scenario.asset_classes.size();
			        int ret0NoEfIndex = scenario.normal_assets; // Prevent randomness change due to presence of ef index.
				int offset[] = new int[ret0NoEfIndex];
				int index[] = new int[ret0NoEfIndex];
				for (int i = 0; i < ret0NoEfIndex; i++)
				{
				        offset[i] = short_block ? random.nextInt(block_size) : 0;
					index[i] = random.nextInt(len_available);
				}
				for (int y = 0; y < length; y++)
				{
					for (int i = 0; i < ret0NoEfIndex; i++)
					{
						if ((y + offset[i]) % block_size == 0 || index[i] == len_returns)
						{
							index[i] = random.nextInt(len_available + bs1) - bs1;
							if (index[i] < 0)
							{
							        offset[i] = - index[i] - y;
								index[i] = 0;
							}
							else
							        offset[i] = - y;
						}
					}
					double[] new_return = new double[ret0Len];
					for (int i = 0; i < ret0NoEfIndex; i++)
					{
						new_return[i] = returns.get(index[i])[i];
					}
					new_returns[y] = new_return;
					for (int i = 0; i < ret0NoEfIndex; i++)
					{
						index[i] = (i + 1) % len_returns;
					}
				}
			}
		}
		else if (draw.equals("shuffle"))
		{
			assert(length <= len_returns);

			if (pair)
			{
			        List<double[]> shuffle_returns = new ArrayList<double[]>();
				shuffle_returns.addAll(returns);
				Collections.shuffle(shuffle_returns, random);
				shuffle_returns = shuffle_returns.subList(0, length);
				new_returns = shuffle_returns.toArray(new double[length][]);
			}
			else
			{
				@SuppressWarnings("unchecked")
				List<double[]> asset_class_returns = Utils.zipDoubleArray(returns);
				List<double[]> new_asset_class_returns = new ArrayList<double[]>();
				for (double[] asset_class_return : asset_class_returns)
				{
				        List<Double> new_asset_class_return = new ArrayList<Double>();
					for (double ret : asset_class_return)
					        new_asset_class_return.add(ret);
					Collections.shuffle(new_asset_class_return, random);
					double[] shuffle_asset_class_return = Utils.DoubleTodouble(new_asset_class_return);
					new_asset_class_returns.add(shuffle_asset_class_return);
				}
				List<double[]> shuffle_returns = Utils.zipDoubleArray(new_asset_class_returns);
				new_returns = shuffle_returns.toArray(new double[length][]);
			}
		}
		else if (draw.equals("normal") || draw.equals("skew_normal"))
                {
		        int ret0Len = scenario.asset_classes.size();
			int ret0NoEfIndex = scenario.normal_assets; // Prevent randomness change due to presence of ef index.

		        if (pair)
			{
			        // Generation of correlated non-autocorrelated returns using Cholesky decomposition.
			        // Cholesky produces returns that are normally distributed.
				double[] aa = new double[ret0Len];
			        for (int y = 0; y < length; y++)
				{
					for (int a = 0; a < ret0NoEfIndex; a++)
					        aa[a] = random.nextGaussian();
					new_returns[y] = Utils.vector_sum(am, Utils.vector_product(sd, Utils.matrix_vector_product(cholesky, aa)));
					if (draw.equals("skew_normal"))
					        for (int a = 0; a < ret0NoEfIndex; a++)
						        if (new_returns[y][a] < 0)
							        new_returns[y][a] = 1 / (1 - new_returns[y][a]) - 1;
				}
		        }
		        else
		        {
			        // Generation of non-correlated returns using normal distribution.
				for (int y = 0; y < length; y++)
				{
					double[] aa = new double[ret0Len];
					for (int a = 0; a < ret0NoEfIndex; a++)
					        aa[a] = am[a] + sd[a] * random.nextGaussian();
				        new_returns[y] = aa;
				}
		        }
                }
		else
		        assert(false);

		return new_returns;
	}

	public double[][] shuffle_returns_cached(int s, int length)
	{
	        double[][] returns_array = returns_cache.get(s);
		assert(returns_array.length >= length);
		return returns_array;
	}

	private List<Double> reduce_returns(List<Double> l, int size)
	{
	        List<Double> r = new ArrayList<Double>();
		int i = 0;
		while (i < l.size())
		{
		        Double ret = 1.0;
			for (int j = 0; j < size; j++)
			{
			        ret *= 1.0 + l.get(i);
				i++;
			}
			r.add(ret - 1.0);
		}
		return r;
	}
}
