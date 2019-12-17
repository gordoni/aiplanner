# AACalc - Asset Allocation Calculator
# Copyright (C) 2009, 2011-2019 Gordon Irlam
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

from datetime import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.forms import BooleanField, CharField, CheckboxInput, ChoiceField, DecimalField, Form, HiddenInput, IntegerField, RadioSelect, TextInput
from django.forms.formsets import formset_factory
from time import strftime, strptime

class HorizontalRadioRenderer(RadioSelect):
    def __init__(self, *args, attrs = {'class': 'radio-horizontal'}, **kwargs):
        super().__init__(*args, attrs = attrs, **kwargs)
    #def render(self):
    #    return mark_safe(u'\n'.join([u'%s\n' % w for w in self]))

class VerticalRadioRenderer(RadioSelect):
    def __init__(self, *args, attrs = None, **kwargs):
        if attrs == None:
            attrs = {}
        if 'class' in attrs:
            attrs['class'] += ' radio-vertical'
        else:
            attrs['class'] = 'radio-vertical'
        super().__init__(*args, attrs = attrs, **kwargs)
    #def render(self):
    #    return mark_safe(u'\n<br />\n'.join([u'%s\n' % w for w in self]))

class DobOrAgeField(CharField):

    def clean(self, v):
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
            try:
                dob = strptime(v, fmt)
                now_year = datetime.utcnow().timetuple().tm_year
                if fmt == '%m/%d/%y' and dob.tm_year > now_year:
                    dob = (dob.tm_year - 100, dob.tm_mon, dob.tm_mday, 0, 0, 0, 0, 0, 0)
                dob = strftime('%Y-%m-%d', dob)  # Some dobs convert but can't be represented as a string. eg. 06/30/1080.
                dob = strptime(dob, '%Y-%m-%d')
                return dob
            except ValueError:
                pass
        try:
            age = int(v)
        except ValueError:
            pass
        else:
            if 0 <= age < 98:
                return age
        if v == '':
            if self.required:
                raise ValidationError('This field is required.')
            else:
                return None
        raise ValidationError('Invalid age or date of birth.')

class LeForm(Form):

    def clean_sex2(self):
        sex2 = self.cleaned_data['sex2']
        if sex2 == '':
            return None
        else:
            return sex2

    def clean(self):
        cleaned_data = super(LeForm, self).clean()
        if self._errors:
            return cleaned_data
        sex2 = cleaned_data.get('sex2')
        age2 = cleaned_data.get('age2')
        if sex2 == None and age2 != None or sex2 != None and age2 == None:
            raise ValidationError('Invalid spouse/partner.')
        return cleaned_data

    sex = ChoiceField(
        choices = (('male', 'male'), ('female', 'female')))
    age = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)
    sex2 = ChoiceField(
        choices = (('', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    age2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)

class SpiaForm(Form):

    def clean_sex2(self):
        sex2 = self.cleaned_data['sex2']
        if sex2 == '':
            return None
        else:
            return sex2

    def clean_date(self):
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
            try:
                date_p = strptime(self.cleaned_data['date'], fmt)
                date_str = strftime('%Y-%m-%d', date_p)  # Some dates convert but can't be represented as a string. eg. 06/30/1080.
                return date_str
            except ValueError:
                pass
        raise ValidationError('Invalid quote date.')

    def clean(self):
        cleaned_data = super(SpiaForm, self).clean()
        if self._errors:
            return cleaned_data
        sex2 = cleaned_data.get('sex2')
        age2_years = cleaned_data.get('age2_years')
        age2_months = cleaned_data.get('age2_months')
        if sex2 == None and age2_years != None or sex2 != None and age2_years == None:
            raise ValidationError('Invalid secondary annuitant.')
        if age2_years == None and age2_months != None:
            raise ValidationError('Missing secondary annuitant age.')
        if cleaned_data['table'] == 'adjust' and (cleaned_data['le_set'] == None or sex2 != None and cleaned_data['le_set2'] == None):
            raise ValidationError('Missing adjusted life expectancy.')
        premium = 0 if cleaned_data['premium'] == None else 1
        payout = 0 if cleaned_data['payout'] == None else 1
        mwr_percent = 0 if cleaned_data['mwr_percent'] == None else 1
        if premium + payout + mwr_percent != 2:
            raise ValidationError('Specify exactly two of premium, payout, and Money\'s Worth Ratio.')
        return cleaned_data

    sex = ChoiceField(
        choices = (('male', 'male'), ('female', 'female')))
    age_years = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)
    age_months = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=11,
        required=False)
    sex2 = ChoiceField(
        choices = (('', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    age2_years = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)
    age2_months = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=11,
        required=False)
    joint_type = ChoiceField(
        choices=(('contingent', 'Contingent. Payout reduced on death of either annuitant.'), ('survivor', 'Survivor. Payout reduced only on death of primary annuitant.'), ),
        widget=VerticalRadioRenderer)
    joint_payout_percent = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=100)

    table = ChoiceField(
        choices=(('iam2012-basic', 'Comparable to the average annuitant of the same sex and age.'), ('ssa-cohort', 'Comparable to the general population of the same sex and age.'), ('adjust', 'Adjust life table to match specified life expectancy.'), ),
        widget=VerticalRadioRenderer)
    ae = ChoiceField(
        choices = (('none', 'no'), ('aer2005_13-grouped', 'age-grouped'), ('aer2005_13-summary', 'summary'), ))
    le_set = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)
    le_set2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)

    date = CharField(
        widget=TextInput(attrs={'class': 'dob_input'}))
    bond_type = ChoiceField(
        choices = (('real', 'inflation indexed TIPS (CPI-U)'), ('nominal', 'U.S. Treasury'), ('corporate', 'U.S. corporate'), ))
    bond_adjust_pct = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=-99)
    adjust = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=-20,
        max_value=20)
    cpi_adjust = ChoiceField(
        choices = (('all', 'payout'), ('payout', 'anniversary of 1st payout'), ('calendar', 'January 1st'), ))

    frequency = ChoiceField(
        choices = (('12', 'monthly'), ('4', 'quarterly'), ('2', 'semi-annual'), ('1', 'annual'), ))
    payout_delay_years = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=100,
        required=False)
    payout_delay_months = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0)
    period_certain = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0)

    premium = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0,
        required=False)
    payout = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0,
        required=False)
    mwr_percent = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        required=False)
    percentile = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=100)

    advanced_spia = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))
    advanced_bonds = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))

class AllocBaseForm(Form):

    def clean_date(self):
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
            try:
                date_p = strptime(self.cleaned_data['date'], fmt)
                date_str = strftime('%Y-%m-%d', date_p)  # Some dates convert but can't be represented as a string. eg. 06/30/1080.
                return date_str
            except ValueError:
                pass
        raise ValidationError('Invalid quote date.')

    def clean(self):
        cleaned_data = super(AllocBaseForm, self).clean()
        if any(self.db.errors):
            raise ValidationError('Error in defined benefits table.')
        if self._errors:
            return cleaned_data
        cleaned_data['db'] = self.db.cleaned_data if self.db.is_bound else self.db.initial
        sex2 = cleaned_data.get('sex2')
        age2 = cleaned_data.get('age2')
        retirement_age2 = cleaned_data.get('retirement_age2')
        if sex2 == 'none' and age2 != None or sex2 != 'none' and age2 == None:
            raise ValidationError('Invalid spouse/partner.')
        le_set2 = cleaned_data.get('le_set2')
        if sex2 == 'none' and le_set2 != None:
            raise ValidationError('Life expectancy specified for non-existant spouse.')
        if sex2 == 'none' and any((db['who'] == 'spouse') and (float(db['amount']) != 0) for db in cleaned_data['db']):
            raise ValidationError('Spousal defined benefits but no spouse present')
        if sex2 == 'none' and retirement_age2 != None:
            raise ValidationError('Retirement age specified for non-existant spouse.')
        mortgage = cleaned_data.get('mortgage')
        mortgage_payment = cleaned_data.get('mortgage_payment')
        have_rm = cleaned_data.get('have_rm')
        if mortgage > 0 and mortgage_payment == 0 and not have_rm:
            raise ValidationError('Mortgage specified but no mortgage payment.')
        rm_loc = cleaned_data.get('rm_loc')
        if rm_loc > 0 and not have_rm:
            raise ValidationError('Reverse mortgage credit line specified but no reverse mortgage.')
        required_income = cleaned_data.get('required_income')
        desired_income = cleaned_data.get('desired_income')
        if required_income != None and desired_income != None and required_income > desired_income:
            raise ValidationError('Required consumption exceeds desired consumption.')
        return cleaned_data

    class DbForm(Form):

        def clean(self):
            cleaned_data = super(AllocBaseForm.DbForm, self).clean()
            if cleaned_data['social_security']:
                if not cleaned_data['inflation_indexed']:
                    raise ValidationError('Social Security must be inflation indexed')
                if cleaned_data['joint_type'] == 'contingent':
                    raise ValidationError('Social Security death benefit must be survivor')
            return cleaned_data

        def __init__(self, data=None, *args, **kwargs):
            super(AllocBaseForm.DbForm, self).__init__(*args, data=data, **kwargs)
            if self.data[self.prefix + '-social_security'] == 'True' if self.is_bound else self.initial['social_security']:
                self.fields['inflation_indexed'].widget.attrs['readonly'] = True
                self.fields['joint_type'].widget.attrs['readonly'] = True

        social_security = BooleanField(
            required=False,
            widget=HiddenInput())
        description = ChoiceField(
            choices=(
                ('Pension', 'Pension'),
                ('Income annuity', 'Income annuity'),
                ('Reverse mortgage', 'Reverse mortgage'),
                ('Other', 'Other')),
            required=False)
        who = ChoiceField(
            choices = (('self', ''), ('spouse', '')),
            widget=HorizontalRadioRenderer)
        age = DecimalField(
            widget=TextInput(attrs={'class': 'small_numeric_input'}),
            min_value=0,
            max_value=110)
        amount = DecimalField(
            widget=TextInput(attrs={'class': 'p_input'}),
            min_value=0)
        inflation_indexed = BooleanField(required=False)
        joint_type = ChoiceField(
            choices=(('contingent', ''), ('survivor', ''), ),
            widget=HorizontalRadioRenderer)
        joint_payout_pct = DecimalField(
            widget=TextInput(attrs={'class': 'percent_input'}),
            min_value=0,
            max_value=100)

    def __init__(self, data=None, *args, **kwargs):
        super(AllocBaseForm, self).__init__(*args, data=data, **kwargs)
        if 'db' in data:
            self.db = self.DbFormSet(initial=data['db'])
        else:
            self.db = self.DbFormSet(data)

    sex = ChoiceField(
        choices = (('male', 'male'), ('female', 'female')))
    age = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)
    sex2 = ChoiceField(
        choices = (('none', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    age2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)
    le_set = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)
    le_set2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)

    DbFormSet = formset_factory(DbForm, extra=8, max_num=8)

    home = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    home_ret_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    home_vol_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    mortgage = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    mortgage_payment = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    mortgage_rate_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    have_rm = BooleanField(required=False)
    rm_loc = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)

    retirement_age2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)
    joint_income_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    needed_income = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0,
        required=False)
    desired_income = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0,
        required=False)
    purchase_income_annuity = BooleanField(required=False)
    use_lm_bonds = BooleanField(required=False)
    use_rm = BooleanField(required=False)
    rm_delay = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        required=False)
    rm_plf = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=1,
        required=False)
    rm_interest_rate_premium_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    rm_interest_rate_pct = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        required=False)
    rm_margin_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    rm_insurance_initial_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    rm_insurance_annual_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    rm_cost = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    rm_age = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)
    rm_tenure_limit = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)
    rm_tenure_duration = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=1)
    rm_eligible = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)

    equity_ret_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    equity_vol_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=1) # 0 fails.
    bonds_premium_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    bonds_vol_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=1) # 0 fails.
    inflation_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    equity_bonds_corr_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=-99,
        max_value=99) # 100 fails.
    real_vol_10yr_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    bonds_lm_bonds_corr_short_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=-100,
        max_value=100)
    equity_se_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    confidence_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=99.99)
    expense_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    date = CharField(
        widget=TextInput(attrs={'class': 'dob_input'}))
    real_rate_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        required = False)

    gamma = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50)
    risk_tolerance_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)

    advanced_calculations = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))

class AllocContribForm(AllocBaseForm):

    p_traditional_iras = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    tax_rate_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    p_roth_iras = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    p = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)

    contribution = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    contribution_reduction = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    contribution_growth_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    contribution_vol_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)

class AllocRetirementForm(AllocBaseForm):

    retirement_age = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)

class AllocIncomeForm(AllocBaseForm):

    required_income = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)

class AllocAaForm(AllocContribForm, AllocRetirementForm):

    pass

class AllocNumberForm(AllocRetirementForm, AllocIncomeForm):

    pass

class AllocRetireForm(AllocContribForm, AllocIncomeForm):

    pass
