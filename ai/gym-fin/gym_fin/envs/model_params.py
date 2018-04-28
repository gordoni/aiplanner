# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

class ModelParams(object):

    def __init__(self):

        self.param_names = []

    def add_arguments(self, parser):

        self.parser = parser

        self._add_arguments()
        self._add_arguments(training = True)
        self._add_arguments(evaluate = True)

    def _add_arguments(self, training = False, evaluate = False):

        assert not (training and evaluate)

        self.training = training
        self.evaluate = evaluate

        self._boolean_flag('verbose', False) # Display relevant model information such as when stepping.

        self._param('consume-floor', 1e4) # Minimum consumption level model is trained for.
        self._param('consume-ceiling', 1e5) # Maximum consumption level model is trained for.
            # Don't span too large a range as neural network fitting of utility to lower consumption levels will dominate over higher consumption levels.
            # This is because for gamma > 1 higher consumption levels are bounded (i.e. a small change in utility can produce a big change in consumption).
            # Will thus probably need separately trained models for different wealth levels.

        self._param('time-period', 1) # Rebalancing time interval in years.
        self._param('gamma', 3) # Coefficient of relative risk aversion.
            # Will probably need smaller [consume_floor, consume_ceiling] ranges if use a large gamma value such as 6.

        self._param('guaranteed-income', (1e3, 1e5), 1e4) # Social Security and similar income. Empirically OK if eval amount is less than model lower bound.
        self._param('p-notax', (1e3, 1e7), 1e5) # Taxable portfolio size. Empirically OK if eval amount is less than model lower bound.

        self._param('risk-free-return', 0) # Annual real return for risk free asset class.
        self._param('stocks-return', 0.05) # Annual real return for stocks.
        self._param('stocks-volatility', 0.16) # Annual real volatility for stocks.

    def set_params(self, dict_args):

        self.params = dict_args

    def get_params(self, training = False):

        def get_param(name):
            if self.params['model_' + name] != None:
                return self.params['model_' + name]
            elif training:
                return self.params['train_model_' + name]
            else:
                return self.params['eval_model_' + name]

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

    def _param(self, name, train_val, eval_val = None, *, tp = float):
        '''Add parameter name to the model parameters.

        Uses the specified values as the default training and evaluation values.
        If eval_val is None, use train_val as the default evaluation value.

        Values may be a tuple to specify a range of values: (low, high).'''

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

        if train_range and not eval_range and eval_val != None:
            eval_val = (eval_val, eval_val)
        if eval_range and not train_range:
            train_val = (train_val, train_val)
        rnge = train_range or eval_range

        if self.training:
            val = train_val
            prefix = '--train-model-'
        elif self.evaluate:
            val = eval_val if eval_val != None else train_val
            prefix = '--eval-model-'
        else:
            if rnge:
                val = (None, None)
            else:
                val = None
            prefix = '--model-'

        under_name = name.replace('-', '_')
        if rnge:
            self.parser.add_argument(prefix + name, type = tp, default = None)
            self.parser.add_argument(prefix + name + '-low', type = tp, default = val[0])
            self.parser.add_argument(prefix + name + '-high', type = tp, default = val[1])
            if not (self.training or self.evaluate):
                self.param_names.append(under_name)
                self.param_names.append(under_name + '_low')
                self.param_names.append(under_name + '_high')
        else:
            self.parser.add_argument(prefix + name, type = tp, default = val)
            if not (self.training or self.evaluate):
                self.param_names.append(under_name)

    def _boolean_flag(self, name, train_val, eval_val = None):

        if self.training:
            val = train_val
            prefix = 'train-model-'
        elif self.evaluate:
            val = eval_val if eval_val != None else train_val
            prefix = 'eval-model-'
        else:
            val = None
            prefix = 'model-'

        dest = prefix + name
        under_dest = dest.replace('-', '_')
        self.parser.add_argument("--" + prefix + name, action = "store_true", default = val, dest = under_dest)
        self.parser.add_argument('--' + prefix + 'no-' + name, action = "store_false", dest = under_dest)

        if not (self.training or self.evaluate):
            under_name = name.replace('-', '_')
            self.param_names.append(under_name)
