# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

cdef class AssetAllocation:

    cdef list aa

    # Worthwhile cdef'ing a few methods because they are called so frequently.
    # Return object so that exceptions can propagate.

    cdef object sum(self)
