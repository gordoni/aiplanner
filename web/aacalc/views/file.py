# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2018 Gordon Irlam
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os.path import dirname, join

from django.http import Http404, HttpResponse

files = {
    'README': ('spia/README', 'text/plain'),
    'agpl-3.0.txt': ('spia/agpl-3.0.txt', 'text/plain'),
    'spia.py': ('spia/spia.py', 'application/octet-stream'),
    'life_table.py': ('spia/life_table.py', 'application/octet-stream'),
    'yield_curve.py': ('spia/yield_curve.py', 'application/octet-stream'),
    'monotone_convex.py': ('spia/monotone_convex.py', 'application/octet-stream'),
    'fetch_yield_curve': ('spia/fetch_yield_curve', 'application/octet-stream'),
}

def file(request, file):
    assert(".." not in file)
    try:
        path, content_type = files[file]
    except KeyError:
        raise Http404
    path_abs = join(dirname(__file__), '..', '..', '..', path)
    f = open(path_abs)
    return HttpResponse(f, content_type = content_type)
