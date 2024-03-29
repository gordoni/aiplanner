#!/usr/bin/env python3

# SPIA - Income annuity (SPIA and DIA) price calculator
# Copyright (C) 2015-2022 Gordon Irlam
#
# This program may be licensed by you (at your option) under an Open
# Source, Free for Non-Commercial Use, or Commercial Use License.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is free for non-commercial use: you can use and modify it
# under the terms of the Creative Commons
# Attribution-NonCommercial-ShareAlike 4.0 International Public License
# (https://creativecommons.org/licenses/by-nc-sa/4.0/).
#
# A Commercial Use License is available in exchange for agreed
# remuneration.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from argparse import ArgumentParser
from xml.etree import ElementTree
from os import devnull, mkdir, remove, rename, stat
from os.path import expanduser, isfile, join, normpath
from re import match, sub
from subprocess import call, check_call, check_output
from sys import stderr
from time import sleep
from urllib.parse import quote

datadir = '~/.spia'

class Fetcher:

    last_year = 2050  # Prevent runaway process in event of bug.

    def last_check_file(self):
        return join(self.dir, 'last_check.' + self.bond_type)

    def curl_cmd(self, year, last_check):

        cmd = ['curl', '-s', '-f']
        if last_check:
            cmd.extend(('-z', self.last_check_file()))
        cmd.append(self.url(year))

        return cmd

    def __init__(self, dir):

        self.dir = dir

        last_file_year = self.start_year
        for year in range(self.start_year, self.last_year, self.year_step):
            if isfile(self.csv_file(year)):
                 last_file_year = year

        lock_file = self.last_check_file() + '.lock'
        try:
            open(lock_file, 'x').close()
        except FileExistsError:
            print('Waiting on lock file:', lock_file, file = stderr)
            while isfile(lock_file):
                sleep(1)
            return
                # Assume got updated by a concurrent process, no need to update.

        sleep(5) # Prevent intra-machine clock skew problems.

        # Missing files.
        for year in range(self.start_year, last_file_year + self.year_step, self.year_step):
            if not isfile(self.csv_file(year)):
                self.fetch_year(year, False)

        self.fetch_year(last_file_year, True)
        for year in range(last_file_year + self.year_step, self.last_year, self.year_step):
            if not self.fetch_year(year, False):
                break

        rename(lock_file, self.last_check_file())

def fetch_yield_curve(bond_type, dir = None):

    if dir is None:
        dir = normpath(expanduser(datadir))
        try:
            mkdir(dir)
        except FileExistsError:
            pass
        dir = join(dir, bond_type)
        try:
            mkdir(dir)
        except FileExistsError:
            pass

    if bond_type == 'corporate':
        return CorporateFetcher(dir)
    elif bond_type == 'nominal':
        return NominalFetcher(dir)
    elif bond_type == 'real':
        return RealFetcher(dir)
    else:
        assert False

class CorporateFetcher(Fetcher):

    bond_type = 'corporate'

    start_year = 1984
    year_step = 5

    #url_base = 'https://www.treasury.gov/resource-center/economic-policy/corp-bond-yield/Documents/'
    url_base = 'https://home.treasury.gov/system/files/226/'
    url_file_part = 'hqm_%(start)02d_%(end)02d'

    def file_part(self, year):
        return self.url_file_part % {'start' : year % 100, 'end' : (year + self.year_step - 1) % 100}

    def url(self, year):
        return self.url_base + self.file_part(year) + '.xls'

    def csv_file(self, year):
        return self.dir + '/' + self.file_part(year) + '.csv'

    def xls_file(self, year):
        return self.dir + '/' + self.file_part(year) + '.xls.tmp'

    def fetch_year(self, fetch_year, last_check):

        csv_filename = self.csv_file(fetch_year)
        xls_filename = self.xls_file(fetch_year)

        out = open(xls_filename, 'w')
        status = call(self.curl_cmd(fetch_year, last_check), stdout=out)
        out.close()

        if status != 0 or stat(xls_filename).st_size == 0:
            remove(xls_filename)
            return False

        out = open(csv_filename + '.tmp', 'w')
        DEVNULL = open(devnull, 'w')  # Discard "Format a4 is redefined" warnings.
        check_call(('xls2csv', '-q1', '-g5', xls_filename), stdout=out, stderr=DEVNULL)
        out.close()
        DEVNULL.close()

        remove(xls_filename)

        rename(csv_filename + '.tmp', csv_filename)

        return True

class TreasuryFetcher(Fetcher):

    year_step = 1

    #url_args = 'year(NEW_DATE) eq %(year)d'
    url_args = 'field_tdr_date_value=%(year)d'

    def url(self, year):
        #return self.url_base + quote(self.url_args % {'year' : year})
        return self.url_base + (self.url_args % {'year' : year})

    def csv_file(self, year):
        return self.dir + '/' + self.bond_type + '-' + str(year) + '.csv'

    def fetch_year(self, fetch_year, last_check):

        s = check_output(self.curl_cmd(fetch_year, last_check)).decode('latin1')

        if s == '':
            return False

        years = {}
        rates = {}

        xml = ElementTree.fromstring(s)
        entries = False
        ns = {
            'empty_ns': 'http://www.w3.org/2005/Atom',
            'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
            'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
        }
        for entry in xml.iterfind('empty_ns:entry', ns):
            entries = True
            properties = entry.find('empty_ns:content', ns).find('m:properties', ns)
            date = properties.find('d:NEW_DATE', ns).text
            date = date[:date.index('T')]
            rates[date] = {}
            for child in properties.iter():
                m = match('^{.*}[BT]C_(\d+)(MONTH|YEAR)$', child.tag)
                if m:
                    maturity, unit = m.groups()
                    if unit == 'MONTH':
                        year = str(float(maturity) / 12)
                    else:
                        year = maturity
                    rate = child.text
                    if rate is not None:
                        years[year] = True
                        rates[date][year] = rate

        if not entries:
            return False

        years = list(years.keys())
        years.sort(key = lambda s: float(s))

        filename = self.csv_file(fetch_year)
        out = open(filename + '.tmp', 'w')

        out.write('# ' + self.bond_type + ' CMT yield curve\n')
        out.write('DATE,' + ','.join(years) + '\n')
        for date in sorted(rates.keys()):
            out.write(date + ',' + ','.join(rates[date].get(year, '') for year in years) + '\n')

        out.close()

        rename(filename + '.tmp', filename)

        return True

class NominalFetcher(TreasuryFetcher):

    bond_type = 'nominal'

    start_year = 1990

    #url_base = 'https://data.treasury.gov/feed.svc/DailyTreasuryYieldCurveRateData?$filter='
    url_base = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&'

class RealFetcher(TreasuryFetcher):

    bond_type = 'real'

    start_year = 2003

    #url_base = 'https://data.treasury.gov/feed.svc/DailyTreasuryRealYieldCurveRateData?$filter='
    url_base = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_real_yield_curve&'

if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('-t', '--type', choices=('corporate', 'nominal', 'real'), required=True)
    parser.add_argument('-d', '--directory', default=None)
    args = parser.parse_args()

    dir = args.directory
    bond_type = args.type

    fetch_yield_curve(bond_type, dir)
