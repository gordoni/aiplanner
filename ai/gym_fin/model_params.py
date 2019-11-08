# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import isnan

class ModelParams(object):

    def __init__(self):

        self.param_names = []

    def add_arguments(self, parser, training = True, evaluate = True):

        self.parser = parser

        self._add_arguments()
        if training:
            self._add_arguments(training = True)
        if evaluate:
            self._add_arguments(evaluate = True)

    def _add_arguments(self, training = False, evaluate = False):

        assert not (training and evaluate)

        self.training = training
        self.evaluate = evaluate

        string_type = None

        self._param('name', 'AIPlanner', tp = string_type) # Descriptive name of this parameter set.

        self._boolean_flag('verbose', False) # Display relevant model information such as when stepping.
        self._boolean_flag('warn', True) # Display warning messages.
        self._boolean_flag('display-returns', True) # Display yield and return statistics.

        self._param('debug-dummy-float', None) # Occasionally useful for debugging.

        # This following four parameters are determined by the training algorithm, and can't be set by the user.
        self._boolean_flag('action-space-unbounded', None) # Whether the action space is unbounded, or bound to the range [-1, 1].
        self._boolean_flag('observation-space-ignores-range', None) # Whether observation space needs to roughly be in the range [-1, 1], or the range specified.
        self._boolean_flag('observation-space-clip', None) # Whether observation space should be clipped to stay in range, or can occasionally be out of range.
        self._param('algorithm', None, tp = string_type) # For RLlib only, the training algorithm being used.

        self._param('reproduce-episode', None, tp = int) # If set, keep reproducing the same numbered episode returns. Useful for benchmarking.

        self._param('consume-policy', 'rl', tp = string_type,
            choices = ('rl', 'constant', 'guyton_rule2', 'guyton_klinger', 'target_percentage', 'extended_rmd', 'pmt'))
            # Consumption policy.
            # "rl": reinforcement learning.
            # "constant": constant fixed amount consume_initial.
            # "guyton_rule2": initially consume_initial,
            #     then no investment portfolio withdrawal inflation adjustment for period following period with a negative nominal market return.
            # "guyton_klinger": initially consume_initial, then increase investment consumption by 10% if below 80% of initial consumption rate,
            #     decrease nominal investment consumption by 10% if above 120% of the initial consumption rate and remaining life expectancy exceeds
            #     15 years based upon consume_policy_life_expectancy, no inflation investment withdrawal inflation adjustment for period following period
            #     with a negative nominal market return and the investment consumption rate exceeds the initial consumption rate.
            # "target_percentage": initially consume_initial, then no investment portfolio withdrawal inflation adjustment for periods where investment
            #     portfolio is below expected value based upon consume_policy_life_expectancy and consume_policy_annual_return.
            # "extended_rmd": consume according to IRS Required Minimum Distribution table extended to start from age 50.
            # "pmt": payout with life expectancy consume_policy_life_expectancy and return amount consume_policy_return.
        self._param('consume-initial', 0) # Initial consumption amount for particular consumption policies.
        self._param('consume-policy-life-expectancy', None) # Assumed life expectancy for particular consumption policies, or None to use actual life expectancy.
        self._param('consume-policy-return', 0) # Assumed annual return for particular consumption policies.
        self._param('annuitization-policy', 'rl', tp = string_type, choices = ('rl', 'age_real', 'age_nominal', 'none'))
            # Annuitization policy.
            # "rl": reinforcement learning.
            # "age_real": fully annuitize using real SPIAs starting at annuitization_policy_age.
            # "age_nominal": fully annuitize using nominal SPIAs starting at annuitization_policy_age.
            # 'none': no SPIA purchases.
        self._param('annuitization-policy-age', 0) # Age (of youngest party) at which to switch from no annuitization to fully annuitized.
        self._param('asset-allocation-policy', 'rl', tp = string_type)
            # Asset allocation policy.
            # "rl": reinforcement learning.
            # "age-in-nominal-bonds": age in years as nominal bonds percentage, remainder in stocks.
            # '{"<asset_class>":<allocation>, ...}': fixed allocation. Eg. '{"stocks":0.5, "nominal_bonds":0.5}'.
        self._param('rl-consume-bias', 0.0, 0.0) # Bias the reinforcement learning conumption policy consumption fraction by this amount.
            # Useful for reversing the effects of training algorithm bias when evaluating.
            # Training bias should always be zero.
        self._param('rl-stocks-bias', 0.0, 0.0) # Bias the reinforcement learning asset allocation policy allocation to stocks by this amount.
            # Useful for reversing the effects of training algorithm bias when evaluating.
            # Training bias should always be zero.
        # Bonds duration policy.
        # Defined by "real-bonds-duration" and "nominal-bonds-duration" below; None for reinforcement learning, or a fixed age in years.

        self._param('observation-space-warn', 1.0) # Warn when observation outside this factor of the expected range.
        self._param('consume-floor', 0) # Minimum expected consumption level model is trained for.
        self._param('consume-ceiling', float('inf')) # Maximum expected consumption level model is trained for.
        #self._param('consume-utility-floor', 10000) # Scale utility to have a value of -1 for this consumption amount.
            # Utility needs to be scaled to prevent floating point overflow.
        self._param('reward-warn', 2e3, 1e1) # Warn reward values not lying within [-reward_warn, reward_warn].
            # During training poor rewards are expected to be generated.
        self._param('reward-clip', 1e15, float('inf')) # Clip reward values to lie within [-reward_clip, reward_clip].
            # Evaluation clip should always be inf.
            #
            # PPO set training clip of 1e15 is to prevent floating point overflow computing global_norm, which can cause training to fail with a tensorflow error.
            # Setting a bound, such as 50, appears to produces worse CEs for Merton's portfolio problem, but has little effect when guaranteed income is present.
            #
            # In DDPG probably always need a low training clip value such as 10 on account of poor step choices getting saved and reused by the replay buffer.
            #
            # In DDPG could also try "--popart --normalize-returns" (see setup_popart() in ddpg/ddpg.py).
            # Need to first fix a bug in ddpg/models.py: set name='output' in final critic tf.layers.dense().
            # But doesn't appear to work well becasuse in the absense of guaranteed income the rewards may span a large many orders of magnitude range.
            # In particular some rewards can be -inf, or close there to, which appears to swamp the Pop-Art scaling of the other rewards.
        #self._param('reward-zero-point-factor', 0.5) # Scale utility of [reward_zero_point_factor * expected consume, expected consume] onto rewards [0, 1].
            # Utility needs to possibly be roughly scaled to an average absolute value of 1 for DDPG implementation (presumably due to optimizer step size).
            # For PPO1 value will matter in ensuring equal optimization weight is placed on different episodes when gamma is variable.
            # For PPO1 increasing this value is associated with an increase in the standard deviation of measured CEs across models.
            # Rllib PPO takes rewards_to_go / 10 batches to converge the value function.
        self._boolean_flag('couple-hide', False)
            # Whether to hide observation of couple specific values.
            # When hidden a couple appears like a single individual. This allows use of a single trained model for evaluation of a couple.
            # A couple trained model may be less accurate due to the large stochasticity associated with the random death of the first member of the couple.

        self._param('life-table', 'ssa-cohort', tp = string_type) # Life expectancy table to use. See spia module for possible values.
        self._param('life-table-date', '2020-01-01', tp = string_type) # Used to determine birth cohort for cohort based life expectancy tables.
        self._param('life-expectancy-additional', (0, 0), 0) # Initial age adjustment for first individual.
            # Shift initial age so as to add this many years to the life expectancy of the first individual.
        self._param('life-expectancy-additional2', (0, 0), 0) # Initial age adjustment for second individual.
        self._param('life-table-spia', 'iam2012-basic', tp = string_type) # Life expectancy table to use for pricing spia purchases.
        self._param('couple-probability', 0) # Probability family unit is a couple, not single.
            # Fractional values only make sense during training.
        self._param('sex', 'female', tp = string_type, choices = ('male', 'female')) # Sex of first individual. Helps determine life expectancy table.
        self._param('sex2', 'male', tp = string_type, choices = ('male', 'female')) # Sex of second individual, if any.
        self._param('age-start', 67, 67) # Age of first individual.
        self._param('age-start2', (67, 67), 67) # Age of second individual.
        self._param('age-end', 151) # Model done when individuals reach this age.
            # Life table ends at 121. Specifying a larger value ensures no truncation of the life table occurs when life_expectancy_additional is specified.
        self._param('age-retirement', (67, 67), 67) # Assess and optimize consumption from when first individual reaches this age.
        self._param('consume-additional', 0.6)
            # When a second individual is present we consume this fraction more than a single individual for the same per individual utility.
        self._param('couple-death-preretirement-consume', 'consume_additional', tp = string_type, choices = ('consume_additional', 'pro_rata', 'none'))
            # How to adjust preretirement consumption in the event of the death of one member of a couple.
            # "consume_additional": reduce so that the original consumption level is consume_additional greater than the new consumption level.
            # "pro_rata": reduce proportionately to the initial pre-retirement income of each member.
            # "none": no change in consumption.
        self._boolean_flag('probabilistic-life-expectancy', True)
            # This flag is useful for debugging.
            # Whether to the extent possible to simulate life expectancy probabilistically, or whether to use random roll outs.
            # For a couple, the first to die always uses random rollouts.
        self._boolean_flag('couple-death-concordant', False) # Whether second member of couple dies at the same time as first.
            # This flag may be used to assess the modeling performance differential between a couple and two individuals.
            # When doing so it is important that consume_additiional=1, income-concordant is specified, both members have the same sex, age, and defined benefits,
            # and the assets and consume_preretirement are doubled.

        self._param('income-preretirement', (0, 0), 0) # Annual pre-tax pre-retirement income for first individual.
        self._param('income-preretirement2', (0, 0), 0) # Annual pre-tax pre-retirement income for second individual.
        self._param('income-preretirement-age-end', None)
            # Age of first individual when pre-retirement income ends, or None to base on first individual reaching age_retirement.
        self._param('income-preretirement-age-end2', None)
            # Age of second individual when pre-retirement income ends, or None to base on first individual reaching age_retirement.
        self._param('income-preretirement-mu', 0) # Pre-retirement income annual drift for first individual.
        self._param('income-preretirement-mu2', 0) # Pre-retirement income annual drift for second individual.
        self._param('income-preretirement-sigma', 0) # Pre-retirement income annual log volatility for first individual.
        self._param('income-preretirement-sigma2', 0) # Pre-retirement income annual log volatility for second individual.
        self._boolean_flag('income-preretirement-concordant', False) # Whether second member of couple's income follows the same fluctuations as the first.
        self._boolean_flag('income-preretirement-taxable', True) # Whether pre-tax pre-retirement income is taxable.
        self._param('consume-preretirement', 0) # Annual pre-retirement consumption.
        self._param('consume-preretirement-income-ratio', (0, 0)) # Fraction of initial pre-retirement income to add to pre-retirement consumption.

        self._param('have-401k', (True, True), True, tp = bool) # 401(k) available to first individual.
        self._param('have-401k2', (True, True), True, tp = bool) # 401(k) available to second individual.

        self._param('time-period', 1) # Rebalancing time interval in years.
        self._param('gamma', (3, 3), 3) # Coefficient of relative risk aversion.
            # Will probably need smaller [consume_floor, consume_ceiling] ranges if use a large gamma value such as 6.

        self._param('gi-fraction', (0, 1), (0, 1)) # Allowed values of guaranteed income as a fraction of total wealth.
        self._param('guaranteed-income', '[{"payout": [1e3, 1e5]}]', '[]', tp = string_type)
            # Guaranteed income and expenses represented as a JSON array of objects. Object fields:
            #     "type": Type of defined benefit or expense. Arbitrary string. Default "income_annuity".
            #         A value of "social_security" is taxed specially.
            #     "owner": Value "self" or "spouse". Default "self".
            #     "start": Starting age in years of owner for benefit. Default of null starts when first individual reaches age_retirement.
            #     "end": Exclusive ending age in years of owner for benfit. Default of null for no end.
            #     "probability": Probability of this defined benefit being present. Used when generating different random scenarios. Default 1.
            #     "payout": Annual guaranteed income payout amount in today's dollars. Negative for expenses.
            #         May be a array of length 2 for stochastic log range. Required.
            #     "inflation_adjustment": Annual inflation increase fraction from today, or "cpi" for adjustment to reflect the CPI value. Default "cpi".
            #     "joint": true if payout drops on death of either self or spouse, false if value payout drops only on death of owner. Default false.
            #     "payout_fraction": payout fraction when joint contingency occurs. Zero specifies a single annuity with no joint contingency. Default 0.
            #     "source_of_funds": "taxable", "tax_deferred", or "tax_free". Tax treatment of benefit or expense. Default "tax_deferred".
            #         Regular expenses should be "tax_free". A tax deductable expense can be either "tax_deferred" or "taxable".
            #     "exclusion_period": If taxable, tax exclusion period in years from starting age. Default 0.
            #     "exclusion_amount": If taxable, annual tax exclusion amount of payout in today's dollars. Not adjusted for inflation. Default 0.
        self._param('guaranteed-income-additional', '[]', tp = string_type) # Additional defined benefits.
        self._param('p-weighted', (1e4, 1e7), 0) # Total investment portfolio size excluding additive specific amounts.
        self._param('p-tax-free', (0, 0), 0) # Non-taxable additive portfolio size. Roth IRAs and similar.
        self._param('p-tax-free-weight', (0, 100), 0) # Weight for p_weighted allocated to non-taxable.
        self._param('p-tax-deferred', (0, 0), 0) # Tax deferred additive portfolio size. Traditional IRAs and similar.
        self._param('p-tax-deferred-weight', (1, 100), 0) # Weight for p_weighted allocated to tax deferred. (Weight low of 1 to avoid all weights zero).
        self._param('p-taxable-stocks', (0, 0), 0) # Taxable additive portfolio stocks.
        self._param('p-taxable-stocks-weight', (0, 100), 0) # Weight for p_weighted allocated to taxable stocks.
        self._param('p-taxable-real-bonds', (0, 0), 0) # Taxable additive portfolio real bonds.
        self._param('p-taxable-real-bonds-weight', (0, 100), 0) # Weight for p_weighted allocated to taxable real bonds.
        self._param('p-taxable-nominal-bonds', (0, 0), 0) # Taxable additive portfolio nominal bonds.
        self._param('p-taxable-nominal-bonds-weight', (0, 100), 0) # Weight for p_weighted allocated to taxable nominal bonds.
        self._param('p-taxable-iid-bonds', (0, 0), 0) # Taxable additive portfolio iid bonds.
        self._param('p-taxable-iid-bonds-weight', (0, 100), 0) # Weight for p_weighted allocated to taxable iid bonds.
        self._param('p-taxable-bills', (0, 0), 0) # Taxable additive portfolio bills.
        self._param('p-taxable-bills-weight', (0, 100), 0) # Weight for p_weighted allocated to taxable bills.
        self._param('p-taxable-stocks-basis', 0) # Taxable portfolio stocks cost basis.
        self._param('p-taxable-real-bonds-basis', 0) # Taxable portfolio real bonds cost basis.
        self._param('p-taxable-nominal-bonds-basis', 0) # Taxable portfolio nominal bonds cost basis.
        self._param('p-taxable-iid-bonds-basis', 0) # Taxable portfolio iid bonds cost basis.
        self._param('p-taxable-bills-basis', 0) # Taxable portfolio bills cost basis.
        self._param('p-taxable-stocks-basis-fraction', (0, 2), 1) # Taxable portfolio stocks cost basis as a fraction of stocks value.
        self._param('p-taxable-real-bonds-basis-fraction', (0.7, 1.1), 1) # Taxable portfolio real bonds cost basis as a fraction of real bonds value.
        self._param('p-taxable-nominal-bonds-basis-fraction', (0.7, 1.1), 1) # Taxable portfolio nominal bonds cost basis as a fraction of nominal bonds value.
        self._param('p-taxable-iid-bonds-basis-fraction', (0.7, 1.1), 1) # Taxable portfolio iid bonds cost basis as a fraction of iid bonds value.
        self._param('p-taxable-bills-basis-fraction', (0.7, 1.1), 1) # Taxable portfolio bills cost basis as a fraction of bills value.
        # Consumption order is assumed to be p_taxable, p_tax_deferred, p_notax.

        self._boolean_flag('tax', False) # Whether income is taxed.
        self._boolean_flag('income-aggregate', True) # When income isn't taxed, whether to aggregate tax_free, tax_deferred, and taxable observations.
        self._param('tax-table-year', None, tp = string_type) # Tax table to use, or use latest tax table if None.
        self._param('dividend-yield-stocks', 0.02) # Dividend yield for stocks.
        self._param('dividend-yield-bonds', 0.04) # Dividend yield for bonds and bills.
        self._param('qualified-dividends-stocks', 1) # Qualified dividends fraction for stocks. Qualified dividends are taxed at capital gains rates.
        self._param('qualified-dividends-bonds', 0) # Qualified dividends fraction for bonds and bills.
        self._param('tax-state', 0.06) # Aggregate state, local, and property taxes as a percentage of income after standard deduction.
            # Average state and local income tax rate is around 3%, and average state property tax is around 3% of income.

        self._boolean_flag('static-bonds', False)
            # Whether to model real bonds and inflation and thus nominal bonds and SPIAs as static (that is using a yield curve that does not vary over time).
            # Does not remove side-effects of potential for temporal variability in bond prices; simply does not step bonds over time.
        self._param('fixed-real-bonds-rate', None) # Rate to model real bonds with a fixed mean yield curve (does not favor duration).
        self._param('fixed-nominal-bonds-rate', None) # Rate to model nominal bonds in determining inflation with a fixed mean yield curve (does not favor duration).
        self._param('bonds-date', '2018-12-31', tp = string_type) # Date to use for typical bond yield curve if not fixed.
        self._param('bonds-date-start', None, tp = string_type) # Optional date to use for start of date range for average typical bond yield curve if not fixed.

        self._boolean_flag('real-spias', False) # Enable purchase of real SPIAs.
        self._param('real-spias-mwr', 0.94) # Money's Worth Ratio for real SPIAs (after any guarantee association tax).
            # When I priced real SPIAs against the IAM 2012 life table with actual/expected adjustemets and Treasury TIPS in 2015,
            # Money's Worth Ratios from Principal Financial Group were around 96.5%. Factor in a 2.35% CA guarantee association tax,
            # and a 94% MWR seems reasonable.
        self._boolean_flag('nominal-spias', False) # Enable purchase of nominal SPIAs.
        self._param('nominal-spias-mwr', 1.0) # Money's Worth Ratio for nominal SPIAs (after any guarantee association tax).
            # When I priced nominal SPIAs against the IAM 2012 life table with actual/expected adjustments in 2015,
            # the best Money's Worth Ratios were around 105-110%. This is possible because nominal SPIAs are probably primarily
            # priced against not the Tresury yield curve, but the higher yielding High Quality Markets corporate bond curve.
            # There is no such thing as a free lunch; a MWR abve 100% implies the issuers and thus the annuitants are taking on default risk.
            # To crudely reflect this, we don't use MWRs above 100%, and the 2.35% CA guarantee association tax is ignored since the premium
            # goes towards covering defaults.
        self._param('nominal-spias-adjust', 0) # Fixed annual adjustment to apply to nominal SPIAs payout to compensate for inflation.
        self._boolean_flag('spias-partial', True) # Whether to allow partial annuitization.
        self._param('spias-min-purchase-fraction', 0) # Minimum fraction of total estimated annual income making up a SPIAs purchase.
        self._boolean_flag('preretirement-spias', True) # Enable purchase of DIAs preretirement.
        self._boolean_flag('couple-spias', True) # Enable purchase of SPIAs by couples.
        self._param('spias-permitted-from-age', 0) # Minimum age (of youngest party) at which able to purchase SPIAs.
        self._param('spias-permitted-to-age', 90) # Maximum age (of oldest party) at which able to purchase SPIAs.
        self._param('spias-from-age', 200)
            # Minimum age (of oldest party) from which must be fully annuitize even if no couple_spias provided age permitted and meets minimum purchase fraction.

        # Market parameters are based on World and U.S. averages from the Credit Suisse Global Investment Returns Yearbook 2019 for 1900-2018.
            # For equities the reported real return is 6.5% +/- 17.4%, standard error 1.6% (geometric 5.0%).
            # For nominal government bonds the reported real return is 2.5% +/- 11.0%, standard error 1.0% (geometric 1.9%).
            # For U.S. Treasury bills the reported real return is 0.9% +/- 4.6%, standard error 0.4% (geometric 0.8%) [from 2017 Yearbook].
            # The reported U.S. inflation rate is 3.0% +/- 4.7%, standard error 0.4% (geometric 2.9%) [from 2017 Yearbook].
        self._boolean_flag('returns-standard-error', True) # Whether to model the standard error of returns.
        self._boolean_flag('stocks', True) # Whether to model stocks.
        self._param('stocks-model', 'bootstrap', tp = string_type, choices = ('normal_residuals', 'bootstrap', 'iid')) # Stock model to use.
            # normal_residuals - normal residuals applied to a monthly GJR-GARCH volatility model.
            # bootstrap - bootrapped residuals applied to a monthly GJR-GARCH volatility model.
            # iid - geometric Brownian motion.
        self._param('stocks-bootstrap-years', 0) # Mean bootstrap residual block size in years for bootstrap stocks.
            # A value of zero results in residuals being drawn at random.
            # A value other than zero may result in unwanted corelations between volatility and next period return depending on the bootstrap data used.
        self._param('stocks-sigma-max', 1.0) # Maximum allowed annual volatility for normal_residuals/bootstrap stocks.
            # Without a maximum, the bootstrap GJR-GARCH volatility model can produce anualized volatilities as high as 15.0, which is unrealistic.
        self._param('stocks-mu', 0.065) # Annual real log return for normal_residuals/bootstrap stocks.
            # Yields 6.5% return for bootstrap stocks in absense of returns_standard_error.
        self._param('stocks-sigma', 0.162) # Annual real log volatility for normal_residuals/bootstrap stocks.
            # Yields 17.4% volatility for bootstrap stocks in absense of returns_standard_error.
        self._param('stocks-alpha', 0.0000) # Monthly GJR-GARCH volatility model alpha parameter for normal_residuals/bootstrap stocks.
        self._param('stocks-gamma', 0.3188) # Monthly GJR-GARCH volatility model gamma parameter for normal_residuals/bootstrap stocks.
        self._param('stocks-beta', 0.7116) # Monthly GJR-GARCH volatility model beta parameter for normal_residuals/bootstrap stocks.
        self._param('stocks-sigma-level-type', 'sample', 'invalid', tp = string_type, choices = ('sample', 'average', 'value'))
            # Monthly GJR-GARCH volatility model current log volatility relative to long term average for normal_residuals/bootstrap stocks.
            # 'sample' chooses initial value at random, 'average' uses the average model value, 'value' uses a specific value.
        self._param('stocks-sigma-level-value', None) # Monthly GJR-GARCH volatility model current log volatility relative to long term average for type 'value'.
        self._param('stocks-mean-reversion-rate', 0.1) # Mean reversion rate for normal_residuals/bootstrap stocks, - d(return percentage)/d(overvalued percentage).
            # Set to non-zero for mean reverting stock returns.
            # Use a value like 0.1 to mimick findings from Shiller's data, that for every 10% overvalued stocks are,
            # there is an approximate 1% reduction in annual returns for the following year.
        self._param('stocks-price-exaggeration', 0.7) # Over-exuberance/pessimism factor for normal_residuals/boostrap stocks with mean reversion:
           #     1 - d(fair price)/d(price).
           # Extent to which movement in stock price doesn't reflect movement in fair price.
           # Used to mimick implications from Shiller's data that stocks can be over/under-valued.
           # A value of 0.7 produces a value/fair value of 60-150% the vast majority of the time.
        self._param('stocks-price', (0.5, 2.0), (None, None)) # Initial observed price of stocks relative to fair price for bootstrap stocks with mean reversion.
        self._param('stocks-price-noise-sigma', 0.2) # Sigma of lognormal noise inherent in observation of stocks price relative to fair price for bootstrap stocks.
            # Used in the case of mean reversion.
        self._param('stocks-return', 0.065) # Annual real return for iid stocks.
        self._param('stocks-volatility', 0.174) # Annual real volatility for iid stocks.
        self._param('stocks-standard-error', 0.016) # Standard error of log real return for stocks.
        self._boolean_flag('real-bonds', True) # Whether to model real bonds (with an interest rate model).
        self._param('real-bonds-duration', None) # Duration in years to use for real bonds, or None to allow duration to vary.
        self._param('real-bonds-duration-max', 30) # Maximum allowed real duration to use when duration is allowed to vary.
        self._boolean_flag('real-bonds-duration-action-force', False) # Whether to employ a real bond model that has variable duration with a fixed duration.
        self._boolean_flag('nominal-bonds', True) # Whether to model nominal bonds (with an interest rate model).
        self._param('nominal-bonds-duration', None) # Duration in years to use for nominal bonds, or None to allow duration to vary.
        self._param('nominal-bonds-duration-max', 30) # Maximum allowed nominal duration to use when duration is allowed to vary.
        self._boolean_flag('nominal-bonds-duration-action-force', False) # Whether to employ a real bond model that has variable duration with a fixed duration.
        self._boolean_flag('iid-bonds', False) # Whether to model independent identically distributed bonds (without any interest rate model).
        self._param('iid-bonds-type', None, tp = string_type, choices = ('real', 'nominal', None))
            # Derive iid bond returns from the specified bond model, or None if iid bond returns are lognormally distributed.
        self._param('iid-bonds-duration', 15) # Duration to use when deriving iid bond returns from the bond model.
        self._param('iid-bonds-return', 0.025) # Annual real return for iid bonds when lognormal.
        self._param('iid-bonds-volatility', 0.110) # Annual real volatility for iid bonds when lognormal.
        self._param('bonds-standard-error', 0.010) # Standard error of log real return for bonds.
        self._param('real-short-rate-type', 'sample', 'invalid', tp = string_type, choices = ('sample', 'current', 'value'))
            # Initial short real interest rate when using model.
            # 'sample' chooses initial value at random, 'current' uses the average model value, 'value' uses a specific value.
        self._param('real-short-rate-value', None) # Initial continuously compounded annualized short real interest rate for type 'value'.
        self._param('inflation-standard-error', 0.004) # Standard error of log inflation.
        self._param('inflation-short-rate-type', 'sample','invalid', tp = string_type, choices = ('sample', 'current', 'value'))
            # Initial inflation rate when using model.
            # 'sample' chooses initial value at random, 'current' uses the average model value, 'value' uses a specific value.
        self._param('inflation-short-rate-value', None) # Initial continuously compounded annualized inflation rate for type 'value'.
        self._boolean_flag('bills', True) # Whether to model stochastic bills (without any interest rate model).
        self._param('bills-return', 0.009) # Annual real return for bill asset class.
        self._param('bills-volatility', 0.046) # Annual real return for bill asset class.
        self._param('bills-standard-error', 0.004) # Standard error of log real return for bills.
        self._param('credit-rate', 0.15) # Annual real interest rate for borrowing cash.

        self._boolean_flag('observe-stocks-price', True) # Whether to observe stocks price relative to fair price pus noise.
        self._boolean_flag('observe-stocks-volatility', True) # Whether to observe bootstrap stocks volatility.
        self._boolean_flag('observe-interest-rate', True) # Whether model reveals the short real interest rate to observers.

    def set_params(self, dict_args):

        self.params = {}
        for param, value in dict_args.items():
            try:
                if isnan(value):
                    value = None
            except TypeError:
                pass
            finally:
                self.params[param] = value

    def get_params(self, training = False):

        def get_param(name):
            if self.params['master_' + name] != None:
                return self.params['master_' + name]
            elif training:
                return self.params['train_' + name]
            else:
                return self.params['eval_' + name]

        params = {}
        for name in self.param_names:
            if not name in params and not name + '_low' in self.param_names:
                params[name] = get_param(name)
            if name.endswith('_low'):
                base = name[:-4]
                if get_param(base) == None:
                    low = get_param(base + '_low')
                    high = get_param(base + '_high')
                    assert low == high or low < high, 'Bad range: ' + base # Handles low == high == None.
                else:
                    params[base + '_low'] = params[base + '_high'] = get_param(base)

        return params

    def remaining_params(self):

        params = dict(self.params)
        del params['config_file']

        for param in self.param_names:
            del params['master_' + param]
            try:
                del params['train_' + param]
            except KeyError:
                pass
            try:
                del params['eval_' + param]
            except KeyError:
                pass

        return params

    def _param(self, name, train_val, eval_val = None, *, tp = float, choices = None):
        '''Add parameter name to the model parameters.

        Uses the specified values as the default training and evaluation values.
        If eval_val is None, use train_val as the default evaluation value.

        Values may be a tuple to specify a range of values: (low, high).'''

        if tp in (float, int, bool):

            try:
                _, _ = train_val
            except TypeError:
                train_range = False
            else:
                train_range = True

            try:
                _, _ = eval_val
            except TypeError:
                eval_range = False
            else:
                eval_range = True

        else:

            train_range = False
            eval_range = False

        if train_range and not eval_range and eval_val != None:
            eval_val = (eval_val, eval_val)
        if eval_range and not train_range:
            train_val = (train_val, train_val)
        rnge = train_range or eval_range

        if self.training:
            val = train_val
            prefix = '--train-'
        elif self.evaluate:
            val = eval_val if eval_val != None else train_val
            prefix = '--eval-'
        else:
            if rnge:
                val = (None, None)
            else:
                val = None
            prefix = '--master-'

        under_name = name.replace('-', '_')
        if rnge:
            if self.parser:
                self.parser.add_argument(prefix + name, type = tp, default = None, choices = choices)
                self.parser.add_argument(prefix + name + '-low', type = tp, default = val[0], choices = choices)
                self.parser.add_argument(prefix + name + '-high', type = tp, default = val[1], choices = choices)
            if not (self.training or self.evaluate):
                self.param_names.append(under_name)
                self.param_names.append(under_name + '_low')
                self.param_names.append(under_name + '_high')
        else:
            if self.parser:
                self.parser.add_argument(prefix + name, type = tp, default = val, choices = choices)
            if not (self.training or self.evaluate):
                self.param_names.append(under_name)

    def _boolean_flag(self, name, train_val, eval_val = None):

        if self.training:
            val = train_val
            prefix = 'train-'
        elif self.evaluate:
            val = eval_val if eval_val != None else train_val
            prefix = 'eval-'
        else:
            val = None
            prefix = 'master-'

        dest = prefix + name
        under_dest = dest.replace('-', '_')
        if self.parser:
            self.parser.add_argument("--" + prefix + name, action = "store_true", default = val, dest = under_dest)
            self.parser.add_argument('--' + prefix + 'no-' + name, action = "store_false", dest = under_dest)

        if not (self.training or self.evaluate):
            under_name = name.replace('-', '_')
            self.param_names.append(under_name)

def dump_params(params):

    print('Parameters:')
    for param in sorted(params):
        print('   ', param, '=', repr(params[param]))

def dump_params_file(fname, params, *, prefix = 'master_'):

    with open(fname, 'w') as f:
        for param in sorted(params):
            f.write(prefix + param + ' = ' + repr(params[param]) + '\n')

def load_params_file(fname, *, prefix = 'master_'):

    config = {}
    with open(fname) as f:
        config_str = f.read()
    exec(config_str, {'inf': float('inf')}, config)

    params = {}
    for param, value in config.items():
        assert param.startswith(prefix)
        params[param[len(prefix):]] = value

    return params
