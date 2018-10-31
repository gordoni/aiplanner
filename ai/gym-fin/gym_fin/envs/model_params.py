# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
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

        self._boolean_flag('verbose', False) # Display relevant model information such as when stepping.
        self._boolean_flag('display-returns', True) # Display yield and return statistics.

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
            # "pmt": payout with life expectancy consume_policy_life_expectancy and return amount consume_policy_annual_return.
        self._param('consume-initial', 0) # Initial consumption amount for particular consumption policies.
        self._param('consume-policy-life-expectancy', None) # Assumed life expectancy for particular consumption policies, or None to use actual life expectancy.
        self._param('consume-policy-return', 0) # Assumed annual return for particular consumption policies.
        self._param('annuitization-policy', 'rl', tp = string_type, choices = ('rl', 'age_real', 'none'))
            # Annuitization policy.
            # "rl": reinforcement learning.
            # "age_real": fully annuitize starting at annuitization_policy_age_real.
            # 'none': no SPIA purchases.
        self._param('annuitization-policy-age-real', 0) # Age (of youngest party) at which to switch from no annuitization to fully real annuitized.
        self._param('asset-allocation-policy', 'rl', tp = string_type)
            # Asset allocation policy.
            # "rl": reinforcement learning.
            # "age-in-nominal-bonds": age in years as nominal bonds percentage, remainder in stocks.
            # '{"<asset_class>":<allocation>, ...}': fixed allocation. Eg. '{"stocks":0.5, "nominal_bonds":0.5}'.
        # Bonds duration policy.
        # Defined by "real-bonds-duration" and "nominal-bonds-duration" below; None for reinforcement learning, or a fixed age in years.

        self._param('consume-floor', 1e4) # Minimum expected consumption level model is trained for.
        self._param('consume-ceiling', 1e5) # Maximum expected consumption level model is trained for.
            # Don't span too large a range as neural network fitting of utility to lower consumption levels will dominate over higher consumption levels.
            # This is because for gamma > 1 higher consumption levels are bounded (i.e. a small change in utility can produce a big change in consumption).
            # Will thus probably need separately trained models for different wealth levels.
        self._param('reward-clip', float('inf'), float('inf')) # Clip returned reward values to lie within [-reward_clip, reward_clip].
            # Clipping during training prevents rewards from spanning 5-10 or more orders of magnitude in the absence of guaranteed income.
            # Fitting the neural networks might then perform poorly as large negative reward values would swamp accuracy of more reasonable small reward values.
            #
            # To get a sense of relative reward sizes, note that, utility(consume_floor) = -1, and when gamma > 1, utility(inf) = 1 / (gamma - 1).
            #
            # Evaluation clip should always be inf.
            #
            # Chosen training clip of inf appears reasonable for PPO.
            # Setting a bound, such as 50, appears to produces worse CEs for Merton's portfolio problem, but has little effect when guaranteed income is present.
            #
            # In DDPG probably always need a low training clip value such as 10 on account of poor step choices getting saved and reused by the replay buffer.
            #
            # In DDPG could also try "--popart --normalize-returns" (see setup_popart() in ddpg/ddpg.py).
            # Need to first fix a bug in ddpg/models.py: set name='output' in final critic tf.layers.dense().
            # But doesn't appear to work well becasuse in the absense of guaranteed income the rewards may span a large many orders of magnitude range.
            # In particular some rewards can be -inf, or close there to, which appears to swamp the Pop-Art scaling of the other rewards.
        self._param('consume-clip', 0, 0) # Minimum allowed consumption level.
            # Similar role to reward_clip, but limit is specified in terms of consumption.
            # Evaluation clip should always be zero.
        self._param('consume-rescale', 'estimate_bounded', tp = string_type,
            choices = ('direct', 'positive_direct', 'fraction_direct', 'fraction_biased', 'estimate_biased', 'estimate_bounded'))
            # Type of re-scaling applied to consume action.
            #     "direct": consumption amount is consume action.
            #     "positive_direct": consumption amount is consume action (after exp).
            #     "fraction_direct": consumption fraction is a linear mapping of consume action (after tanh).
            #     "fraction_biased": consumption fraction is an exponential rescaling of consume action (after tanh).
            #     "estimate_bounded": consumption fraction is a bounded mapping of consume action based on expected consumption (after tanh).
            #     "estimate_biased": consumption fraction is an exponential rescaling of consume action based on expected consumption (after tanh).

        self._param('life-table', 'ssa-cohort', tp = string_type) # Life expectancy table to use. See spia module for possible values.
        self._param('life-table-date', '2020-01-01', tp = string_type) # Used to determine birth cohort for cohort based life expectancy tables.
        self._param('life-expectancy-additional', 0) # Initial age adjustment for first individual.
            # Shift initial age so as to add this many years to the life expectancy of the first individual.
            # Compute time will suffer if value is non-zero and age-start is variable rather than fixed.
        self._param('life-expectancy-additional2', 0) # Initial age adjustment for second individual.
        self._param('life-table-spia', 'iam2012-basic', tp = string_type) # Life expectancy table to use for pricing spia purchases.
        self._param('sex', 'female', tp = string_type, choices = ('male', 'female')) # Sex of first individual. Helps determine life expectancy table.
        self._param('sex2', None, tp = string_type, choices = ('male', 'female', None)) # Sex of second individual, None if none.
        self._param('age-start', (65, 65), 65) # Age of first individual.
        self._param('age-start2', (65, 65), 65) # Age of second individual.
        self._param('age-end', 120) # Model done when individuals reach this age.
        self._param('age-retirement', (65, 65), 65) # Assess and optimize consumption from when first individual reaches this age.
        self._param('consume-additional', 0.6)
            # When a second individual is present we consume this fraction more than a single individual for the same per individual utility.

        self._param('income-preretirement', (0, 0), 0) # Annual pre-tax pre-retirement income for first individual.
        self._param('income-preretirement2', (0, 0), 0) # Annual pre-tax pre-retirement income for second individual.
        self._param('income-preretirement-age-end', None)
            # Age of first individual when pre-retirement income ends, or None to base on first individual reaching age_retirement.
        self._param('income-preretirement-age-end2', None)
            # Age of second individual when pre-retirement income ends, or None to base on first individual reaching age_retirement.
        self._param('income-preretirement-mu', 0) # Pre-retirement income annual drift for first individual.
        self._param('income-preretirement-mu2', 0) # Pre-retirement income annual drift for second individual.
        self._param('income-preretirement-sigma', 0.12) # Pre-retirement income annual log volatility for first individual.
        self._param('income-preretirement-sigma2', 0.12) # Pre-retirement income annual log volatility for second individual.
        self._param('consume-preretirement', (0, 0), 0) # Annual pre-retirement consumption.
        self._param('consume-income-ratio-max', float('inf')) # Maximum allowed value of consume_preretirement / (income_preretirement + income_preretirement2).

        self._boolean_flag('have_401k', True) # 401(k) available to first individual.
        self._boolean_flag('have_401k2', True) # 401(k) available to second individual.

        self._param('time-period', 1) # Rebalancing time interval in years.
        self._param('gamma', (3, 3), 3) # Coefficient of relative risk aversion.
            # Will probably need smaller [consume_floor, consume_ceiling] ranges if use a large gamma value such as 6.

        self._param('defined-benefits', '[{"payout": [1e3, 1e5]}]', '[{"payout": 1e4}]', tp = string_type)
            # Defined benefits represented as a JSON array of objects. Object fields:
            #     "type": Type of defined benefit. Arbitrary string. Default "Income Annuity". A value of "Social Security" may in the future be taxed specially.
            #     "owner": Value "self" or "spouse". Default "self".
            #     "age": Starting age in years of owner for benefit. Default starts when first individual reaches age_retirement.
            #     "payout": Annual payment amount in today's dollars. May be a array of length 2 for stochastic log range. Required.
            #     "inflation_adjustment": Annual inflation increase fraction from today, or "cpi" for adjustment to reflect the CPI value. Default "cpi".
            #     "joint": true if payout drops on death of either self or spouse, false if value payout drops only on death of owner. Default false.
            #     "payout_fraction": payout fraction when joint contingency occurs. Default 0.
            #     "source_of_funds": "taxable", "tax_deferred", or "tax_free". Default "tax_deferred".
            #     "exclusion_period": If taxable, exclusion period in years from starting age. Default 0.
            #     "exclusion_amount": If taxable, annual tax exclusion amount of payout in today's dollars. Not adjusted for inflation. Default 0.
        self._param('defined-benefits-additional', '[]', tp = string_type) # Additional defined benefits.
        self._param('p-tax-free', (1e3, 1e7), 0) # Non-taxable portfolio size. Roth IRAs and similar. Empirically OK if eval amount is less than model lower bound.
        self._param('p-tax-deferred', (1e3, 1e7), 0) # Taxable deferred portfolio size. Traditional IRAs and similar.
        self._param('p-taxable-stocks', (1e3, 1e7), 0) # Taxable portfolio stocks.
        self._param('p-taxable-real-bonds', (1e3, 1e7), 0) # Taxable portfolio real bonds.
        self._param('p-taxable-nominal-bonds', (1e3, 1e7), 0) # Taxable portfolio nominal bonds.
        self._param('p-taxable-iid-bonds', (1e3, 1e7), 0) # Taxable portfolio iid bonds.
        self._param('p-taxable-bills', (1e3, 1e7), 0) # Taxable portfolio bills.
        self._param('p-taxable-stocks-basis-fraction', (0, 1.5), 1) # Taxable portfolio stocks cost basis as a fraction of stocks value.
        # Consumption order is assumed to be p_taxable, p_tax_deferred, p_notax.

        self._boolean_flag('tax', False) # Whether income is taxed.
        self._boolean_flag('income-aggregate', True) # When income isn't taxed, whether to aggregate tax_free, tax_deferred, and taxable observations.
        self._param('dividend-yield-stocks', 0.02) # Dividend yield for stocks.
        self._param('dividend-yield-bonds', 0.04) # Dividend yield for bonds and bills.
        self._param('qualified-dividends-stocks', 1) # Qualified dividends fraction for stocks. Qualified dividends are taxed at capital gains rates.
        self._param('qualified-dividends-bonds', 0) # Qualified dividends fraction for bonds and bills.
        self._param('tax-state', 0.06) # Aggregate state, local, and property taxes as a percentage of income after standard deduction.
            # Average state and local income tax rate is around 3%, and average state property tax is around 3% of income.

        self._boolean_flag('static-bonds', False)
            # Whether to model real bonds and inflation and thus nominal bonds and SPIAs as static (that is using a yield curve that does not vary over time).
        self._param('fixed-real-bonds-rate', None) # Rate to model real bonds with a fixed mean yield curve (does not favor duration).
        self._param('fixed-nominal-bonds-rate', None) # Rate to model nominal bonds in determining inflation with a fixed mean yield curve (does not favor duration).

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
        self._param('spias-min-purchase-fraction', 0) # Minimum fraction of total estimated annual income making up a SPIAs purchase.
        self._boolean_flag('couple-spias', True) # Enable purchase of SPIAs by couples.
        self._param('spias-permitted-from-age', 0) # Minimum age (of youngest party) at which able to purchase SPIAs.
        self._param('spias-permitted-to-age', 85) # Maximum age (of oldest party) at which able to purchase SPIAs.
            # Age at which availability of quotes starts to decrease.

        # Market parameters are based on World and U.S. averages from the Credit Suisse Global Investment Returns Yearbook 2017 for 1900-2016.
            # For equities the reported real return is 6.5% +/- 17.4%, standard error 1.6% (geometric 5.1%).
            # For nominal government bonds the reported real return is 2.4% +/- 11.2%, standard error 1.0% (geometric 1.8%).
            # For U.S. Treasury bills the reported real return is 0.9% +/- 0.4%, standard error 0.4% (geometric 0.8%).
            # The reported U.S. inflation rate is 3.0% +/- 4.7%, standard error 0.4% (geometric 2.9%).
        self._boolean_flag('returns-standard-error', True) # Whether to model the standard error of returns.
        self._boolean_flag('stocks', True) # Whether to model stocks.
        self._param('stocks-return', 0.065) # Annual real return for stocks prior to effects of mean reversion.
        self._param('stocks-volatility', 0.174) # Annual real volatility for stocks prior to effects of mean reversion.
        self._param('stocks-price', (0.5, 2.0)) # Initial price of stocks relative to fair price. Used in the case of mean reversion.
        self._param('stocks-mean-reversion-rate', 0) # Mean reversion rate, - d(return percentage)/d(overvalued percentage).
            # Set to zero for independent identically distributed stock returns.
            # Set to non-zero for mean reverting stock returns.
            # Use a value like 0.1 to mimick findings from Shiller's data, that for every 10% overvalued stocks are,
            # there is an approximate 1% reduction in annual returns for the following year.
        self._param('stocks-standard-error', 0.016) # Standard error of log real return for stocks.
        self._boolean_flag('real-bonds', True) # Whether to model real bonds (with an interest rate model).
        self._param('real-bonds-duration', None) # Duration in years to use for real bonds, or None to allow duration to vary.
        self._param('real-bonds-duration-max', 30) # Maximum allowed real duration to use when duration is allowed to vary.
        self._boolean_flag('nominal-bonds', True) # Whether to model nominal bonds (with an interest rate model).
        self._param('nominal-bonds-duration', None) # Duration in years to use for nominal bonds, or None to allow duration to vary.
        self._param('nominal-bonds-duration-max', 30) # Maximum allowed nominal duration to use when duration is allowed to vary.
        self._boolean_flag('iid-bonds', False) # Whether to model independent identically distributed bonds (without any interest rate model).
        self._param('iid-bonds-type', None, tp = string_type, choices = ('real', 'nominal', None))
            # Derive iid bond returns from the specified bond model, or None if iid bond returns are lognormally distributed.
        self._param('iid-bonds-duration', 15) # Duration to use when deriving iid bond returns from the bond model.
        self._param('iid-bonds-return', 0.024) # Annual real return for iid bonds when lognormal.
        self._param('iid-bonds-volatility', 0.112) # Annual real volatility for iid bonds when lognormal.
        self._param('bonds-standard-error', 0.010) # Standard error of log real return for bonds.
        self._param('real-short-rate', None) # Initial short real interest rate when using model, or None to use the average model value.
        self._param('inflation-standard-error', 0.004) # Standard error of log inflation.
        self._param('inflation-short-rate', None) # Initial inflation rate when using model, or None to use the average model value.
        self._boolean_flag('bills', True) # Whether to model stochastic bills (without any interest rate model).
        self._param('bills-return', 0.009) # Annual real return for bill asset class.
        self._param('bills-volatility', 0.004) # Annual real return for bill asset class.
        self._param('bills-standard-error', 0.004) # Standard error of log real return for bills.

        self._boolean_flag('observe-interest-rate', True) # Whether model reveals the short real interest rate to observers.
        self._boolean_flag('observe-inflation-rate', True) # Whether model reveals the short inflation rate to observers.

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

    def dump_params(self):

        print('Parameters:')
        for param in sorted(self.params):
            print('   ', param, '=', repr(self.params[param]))

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
            if not name in params:
                params[name] = get_param(name)
            if name.endswith('_low'):
                base = name[:-4]
                if get_param(base) == None:
                    low = get_param(base + '_low')
                    high = get_param(base + '_high')
                    assert low <= high
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

        if tp in (float, int):

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
            self.parser.add_argument(prefix + name, type = tp, default = None, choices = choices)
            self.parser.add_argument(prefix + name + '-low', type = tp, default = val[0], choices = choices)
            self.parser.add_argument(prefix + name + '-high', type = tp, default = val[1], choices = choices)
            if not (self.training or self.evaluate):
                self.param_names.append(under_name)
                self.param_names.append(under_name + '_low')
                self.param_names.append(under_name + '_high')
        else:
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
        self.parser.add_argument("--" + prefix + name, action = "store_true", default = val, dest = under_dest)
        self.parser.add_argument('--' + prefix + 'no-' + name, action = "store_false", dest = under_dest)

        if not (self.training or self.evaluate):
            under_name = name.replace('-', '_')
            self.param_names.append(under_name)

def dump_params_file(fname, params, *, prefix = 'master_'):

    with open(fname, 'w') as f:
        for param in sorted(params):
            f.write(prefix + param + ' = ' + repr(params[param]) + '\n')
