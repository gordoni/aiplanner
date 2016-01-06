/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2016 Gordon Irlam
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

import java.lang.Exception;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Class containing all the configuration parameters  
 * 
 * @author William
 *
 */
public class Config
{
        public String version = "java-1.2.15";

        public String prefix = "opal"; // Prefix to use for result files.

        public boolean trace = false; // Be chatty.
        public boolean trace_error = false; // Less chatty tracing of error bar calculations.
        public boolean debug_till_end = false; // Whether to plot until the final year or display graphs only through age 99.

        public int tasks_generate = 100; // Break generation into this many concurrent tasks.
        public int tasks_validate = 500; // Break validation into this many concurrent tasks.
                // Changing this value will alter the results due to different random number generators being used for each task.
        public int workers = Runtime.getRuntime().availableProcessors(); // Number of worker threads to use.
        public boolean conserve_ram = false; // Whether to conserve memory by not storing the simulate() results.
        public boolean search_cache_map = true; // Whether to use a hashmap or an arraylist for the search cache.
        public String validate = null; // Load asset allocation from validate prefix rather than generating it.
        public boolean skip_generate = false; // Speed up by not generating aa/consume.
        public boolean skip_retirement_number = true; // Speed up by not generating retirement number values.
        public boolean skip_success_lines = true; // Speed up by not generating success lines.
        public boolean skip_compare = true; // Speed up by not performing comparison.
        public boolean skip_target = true; // Speed up by not performing goal targeting.
        public boolean skip_validate = false; // Speed up by not performing any validation.
        public boolean skip_validate_all = true; // Speed up by performing validation at a specific age rather than at every age.
        public boolean skip_smooth = true; // Speed up by not performing smoothing.
        public boolean skip_metric_jpmorgan = true; // Speed up by not calculating jpmorgan metric when validating.
        public boolean skip_metric_wer = true; // Speed up by not calculating withdrawal efficiency rate.
        public boolean skip_sample_cholesky = true; // Speedup simulation by using the returns Cholesky matrix for the trial sample Cholesky matrix.
        public boolean skip_dump_load = true; // Speed up by not dumping and loading asset allocation.
        public boolean skip_dump_le = false; // Speed up by not dumping life expectencies.
        public boolean skip_dump_log = true; // Save disk by not dumping future maps.
        public boolean skip_corr = true; // Don't report the correlation matrix.

        public int dump_max_age = Integer.MAX_VALUE; // Dump this age and below.
        public double dump_max_tp = Double.POSITIVE_INFINITY; // Dump this portfolio value and below.
        public double dump_max_ria = 0; // Dump this real immediate anuity payout and below.
        public double dump_max_nia = 0; // Dump this nominal immediate annuity payout and below.

        // Simulation specific parameters.

        public double tp_zero_factor = 0.0001; // Portfolio buckets this much of consume_max_est at portfolio 0.
        public double annuity_zero_factor = 0.001; // Taxable immediate annuity payout buckets this much of consume_max_est appart at payout 0.

        public double scaling_factor = 1.05; // Successive portfolio buckets this much larger.
               // This can be set quite a bit higher without affecting path metrics.
               // However the map metric will start to suffer very slightly.
               // We set it low to allow validate_draw='bootstrap' bootstrap_block_size=0 generation validation.
               // Old comment (pre-spline value was 1.002): Above 1.01 aa plots start to become pixelated.
        public double annuity_scaling_factor = 1.05; // Successive immediate annuity buckets this much larger.

        public Double consume_max = null; // Estimate of maximum consumption level. Should only need to specify when debugging.
        public Double tp_max = null; // Estimate of maximum portfolio size. Should only need to specify when debugging.

        public double ria_high = 100000; // Maximum taxable real immediate annuity payout.
        public double nia_high = 100000; // Maximum taxable nominal immediate annuity payout.

        public int retirement_number_steps = 100; // Retirement number steps.
        public double success_lines_scale_size = 0.2; // Success probability line linear scale.
        public double generate_time_periods = 1.0; // 1.0 to perform analysis on an annual basis, or 12.0 to perform analysis monthly.
        public double validate_time_periods = 1.0;
        public double rebalance_time_periods = 1.0;

        public String aa_strategy = "sdp";
                // Asset allocation scheme for generation. "sdp", "file" for validate=datafile,
                // "fixed_aa", "fixed", "age_in_bonds", "age_minus_10_in_bonds", or "target_date".
        public Double aa_fixed_stocks = 1.0; // Proportion stocks for fixed asset allocation scheme. Null to search for best fixed aa.
        public double[] fixed_aa = null; // Fixed_aa holding fractions.
        public double aa_fixed_steps = 100; // Search delta to use when searching for best fixed aa.
        public boolean db_bond = false;
                // Treat defined benefit as equal to a bond of value defined_benefit * retirement life expectancy in determining asset allocation.
        public boolean savings_bond = false;
                // Treat future savings as equal to a bond in determining asset allocation.
        public boolean vbond_discounted = false; // Use vbond_discount_rate discounted life expectancy when computing db_bond and savings_bond.
        public double vbond_discount_rate = 0.0; // Discount rate to use if discounting db_bond and savings_bond income.
        public double stock_bias = 0.0; // Bias to apply to stocks to improve random_block_size > 1 results due to momentum and reversion to the mean.
        public double[] aa_offset = null; // Offset to apply during valadation to the generated asset allocation.
                // Used to determine the implications of a 10% error in aa. More general than stock bias.

        public List<String> asset_classes = new ArrayList<String>(Arrays.asList("stocks", "bonds")); // Which asset classes to simulate out of 'stocks', 'bonds', 'eafe', 'bl', 'bm', 'bh', 'sl', 'sm', 'sh', 'equity_reits', 'mortgage_reits', 'gs1', 'gs10', 'tips', 'aaa', 'baa', 'cash', 'gold', 'risk_free', and 'margin'.
                // Seem to get quicker search time if list highest return assets first.
        public List<String> asset_class_names = null;
               // Corresponding asset class names to use for MVO inputs and transition map.
        public int aa_steps = 1000; // Use 4 steps to mirror 5 choice Trinity study.
        public boolean compute_risk_premium = false; // Compute the risk premium against cash (t1) instead of generating/targeting/validating.
        public String ef = "none";
               // Efficient frontier calculation method. "mvo", or "none" to search asset allocations.
        public double risk_tolerance = 1e12; // Maximum permitted relative standard deviation in portfolio returns when performing MVO.

        public double annuity_steps = 10000; // Number of annuitization steps. Keep steps small since annuitization can't be undone.
        public boolean annuity_partial = true; // Allow partial annuitization, or make annuitization a one time complete irrevocable decision.
        public double annuity_time_periods = 12; // Number of times per year to receive annuity payments in the annuity pricing model.
        public int annuity_mwr_age1 = 50; // Age for first Money's Worth Ratio value.
        public int annuity_mwr_age2 = 90; // Age for second Money's Worth Ratio value.
        public boolean annuity_real_synthetic = true; // Whether to use sythetically generated real annuity quotes based on life table.
               // Strictly speaking use of actual quotes is cheating becasue actual quotes are period quotes that don't reflect cohort mortality improvements.
               // Actual quotes are only available for a few sparse years which may be inadequate for annuity_partial.
        public String annuity_real_quote = "2014-04-15"; // Source for non-synthetic real quotes.
        public double annuity_real_mwr1 = 1.0; // Money's Worth Ratio associated with synthetic real annuity (NPV less profit and expense) at first age.
        public double annuity_real_mwr2 = 1.0; // Money's Worth Ratio associated with synthetic real annuity (NPV less profit and expense) at second age.
        public double annuity_real_rate = 0.02; // Real interest rate/discount rate associated with synthetic real annuity.
        public String annuity_real_yield_curve = null; // Treasury TIPS yield curve to use for synthetic annuity.
               // Null to use constant annuity_real_rate. Or a date like "2014-04-15" (invokes R to interpolate yield curve so marginally slower).
               // (Can't use math3 to interpolate because doesn't handle years less than lowest actual year ie. years 0-4).
               // Erroneously assumes the same yield curve will be present throughout time.
        public double annuity_real_yield_curve_adjust = 0; // Adjustment to apply to yield curve rates.
        public int annuity_real_long_years = 30; // Maturity beyond which a lack of bond availability causes rates to be reduced.
        public double annuity_real_long_penalty = 0.0; // Amount by which to reduce rates post long_years to reflect lack of bond availability.
        public boolean annuity_nominal_synthetic = true; // Whether to use sythetically generated nominal annuity quotes based on life table.
               // Strictly speaking use of actual quotes is cheating becasue actual quotes are period quotes that don't reflect cohort mortality improvements.
               // In other words annuities are expected to become more expensive in the future.
        public String annuity_nominal_quote = "2014-04-15"; // Source for non-synthetic nominal quotes.
        public double annuity_nominal_mwr1 = 1.0; // Money's Worth Ratio associated with synthetic nominal annuity (NPV less profit and expense) at first age.
        public double annuity_nominal_mwr2 = 1.0; // Money's Worth Ratio associated with synthetic nominal annuity (NPV less profit and expense) at second age.
        public double annuity_nominal_rate = 0.04; // Nominal interest rate/discount rate associated with synthetic nominal annuity.
               // Have seen values of 5 and 6% used on the web. So possibly on the low side, but gives results consistent with non-synthetic annuities.
        public String annuity_nominal_yield_curve = "2014-Apr";
               // Treasury corporate high quality market yield curve to use for synthetic annuity. May be an implicitly anchored regexp.
               // Null to use constant annuity_nominal_rate.
               // Erroneously assumes the same yield curve will be present throughout time.
        public double annuity_nominal_yield_curve_adjust = 0; // Adjustment to apply to yield curve rates.
        public int annuity_nominal_long_years = 30; // Maturity beyond which a lack of bond availability causes rates to be reduced.
        public double annuity_nominal_long_penalty = 0.0; // Amount by which to reduce rates post long_years to reflect lack of bond availability.
        public double annuity_payout_delay = 1.5; // Delay in months until first payout from a newly purchased annuity.

        public int error_count = 0; // Number of scenarios to generate to produce error bars on estimates.
        public boolean equity_premium_vol = true; // Whether to consider the distribution of different possible population equity premiums when generating error bars.
        public double gamma_vol = 0.0;
                // Scale parameter for log normally distributed multiplicative adjustment to be applied to utility eta/gamma for generating error bars.
        public double q_vol = 0.0;
                // Scale parameter for log normally distributed multiplicative adjustment to be applied to mortality q values for generating error bars.

        public String safe_aa = "bonds";
                // Which asset allocation choice to favor when choices are equal, and success is guaranteed.
                // Irrelevant if tangency_aa is non-null.
        public String fail_aa = "stocks";
                // Which asset allocation choice to favor when choices are equal, and failure is guaranteed.
                // Irrelevant if tangency_aa is non-null.
        public double ret_risk_free = 0.0; // Real return for risk-free asset class.
        public double ret_borrow = 0.0; // Annual cost rate when portfolio is negative. Also annual cost for cost metric.
        public double min_safe_aa = 0.0; // Minimum safe_aa holding fraction.
        public double min_safe_abs = 0.0; // Minimum safe_aa holding plus annuity values.
        public double min_safe_le = 0.0; // Minimum safe_aa holding plus annuity values divided by then life expectancy.
        public double min_safe_until_age = 999; // Don't enforce min_safe constraints at or beyond this age.

        public int spend_steps = 10000; // Number of portfolio expenditure steps.

        public String vw_strategy = "sdp";
                // Variable withdrawal strategy to use.
                // "amount" for no variable withdrawals; use withdrawal amount.
                // "retirement_amount" for no variable withdrawals; use fixed percentage of retirement date portfolio.
                // "sdp" for sdp.
                // "percentage" for constant percentage.
                // "life" for 1 / life_expectancy.
                // "discounted_life" for 1 / consume_discount_weight discounted life_expectancy.
                // "merton" for consumption according to solution to Merton's portfolio problem; uses then current life expectancy and doesn't discount future income
                // Requires vw_merton_nu be set.
                // "vpw" for even consumption at some assumed real rate of return (Bogleheads Variable Percentage Withdrawal scheme).
        public Double vw_percentage = 0.04; // Withdrawal percentage to use for strategies retirement_amount and percentage. Null to search.
        public double vw_percentage_steps = 1000; // Search delta to use when searching for best vw_percentage.
        public double vw_le_min = 0; // Minimum allowed life expectancy for life and discounted_life.
        public int vw_years = 30; // VPW payout years.
        public double vw_rate = 0.03; // VPW assumed real rate of return.
        public Double vw_merton_nu = null; // Value to use for nu in the solution to Merton's portfolio problem.
        public double vw_merton_le_factor = 1.0; // Multiply life expectancy by this much for "merton".

        public boolean book_post = false; // false to book consumption at the start of the time period when it is subtracted; true to book at the end.
                // Use of book_post=true gets rid of an annoying uptick on first median consumption when retired, but this uptick might be valid,
                // reflecting a greater weight placed on below median consumption values.
                // Use of book_post=true also seems to destroy monte_carlo_validate model, or at least monte_carlo_validate generated model fails to fully validate.
                // Use of book_post=true is also more conservative as consumption benefits only accrue if you survive the full year.
        public boolean spend_fract_all = false; // Whether to allow consumption/contribution choice for all years or only in retirement.
        public String search = "memory"; // How to search the asset allocation / spend_fract space for each map location.
                // "all" - exhaustive search (painfully slow)
                // "hill" - axis based hill climbing (fast; fails on diagonal ridges causing vertical or horizontal line noise)
                // "gradient" - gradient ascent (slow; zig-zags and fails on ridges causing horizontal line noise; fails with efficient frontier)
                // "memory" - ascent with directional memory (medium; works on ridges; fails with efficient frontier)
        public int search_memory_attempts = 20; // Number of random attempts for "memory" before deciding no improvement can be found and shrinking search radius.
                //  8 results in accurate metrics with no annuities.
                // 10 results in noisy nia plot and 4 horizontal lines with annuities.
                // 20 results in only slightly noisy nia plot with annuities.
        public boolean search_neighbour = false; // Whether to attempt to uncover non-local maxima by searching based on neighbouring points at a given age.
        public Integer num_sequences_generate = null; // Number of paths for shuffled or time_varying generate or None to base off of length of returns sequences.
        public String success_mode = "combined";
                // What to optimize for.  'tw' for time weighted, or 'ntw' for non-time weighted, or 'tw_simple' or
                // 'ntw_simple' to ignore partial year solvency and success through death,
                // 'inherit' for discounted inheritance, 'consume' for discounted consumption utility, 'combined' for both, or 'cost' for NPV cost.
                // The Trinity study claims to uses NTW simple. How else could they get 0% success for 30 year bonds at 7%?
                // One would thus expect them to get percentages that are a multiple of 1 /
                // 41 for 30 years, or 1 / 51 for 20 years, or in general 1 / the number of samples.
                // This appears to be the case.

        public boolean interpolation_linear = false; // Use old linear interpolation code; any number of p dimensions.
        public boolean interpolation_validate = true; // Perform interpolation on validation.
                // Want to disable for non-partial annuitization, otherwise decision to annuitize could get interpolated.
                // Results in nia_aa and spend_fract indexes around 0.5 instead of both close to 0 or 1, which causes a consumption spike.
        public String interpolation1 = "spline"; // How to interpolate non-grid 1 dimensional p values.
                // "linear" - linear interpolation using math3 library. For debugging.
                // "spline" - cubic spline interpolation.
        public String interpolation2 = "spline-linear"; // How to interpolate non-grid 2 dimensional p values.
                // "spline" - cubic spline interpolation. Unacceptable 6 fold slowdown with annuities.
                // "linear-spline" - linear in first dimension; spline in second.
                // "spline-linear" - spline in first dimension; linear in second.
        public String interpolation3 = "spline"; // How to interpolate non-grid 3 dimensional p values.
                // "spline" - cubic spline interpolation.

        public boolean negative_p = false; // Allow negative portfolio values versus utilized reduced consumption when p near zero.
        public double consume_discount_rate = 0.0; // Discount rate to apply to consumption.
                // Should probably exceed maximum after tax asset class return, otherwise a winning strategy can be to invest everything in the maximum asset class.
        public double upside_discount_rate = 0.0; // Discount rate to apply to consumption above utility_join_1.
        // No hyperbolic utility. Appers to just be power shifted and scaled, which we do anyway with public assistance.
        public boolean utility_retire = true; // Whether to compute non-tw/ntw metrics just for retirement, or across the entire lifecycle.
        public boolean utility_epstein_zin = false; // Whether to utilize separate risk and time consumption utility functions.
        public String utility_consume_fn = "power"; // Consumption utility function to use. "power", "exponential", "hara", or "linear".
        public boolean utility_join = false; // Whether to join a second power utility to consume utility function.
        public String utility_join_type = "slope-cubic-monotone"; // When joining where to interpolate any gap. 'slope-linear',
               // 'slope-cubic-monotone', 'slope-cubic-smooth', or 'ara'.
               // slope-linear - interpolate utility slopes linearly.
               // slope-cubic-monotone - interpolate utility slopes using a cubic polynomial; slope not guaranteed to be smooth at join points.
               // slope-cubic-smooth - interpolate utility slopes using a cubic polynomial; guaranteed smooth at join points but may be impossible to produce.
               // ara - interpolate over the coefficient of absolute risk aversion linearly.
        public double utility_gamma = 4; // Consumption Epstein-Zin utility risk aversion.
        public double utility_psi = 1 / 4.0; // Consumption Epstein-Zin utility elasticity of inter-temporal substitution.
        public Double utility_eta = null; // Consumption power utility eta parameter to use in place of utility_slope_zero definition, e.g. 3.
        public double utility_beta = 0.0; // Consumption HARA utility beta parameter.
        public Double utility_alpha = null; // Consumption exponential utility alpha parameter.
               // If the same relative slopes are desired at consumptions c1 and c2 as occur with a power utility function eta then,
               // alpha = - eta . ln(c1/c2) / (c2 - c1).
        public Double utility_ce = null; // Specify consumption power utility eta parameter as indifferent to utility_ce * c and a
               // 50/50 chance of either c or utility_ce_ratio * c.
        public double utility_ce_ratio = 2;
        public double utility_slope_double_withdrawal = 16; // Change in utility for a dollar of consumption at withdrawal relative to 2 * withdrawal.
               // Excludes assistance reduction.
        public double defined_benefit = 0.0; // Defined benefit plans in retirement annual amount.
        public double public_assistance = 0.1; // Consumption level at which public assistance kicks in, in dollars.
               // Assuming power utility set defined_benefit and public_assistance to 0 to avoid low portfolio size maximum return "wedge artifact".
               // Then get a minimum return wegde artifact as interpolated -Infinity consumption utilities back up.
               // Can either use a smaller tp_zero_factor, use an infinitesimal value for public_assistance, or generate_interpolate=false.
               // But in this last case need to run at a much higher scale to avoid noise.
        public double public_assistance_phaseout_rate = 0.0; // Public assistance is reduced at this rate for each dollar of consumption
        public double utility_eta_2 = 3; // Consumption power utility second utility_join eta parameter.
        public double utility_join_required = 1e12; // Floor plus upside separation point. Consumption utility_join start of join.
        public double utility_join_slope_ratio = 1; // Consumption utility_join slope ratio at join point.
        public double utility_join_desired = 0; // Consumption utility_join width of join.
        public double utility_dead_limit = 0; // Maximum fraction of remaining utility capable of being satisfied by being able to leave a bequest.
        public double utility_inherit_years = 10; // Value inheritance using the utility function but treat it as being spread over this many individuals or years.
                // If leaving an inheritance, set this parameter to 1 and utility to power to avoid maximum return "swirl artifact" at high ages.
        public Double utility_bequest_consume = null; // Value inheritance at this consumption amount.
        public int utility_steps = 1000;  // Utility cache steps.
                // Cutoff at utility_cutoff. For utility_eta == 2.0, utility_cutoff linear units are equal in size to all utility above utility_cutoff.
        public double rebalance_band_hw = 0.0; // During validation and non-single step generation rebalance everything if an asset class is this far or greater from its target value.

        public double map_max_factor = 8; // Multiple of tp_max_estimate at which to generate maps.
                // Set high enough or get top left maximum return artifact.
        public double pf_fail = 0.0; // Stop the generation process early if we reach a guaranteed failed portfolio size.
                // For a contribution sequence other than contributions followed by withdrawals, or if we allow leverage, may need to allow a negative pf_fail value.
        public double retirement_number_max_factor = 10; // Generated retirement number up to this value times retirement_number_max_estimate portfolio size.
        public Double gnuplot_tp = null; // Maximum taxable portfolio value to plot.
        public Double gnuplot_consume = null; // Maximum consume value to plot.
        public Double gnuplot_annuitization = null; // Maximum annuuitization value to plot.
        public double gnuplot_extra = 1.05; // Headroom to leave on plots.
        public int gnuplot_steps = 600; // Number of steps at which to gnuplot data.

        public int distribution_steps = 100; // Number of bucket steps for probability distribution outputs.
        public double distribution_significant = 0.02; // Lowest relative probability density to map.

        // All max_path values must be equal to or below num_sequences_validate.
        public int max_jpmorgan_paths = 100000; // Maximum number of paths to use for the jpmorgan metric.
        public int max_distrib_paths = 10000; // Maximum number of paths to use for the probability distribution output files.
        public int max_pct_paths = 10000; // Maximum number of paths to use for the percentile output files.
        public int max_delta_paths = 100; // Maximum number of paths to use for the delta paths output files.
        public int max_display_paths = 10; // Maximum number of paths to use for the paths output file.

        public Double start_tp = 0.0; // Starting taxable investement portfolio size. Null if not a portfolio dimension.
        public Double start_ria = null; // Starting taxable real annuity annual payout size. Null if not a portfolio dimension.
        public Double start_nia = null; // Starting taxable nominal annuity annual payout size. Null if not a portfolio dimension.

        public Integer birth_year = null; // Year of birth of first person or null to non-deterministically base it on the current date and start_age.
        public int start_age = 25; // Generate data from this age on.
        public Integer start_age2 = 25; // Initial age of second person in a couple.
        public Integer validate_age = null; // Validate and target for this age of first person, start_age if null.
        public int retirement_age = 65; // Age at retirement of first person assuming both retire at same age.
        public Integer utility_age = null; // Age at which utility function specified (subsequent ages experience upside discounting), last possible age if null.
        public double[] cw_schedule = new double[0]; // Contribute / withdrawal schedule to use in addition to computed plans.
                // No utility is derived from cw_schedule withdrawals.  Array of numeric amounts for each time period, extended with zeros.
        public double accumulation_rate = 500; // Relative contribution rate. Initial rate of asset accumulation prior to retirement.
        public double accumulation_ramp = 1.07; // Annual ramping factor by which to boost accumulation rate over time.
        public Double withdrawal = null; // Annual retirement consumption amount (includes both defined benefits and investment portfolio).
        public double floor = 0.0; // Annual retirement floor consumption amount at below which portfolio failure is considered to have occured.
        public Double generate_ret_equity = null; // None for no adjustment to equities during generation, float for stocks target geomean return.
        public Double validate_ret_equity = null; // None for no adjustment to equities during targeting and validation, float for stocks target geomean return.
        public Double ret_equity_adjust = null; // None for no adjustment to equities, float for adjust.
        public double ret_sh_adjust = 0.0; // Small high asset class additional adjust.
        public double ret_tips_adjust = 0.0; // TIPS bond asset class additional adjustment.
        public double ret_tips_vol_adjust = 1.0; // Adjustment to apply to TIPS bond volatility.
        public double ret_gs10_to_bonds_arith = 0.0072; // Arithmetic adjustment to apply to GS10 to get bond returns indicative of the bond universe.
                // Justification:
                //
                // Considering the holdings of Treasury, Agency, Municipal, and Corporate bonds by households as reported in the Federal Reserve Financial Accounts
                // of the United States. Estimating the average maturity and rating of corporate bonds using the iShares LQD corporate bond index fund fact sheet.
                // Taking the BofA-Merrill option adjusted spreads reported by FRED. Down projecting these values to intermediate term corporate
                // bonds using the Treasury High Quality Markets average yield curve. Based on the rating distribution of municipal bonds seen on Yahoo's bond
                // screener equating municipal bonds to AA corporate bonds after any tax advantage has been factored in. Guessing at the real return on Agency
                // bonds as somewhere between that of Treasury and Municipal bonds. And adjusting the volatility to appear reasonable on a risk-return plot.
                //
                // BofA-Merrill option-adjusted spreads (1996-12-31 - 2015-03-18):
                //          average spread over Treasuries
                //     AAA              0.84%
                //     AA               1.06%
                //     A                1.41%
                //     BBB              2.10%
                //     BB               3.85%
                //     B                5.71%
                //     CCC and below   11.71%
                //
                // Downgrade correction:
                //
                //     Moody's reports a yield till maturity which does not include loss incurred when a bond is downgraded and has to be replaced.
                //     http://efinance.org.cn/cn/FEben/Corporate%20Default%20and%20Recovery%20Rates,1920-2010.pdf
                //
                //     One year upgrade/downgrade rates (1920-2010) (excluding transitions to withdrawn rating):
                //            To:   Aaa    Aa      A     Baa    Ba     B      Caa    Ca_C   weighted net migration loss (mig. rate x spread diff. x 8 yr LQD durat.)
                //           Aaa     -    8.21%  0.83%  0.16%  0.03%   0       0      0                     0.21%
                //     From: Aa    1.20%    -    7.24%  0.74%  0.17%  0.04%  0.01%  0.01%                   0.31%
                //           A     0.08%  2.92%    -    5.55%  0.68%  0.12%  0.03%  0.01%                   0.42%
                //           Baa   0.04%  0.29%  4.47%    -    5.00%  0.79%  0.13%  0.02%                   0.77%
                //
                //     One year credit loss rates due to default based on post default trading prices (1982-2010):
                //           credit loss   total annual losses    weight (LQD rating breakdown)
                //         Aaa  0.00%            0.21%                   2%
                //         Aa   0.01%            0.32%                  12%
                //         A    0.04%            0.46%                  51%
                //         Baa  0.12%            0.89%                  35%
                //         weighted average      0.43%
                //     NB: We don't currently adjust Aaa and Baa bond yield data series in AACalc for migration/default. Perhaps we should.
                //
                // Arithmetic mean return (GS10 + spread - total annual losses):
                //     GS10             2.42%
                //     AAA              3.05%
                //     AA               3.16%
                //     A                3.37%
                //     BBB              3.63%
                //
                // Fed. Flow of Funds:
                //
                // L.214 Mutual fund shares
                //   Household                          6692 58%
                //   Total                             11526
                //
                // 2013 Q4 L.100 Household  L.121 Mutual funds   Total      arithm. real return (1927-2013)
                //   Treasury            944             641     1316 17%       2.42% GS10
                //   Agency              121             837      607  8%      ~2.60% guess
                //   Muni               1617             610     1971 25%       3.16% after correct for tax adv; equiv to AA corporates
                //   Corp and foreign   2793            2001     3955 50%       3.46% 2/3 A and 1/3 BAA based on LQD
                //   Weighted                                                   3.14% use GS10 and adjust gm value by +0.72% to get 3.14% am
                //   Total                -              -       7849
        public double ret_gs10_to_bonds_vol_adjust = 1.1; // Adjustment to apply to GS10 volatility to get bond returns indicative of the bond universe.
                // A guess based on risk-return plots placing its risk close to but slightly less than AAA bonds, with which it shares a similar return.
                // If risk was higher than AAA bonds, no point in holding "bonds", ignoring different correlations.
                // Rough calc:
                // Vol(0.25 GS10 + 0.25 AAA-16yrs + 0.5 BBB-16yrs). Assume volatility differences can be summed. Not really true.
                // = 0.25 8.65% + 0.25 10.15%-1.05% + 0.5 12.20-1.05%. Because AAA reduces to GS10. Assume volatility additively reduces off BBB.
                // = 0.5 8.14% + 0.5 (9.10% + 2.05%).
                // = Vol(1.096 GS10).
        public Double generate_ret_bonds = null; // None for no adjustment to bonds during generation, float for target geomean return.
        public Double validate_ret_bonds = null; // None for no adjustment to bonds during targeting and validation, float for target geomean return.
        public Double ret_bonds_adjust = null; // None for no adjustment to fixed income, float for adjust.
        public Double ret_cash_arith = null; // None for no adjustment, or arithmetic mean to use for cash returns.
        public Double ret_equity_premium = null; // None for no adjustment, or arithmetic mean to use for excess of stock returns over cash returns.
        public double generate_all_adjust = 0.0;  // Adjust applied to all asset classes during generation.
        public double validate_all_adjust = 0.0;  // Adjust applied to all asset classes during targeting and validation.
        public Double generate_ret_inflation = null; // None for no adjustment to inflation during generation, float for geomean value.
        public Double validate_ret_inflation = null; // None for no adjustment to inflation during targeting and validation, float for geomean value.
        public double generate_equity_vol_adjust = 1.0;  // Adjust applied to volatility of equity asset classes during generation.
        public double validate_equity_vol_adjust = 1.0;  // Adjust applied to volatility of equity asset classes during targeting and validation.
        public double tax_rate_cg = 0.0; // Average tax rate for capital gains.
        public double[] tax_rate_div = null; // Average tax rate for dividends for each asset class. Null for defaults.
        public double tax_rate_div_default = 0.0; // Default tax rate for dividends.
        public double tax_rate_annuity = 0.0; // Average tax rate for annuities.
               // Annuity taxation is not reported in tax metric output (could probably modify to track and report if desired).
        public boolean tax_annuity_credit_expire = true; // Perform US rather than Canadian style annuity taxation.
              // Both allow a credit for the purchase price, but in law US style taxation provides a credit to the estate if you die before the IRS life expectancy
              // and revokes the credit after. Canadian style taxation simply allows an ongoing credit derived from the purchase price for as long as you are alive.
              // When generating we fail to consider the expiration of the tax credit (increasing the income expected from annuities and making them appear more
              // favorable). We include its expiration when simulating US style annuities.
              // We fail to apply a credit to the estate if die before reach IRS life expectancy.
        public String cost_basis_method = "immediate";  // Cost basis method for validation.  Immediate is used for generation.
               // "immediate", "avgcost", "hifo", or "fifo".
        public double tax_immediate_adjust = 0.8; // Immediate taxation isn't realistic. Multiplicative adjustment to tax rate when generating to make it more so.
               // Determined empirically to maximize hifo.
               //     1.00: stocks/bonds and an individual age 25 with an rcr of 0.05 growing 7% and taxes of div. (0.15, 0.20), cg 0.15, rbs 20.
               //     0.75: stocks/bonds and an individual age 25 with an rcr of 0.05 growing 7% and taxes of div. (0.15, 0.25), cg 0.15, rbs 1.
        public double[] dividend_fract = null; // Fraction of nominal gains for each asset class attributed to dividends. Null for defaults.
        public double dividend_fract_equity = 0.25; // Dividend fraction equity default.
        public double dividend_fract_fixed_income = 1.0; // Dividend fraction fixed income default.
        public double management_expense = 0.0; // Management fees adjustment for all asset classes except margin.
        public double margin_premium = 0.05; // Premium above current cash interest rate charged for margin borrowing.
        public String borrow_aa = "margin"; // Asset class to borrow against.
        public String borrow_only_aa = "margin"; // Don't allow positive investing in margin returns.
        public double max_borrow = 0.0; // Maximum amount borrowed relative to total net assets to provide leverage.  May be greater than 1.0.
        public String generate_shuffle = "none"; // How to shuffle the returns.
                // 'none' - The return sequence will be used exactly as received.
                // 'once' - A single shuffled set of returns will be used.
                // 'all' - The returns will be shuffled at each opportunity.
        public boolean ret_reshuffle = false; // Whether to re-shuffle for different asset allocation choices at the same asset allocation map location.
        public String generate_draw = "log_normal"; // How to shuffle the returns.
                // 'bootstrap' - Draw with replacement as ret_bootstrap_block_size length sequences.
                // 'shuffle' - Draw without replacement.
                // 'normal' - Draw from a normal distribution matching the return statistics. May produce values less than zero which would is catastrophic.
                //            Error in resulting geometric mean.
                // 'skew_normal' - Skew normal to prevent return values less than 0%. Resulting distribution no longer matches statistics.
                // 'log_normal' - Transform normal to a log normal distribution. Slight error in geometric mean and correlations.
        public Integer ret_resample = 1; // For distribution based draws whether and how to treat the underlying returns as a descriptive sample or population.
                // Treating as a sample means for each draw we generate a new sequence of returns from the underlying returns statistics every this many draws,
                // use its statistics as the population statistics, and from that produce the draw. This allows us to get a draw that is perpetually good
                // or bad, simulating that the underlying returns differed from their population.
                // Setting this to null means we produce the draw directly from the underlying return statistics.
                // Setting this to a value greater than 1, we find we need to increase num_sequences to get the same accuracy,
                // and cost of increasing num_sequences more than offsets the performance savings.
        public boolean ret_geomean_keep = true; // Whether to destroy arithmetic means and standard deviations in order to preserve geometric means when drawing.
        public int ret_geomean_keep_count = 20000; // Number of returns sequences to use to callibrate geometric mean preservation.
        public int ret_bootstrap_block_size = 20; // Size of blocks in years to use when drawing returns using bootstrap.
        public boolean ret_pair = true; // When shuffling whether to keep stock and bond returns for a given year together or treat them independently.
        public boolean ret_short_block = true; // Make return probabilities uniform by allowing short blocks.
                // Short blocks may be generated from the beginning and end of the original returns sequence, and for the initial block of the generated sequence.
        public int generate_start_year = 1927;
        public Integer generate_end_year = 2014; // None for until end of data.
        public String sex = "male"; // Death probabilities. 'male', 'female', or 'person'.
        public String sex2 = null; // Sex of seond person in a couple, or None for an individual.
        public boolean couple_unit = true; // Model a couple as a single unit.
        public double couple_weight1 = 0.5; // Weight placed on well-being of first individual relative to couple when not couple_unit.
        public double couple_annuity1 = 0.5; // Portion of annuities belonging to first individual when not couple_unit.
        public double couple_db = 0.5; // Portion of defined benefit income received when one member dead when not couple_unit.
        public double couple_consume = 0.7; // Fraction of consuption required when one member dead for same level of individual utility when not couple_unit.
        public String generate_life_table = "ssa-cohort"; // Life table to use for generation.
               // 'immortal', 'suicidal', 'gompertz-makeham', 'cdc-period', 'ssa-period',
               // 'iam2000-unloaded-period', 'iam2000-loaded-period', or 'iam2012-basic-period'.
        public String validate_life_table = "ssa-cohort"; // Life table to use for validation.
        public String annuity_table = "iam2012-basic-period"; // Life table to use for synthetic annuuity pricing.
        public String mortality_projection_method = "g2"; // Method to use to convert period life tables into cohort life tables.
               // "g2" - SOA Projection Scale G2.
               // "rate" - use mortality_reduction_rate.
        public double mortality_reduction_rate = 0.0; // Annual rate of mortality reduction for converting period life tables to cohort tables.
               // See http://www.ssa.gov/oact/NOTES/as120/LifeTables_Tbl_3.html and SoA projection scale G for choice of value; 0.01 is reasonable.
        public String annuity_mortality_experience = "aer2005_08-full"; // Actual/expected mortality experience to apply to annuity life tables.
               // "none" - No adjustment.
               // "aer2005_08-summary" - SOA 2005-08 Annuity Experience Report contract year length adjustment summary statistics
               // "aer2005_08-full" - SOA 2005-08 Annuity Experience Report contract year length adjustment age specific statistics
        // Moshe Milevsky style Gompertz-Makeham law: q = alpha + exp((y - m) / b) / b
        public double gompertz_alpha = 0.0; // Gompertz-Makeham mortality parameter.
        public double gompertz_m = 82.3; // Gompertz-Makeham mortality parameter.
        public double gompertz_b = 11.4; // Gompertz-Makeham mortality parameter.
        public double mortality_load = 0.0; // Loading to apply to mortality beyond that contained in table.
        public Integer years = null; // Years to run. Set to None to use the full death array length.

        public String target_mode = "rps"; // None not to perform targetting, 'rps' to target search over RPS, or 'rcr' to target search over RCR.
        public List<String> target_schemes = new ArrayList<String>(Arrays.asList("file"));
                // Asset allocation schemes to use in targetting. "sdp", "file" for validate=datafile, "fixed", "age_in_bonds", "age_minus_10_in_bonds", or "target_date".
        public boolean target_sdp_baseline = true; // Whether to use SDP or the target asset allocation scheme as the target for the other to target.
        public boolean target_rebalance = false; // True to perform target generation with no rebalancing band, so the impact of rebalancing can be seen.
        public String target_shuffle = "all";
        public String target_draw = "log_normal";
        public int target_start_year = 1927;
        public Integer target_end_year = 2014; // None for until end of data.
        public boolean target_short_block = true;

        public List<String> compare_aa = new ArrayList<String>(Arrays.asList("age_in_bonds", "age_minus_10_in_bonds", "target_date"));
                // Asset allocation schemes to use in comparing. "file" for validate=datafile, "fixed", "age_in_bonds", "age_minus_10_in_bonds", or "target_date".
        public List<String> compare_vw = new ArrayList<String>(Arrays.asList("retirement_amount"));
                // Variable withdrawal schemes to use in comparing.

        public boolean generate_interpolate = true; // Whether to interpolate lookups during generation.
               // Normally produces better results, but can cause unexpected negative infinity utility for a power utility with no floor.
        public boolean validate_interpolate = true; // Whether to interpolate lookups during validation.
               // Normally produces better results, but can cause unexpected negative infinity utility for a power utility with no floor.
        public String validate_shuffle = "all"; // How to shuffle the returns for a validation run.
        public String validate_draw = "log_normal";
        // Only bootstrap provides any momentum/reversion to the
        // mean. This is acceptable.
        //
        // Variance ratio tests and Pearson's r test show stock return
        // (after inflation) reversion to the mean does not currently
        // appear to be statistically significant, but if it does
        // occur it has a period of around 20 years. Papers looking
        // for mean reversion in stock prices are equivical.
        //
        // Variance ratio tests and Pearson's r test of gs10 returns
        // (after inflation) shows momentum with a period of 2-3
        // years, and for it to be strongly statistically significant,
        // but not quite significant if you shift everything backwards
        // 6 months. Appears to be a combination of distinct clusters
        // of values around different mean values for a given era
        // giving momentum overall but not within the era, and
        // Pearson's r statistic getting tricked by limited number of
        // distinct samples of mean value. Simulating different eras
        // would be difficult, so we assume all returns are from a
        // single era.
        public int validate_start_year = 1927;
        public Integer validate_end_year = 2014; // None for until end of data.

        public int generate_seed = 0; // Random seed used for generate shuffle.
        public int target_seed = 1; // Random seed used for target shuffle.
        public int validate_seed = 76254; // Random seed used for validation shuffle.
        public int vital_stats_seed = 3; // Random seed used for vital stats generation during validation when couple_unit=false.

        public int num_sequences_retirement_number = 20000; // Number of paths per location for retirement number.
        public int num_sequences_target = 20000; // Number of paths per targeting attempt.
        public Integer num_sequences_validate = 50000; // Number of paths for a validation run.
                // 20000 would be fine. The accuracy of the metric is then around 1%.
                // But since we have spent so much time generating a map we might spend a little extra evaluating it more accurately.
                // Not too much though, since we also use this value for any comparison runs, so we may run several times.

        public int path_metrics_bucket_size = 200; // How many paths to evaluate at once.
                // Smaller allows better computation of the standard deviation of success probabilities, but takes more time.
        public int returns_cache_size = 100; // How many buckets of path_metrics_bucket size returns sequences to pre-calculate.

        public boolean validate_dump = false; // Whether to dump paths and aa-linear for validation runs.

        // Static values that can't be changed from run to run.
        public static String data_source = "shiller"; // 'sbbi' or 'shiller'.

        /**
         * Return all the fields/values as a Map
         * 
         * @return
         */
        private Map<String, Object> getAsMap()
        {
                Map<String, Object> params = new TreeMap<String, Object>();
                for (Field f : this.getClass().getDeclaredFields())
                {
                        try
                        {
                                params.put(f.getName(), f.get(this));
                        }
                        catch (IllegalArgumentException e)
                        {
                                e.printStackTrace();
                        }
                        catch (IllegalAccessException e)
                        {
                                e.printStackTrace();
                        }
                }
                return params;
        }

        public void load_params(Map<String, Object> params, String in)
        {
                String[] lines = in.split(System.getProperty("line.separator"));
                for (String line : lines)
                {
                        int comment_pos = line.indexOf("#");
                        if (comment_pos != -1)
                                line = line.substring(0, comment_pos);
                        line = line.trim(); // Handle empty lines containing whitespace.
                        String[] split_line = line.split("=");
                        if (split_line.length == 0 || (split_line.length == 1 && split_line[0].equals("")))
                                continue;

                        String var = split_line[0];
                        String val = split_line[1];
                        var = var.trim();
                        val = val.trim();
                        params.put(var, convertObjectFor(var, val));
                }
        }

        /**
         * Apply the parameters from the Map to the internal parameters
         * 
         * @param params
         */
        public void applyParams(Map<String, Object> params)
        {
                for (String field : params.keySet())
                {
                        try
                        {
                                Field f = this.getClass().getDeclaredField(field);
                                f.set(this, params.get(field));
                        }
                        catch (NoSuchFieldException e)
                        {
                                throw new IllegalArgumentException("Invalid field " + field);
                        }
                        catch (IllegalAccessException e)
                        {
                                throw new IllegalArgumentException("Illegal access field " + field);
                        }
                }
        }

        /**
         * Dump all the parameters to the output
         */
        public void dumpParams()
        {
                Map<String, Object> params = getAsMap();
                for (String key : params.keySet())
                {
                        Object param = params.get(key);
                        String sparam;
                        if (param instanceof double[])
                        {
                                double[] da = (double[]) param;
                                sparam = "[";
                                boolean first = true;
                                for (double d : da)
                                {
                                        if (first)
                                                first = false;
                                        else
                                                sparam += ",";
                                        sparam += String.valueOf(d);
                                }
                                sparam += "]";
                        }
                        else
                                sparam = String.valueOf(param);
                        System.out.println("   " + key + " = " + sparam);
                }
        }

        /**
         * Convert the string raw parameter to an object compatible with the specified field
         * 
         * @param field
         * @param raw
         * @return
         */
        @SuppressWarnings("rawtypes")
        private Object convertObjectFor(String field, String raw)
        {
                Field f;
                try
                {
                        f = this.getClass().getDeclaredField(field);
                }
                catch (Exception e)
                {
                        throw new IllegalArgumentException("No such field " + field);
                }
                try
                {
                        Class type = f.getType();
                        return convertObject(type, raw);
                }
                catch (Exception e)
                {
                        throw new IllegalArgumentException("Value " + raw + " is not valid for the field " + field);
                }
        }

        /**
         * Convert the string raw parameter to an object of the specified class
         * 
         * @param type
         * @param raw
         * @return
         */
        @SuppressWarnings("rawtypes")
        private Object convertObject(Class type, String raw)
        {
                raw = raw.trim();
                
                if ("none".equalsIgnoreCase(raw) || "null".equalsIgnoreCase(raw))
                        return null;

                if (type == String.class)
                {
                        if (raw.startsWith("\"") && raw.endsWith("\""))
                                raw = raw.substring(1, raw.length() - 1);
                        else if (raw.startsWith("\'") && raw.endsWith("\'"))
                                raw = raw.substring(1, raw.length() - 1);
                        else
                                throw new IllegalArgumentException("Unquoted string value");
                        return raw;
                }
                else if (type == boolean.class)
                        return "true".equals(raw.toLowerCase()) || "1".equals(raw);
                else if (type == int.class || type == Integer.class)
                        return Integer.parseInt(raw);
                else if (type == double.class || type == Double.class)
                        return Double.parseDouble(raw);
                else if (type == List.class)
                {
                        String slist = raw.substring(1, raw.length() - 1);
                        String sa[] = slist.split(",");
                        List<String> data = new ArrayList<String>();
                        if (sa.length > 1 || sa[0].trim().length() > 0)
                        {
                                for (String s : sa)
                                {
                                        data.add((String) convertObject(String.class, s));
                                }
                        }
                        return data;
                }
                else if (type == double[].class)
                {
                        String slist = raw.substring(1, raw.length() - 1);
                        String sa[] = slist.split(",");
                        double[] data;
                        if (sa.length > 1 || sa[0].trim().length() > 0)
                        {
                                data = new double[sa.length];
                                int idx = 0;
                                for (String s : sa)
                                {
                                        data[idx++] = (Double) convertObject(double.class, s);
                                }
                        }
                        else
                        {
                                data = new double[0];
                        }
                        return data;
                }
                else
                        return null;
        }
}
