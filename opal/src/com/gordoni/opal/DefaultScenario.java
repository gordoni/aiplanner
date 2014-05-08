package com.gordoni.opal;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class DefaultScenario extends BaseScenario
{
	private String param_filename;

	@SuppressWarnings("unchecked")
        public DefaultScenario(Config config, HistReturns hist, String cwd, Map<String, Object> params, String param_filename) throws IOException, InterruptedException
	{
	        this.config = config;
	        this.hist = hist;

		// Override default scenario based on scenario file.
		boolean param_filename_is_default = (param_filename == null);
		if (param_filename_is_default)
			this.param_filename = config.prefix + "-scenario.txt";
		else
			this.param_filename = param_filename;

		File f = new File(cwd + '/' + this.param_filename);
		if (!f.exists())
		{
			if (!param_filename_is_default)
				throw new FileNotFoundException(this.param_filename);
		}
		else
		{
		        BufferedReader reader = new BufferedReader( new FileReader (f));
			StringBuilder stringBuilder = new StringBuilder();
			String line;
			while ((line = reader.readLine()) != null)
			{
			        stringBuilder.append(line);
			        stringBuilder.append(System.getProperty("line.separator"));
                        }
			Map<String, Object> fParams = new HashMap<String, Object>();
		        config.load_params(fParams, stringBuilder.toString());
			config.applyParams(fParams);
		}

		// Override default scenario based on command line arguments.
		if (params != null)
		        config.applyParams(params);

                // Internal parameters.

		int p_size = 0;
		tp_index = (config.start_tp == null ? null : p_size);
		if (tp_index != null)
		        p_size++;
		ria_index = (config.start_ria == null ? null : p_size);
		if (ria_index != null)
		        p_size++;
		nia_index = (config.start_nia == null ? null : p_size);
		if (nia_index != null)
		        p_size++;
		start_p = new double[p_size];
		if (tp_index != null)
		        start_p[tp_index] = config.start_tp;
		if (ria_index != null)
		        start_p[ria_index] = config.start_ria;
		if (nia_index != null)
		        start_p[nia_index] = config.start_nia;

		// Set up the scales.
		scale = new Scale[start_p.length];
		if (tp_index != null)
		        scale[tp_index] = Scale.scaleFactory(config.zero_bucket_size, config.scaling_factor);
		if (ria_index != null)
		        scale[ria_index] = Scale.scaleFactory(config.annuity_zero_bucket_size, config.annuity_scaling_factor);
		if (nia_index != null)
		        scale[nia_index] = Scale.scaleFactory(config.annuity_zero_bucket_size, config.annuity_scaling_factor);

		// Calculated parameters.

	        config.cwd = cwd;

		// Generate data all the way down to the floor.
		config.generate_bottom_bucket = this.scale[tp_index].pf_to_bucket(config.pf_guaranteed);
		// Generate data all the way up to the ceiling.
		config.generate_top_bucket = this.scale[tp_index].pf_to_bucket(config.pf_fail);
		// Report data all the way down to the validate floor.
		config.validate_bottom_bucket = this.scale[tp_index].pf_to_bucket(config.pf_validate);
		// Report data all the way up to the validate ceiling.
		config.validate_top_bucket = this.scale[tp_index].pf_to_bucket(0.0);
		config.success_mode_enum = Metrics.to_enum(config.success_mode);
		vital_stats = new VitalStats(config, hist);
		vital_stats.compute_stats(config.generate_time_periods, config.generate_life_table); // Compute here so we can access death.length.
		vital_stats_annuity = new VitalStats(config, hist);
		annuity_stats = new AnnuityStats(this, config, hist, vital_stats_annuity);
		annuity_stats.compute_stats(config.generate_time_periods, config.annuity_table);
;
		if (config.cw_schedule != null && config.max_years > config.cw_schedule.length)
		        config.max_years = config.cw_schedule.length;
		if (config.validate_age >= config.start_age + config.max_years)
		        config.validate_age = config.start_age; // Prevent divisions by zero??

		config.normal_assets = config.asset_classes.size();

		// Sanity checks.
		if (config.ef.equals("none"))
		{
			assert(config.asset_classes.contains(config.safe_aa));
			assert(config.asset_classes.contains(config.fail_aa));
		}
		assert(config.max_borrow == 0.0 || !config.borrow_aa.equals(config.fail_aa));
		assert(config.validate_time_periods >= config.rebalance_time_periods);
		assert(!config.utility_epstein_zin || (config.success_mode_enum == MetricsEnum.COMBINED)); // Other success modes not Epstein-Zinized.

		System.out.println("Parameters:");
		config.dumpParams();
		System.out.println();

		// More internal parameters.

		do_tax = config.tax_rate_cg != 0 || config.tax_rate_div != null || config.tax_rate_div_default != 0 || config.tax_rate_annuity != 0;

		ria_aa_index = -1;
		if (ria_index != null)
		{
		        assert(config.sex2 == null); // Calculated annuity purchase prices are for a couple which doesn't work if one party is dead.
		        ria_aa_index = config.asset_classes.size();
			config.asset_classes.add("[ria]");
		}
		nia_aa_index = -1;
		if (nia_index != null)
		{
		        assert(config.sex2 == null);
		        nia_aa_index = config.asset_classes.size();
			config.asset_classes.add("[nia]");
		}
		spend_fract_index = config.asset_classes.size();
		config.asset_classes.add("[spend_fract]");
		all_alloc = config.asset_classes.size();
		cpi_index = -1;
		if (do_tax || nia_index != null)
		{
		        cpi_index = config.asset_classes.size();
		        config.asset_classes.add("[cpi]");
		}
		ef_index = -1;
		if (!config.ef.equals("none"))
		{
		        ef_index = config.asset_classes.size();
		        config.asset_classes.add("[ef_index]");
		}

		// Set up utility functions.
		Double eta = (config.utility_epstein_zin ? (Double) config.utility_gamma : config.utility_eta);
		Utility utility_consume_risk = Utility.utilityFactory(config, config.utility_consume_fn, eta, config.utility_alpha, 0, config.withdrawal, config.utility_ce, config.utility_ce_ratio, 2 * config.withdrawal, 1 / config.utility_slope_double_withdrawal, config.withdrawal, 1, config.public_assistance, config.public_assistance_phaseout_rate, config.withdrawal * 2);
		eta = (config.utility_epstein_zin ? (Double) (1 / config.utility_psi) : config.utility_eta);
		utility_consume_time = Utility.utilityFactory(config, config.utility_consume_fn, eta, config.utility_alpha, 0, config.withdrawal, config.utility_ce, config.utility_ce_ratio, 2 * config.withdrawal, 1 / config.utility_slope_double_withdrawal, config.withdrawal, 1, config.public_assistance, config.public_assistance_phaseout_rate, config.withdrawal * 2);
		double bequest_consume = (config.utility_bequest_consume == null ? config.withdrawal : config.utility_bequest_consume);
		// Model: Bequest to 1 person for utility_inherit_years or utility_inherit_years people for 1 year who are currently consuming bequest_consume
		// and share the same utility function as you.
		double scale = config.utility_inherit_years;
		if (config.utility_join)
		{
		        Utility utility_gift = new UtilityScale(config, utility_consume_risk, 0, 1 / config.utility_inherit_years, scale * config.utility_live, - bequest_consume);
		        utility_consume = new UtilityJoin(config, utility_consume_risk, utility_gift);
		        utility_gift = new UtilityScale(config, utility_consume_time, 0, 1 / config.utility_inherit_years, scale * config.utility_live, - bequest_consume);
		        utility_consume_time = new UtilityJoin(config, utility_consume_time, utility_gift);
		}
		else
		        utility_consume = utility_consume_risk;
		utility_inherit = new UtilityScale(config, utility_consume_time, 0, 1 / config.utility_inherit_years, scale * config.utility_dead_limit, - bequest_consume);
		utility_inherit.range = config.withdrawal * 100;
	}
}
