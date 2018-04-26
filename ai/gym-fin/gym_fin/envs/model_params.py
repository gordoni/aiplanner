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

        self.training_param_names = []
        self.param_names = []

    def add_arguments(self, parser, training):

        self.parser = parser
        self.training = training

        self._add_param('consume-floor', 1e4) # Minimum consumption level model is trained for.
            # Don't set too low, or utility at higher consumption levels will loose floating point precision.

        self._add_param('gamma', 3) # Coefficient of relative risk aversion.
        self._add_param('guaranteed-income', (1e3, 1e5), 1e4) # Social Security and similar income.
        self._add_param('p-notax', (1e3, 1e7), 1e5) # Taxable portfolio size.

    def set_params(self, dict_args):

        self.params = dict_args

    def get_params(self, training = False):

        prefix = 'model_' if training else 'eval_model_'
        names = self.training_param_names if training else self.param_names

        for name in names:
            if name.endswith('_low'):
                low = self.params[prefix + name]
                high = self.params[prefix + name[:-4] + '_high']
                assert low <= high

        return {name: self.params[prefix + name] for name in names}

    def _add_param(self, name, train_val, eval_val = None):
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

        under_name = name.replace('-', '_')
        param_names = self.training_param_names if self.training else self.param_names

        val = train_val if self.training or eval_val == None else eval_val
        prefix = '--model-' if self.training else '--eval-model-'

        if rnge:
            self.parser.add_argument(prefix + name + '-low', type = float, default = val[0])
            self.parser.add_argument(prefix + name + '-high', type = float, default = val[1])
            param_names.append(under_name + '_low')
            param_names.append(under_name + '_high')
        else:
            self.parser.add_argument(prefix + name, type = float, default = val)
            param_names.append(under_name)
