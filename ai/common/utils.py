# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

def boolean_flag(parser, name, default = False):

    under_dest = name.replace('-', '_')
    parser.add_argument('--' + name, action = "store_true", default = default, dest = under_dest)
    parser.add_argument('--' + 'no-' + name, action = "store_false", dest = under_dest)
