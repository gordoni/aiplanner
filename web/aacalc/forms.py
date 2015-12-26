from datetime import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.forms import BooleanField, CharField, CheckboxInput, ChoiceField, DecimalField, Form, HiddenInput, IntegerField, RadioSelect, TextInput
from django.forms.formsets import formset_factory
from time import strftime, strptime

from aacalc.utils import all_asset_classes, asset_class_names, too_early_for_asset_classes, too_late_for_asset_classes
from aacalc.views.utils import default_params

class HorizontalRadioRenderer(RadioSelect.renderer):
    def render(self):
        return mark_safe(u'\n'.join([u'%s\n' % w for w in self]))

class VerticalRadioRenderer(RadioSelect.renderer):
    def render(self):
        return mark_safe(u'\n<br />\n'.join([u'%s\n' % w for w in self]))

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

class ScenarioBaseForm(Form):
    sex = ChoiceField(
        choices = (('male', 'male'), ('female', 'female')))
    dob = DobOrAgeField(
        widget=TextInput(attrs={'class': 'dob_input'}))
    sex2 = ChoiceField(
        choices = (('', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    dob2 = DobOrAgeField(
        widget=TextInput(attrs={'class': 'dob_input'}),
        required=False)
    advanced_position = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))
    defined_benefit_social_security = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    defined_benefit_pensions = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    defined_benefit_fixed_annuities = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    tax_rate_cg_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    tax_rate_div_default_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    cost_basis_method = ChoiceField(
        choices=(('hifo', 'HIFO (highest-in first-out)'), ('avgcost', 'Average Cost'), ('fifo', 'FIFO (first-in first-out)')),
        widget=RadioSelect(renderer=HorizontalRadioRenderer))
    advanced_goals = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))
    retirement_year = IntegerField(
        widget=TextInput(attrs={'class': 'year_input'}),
        min_value=1900)
    withdrawal = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    utility_join_required = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=1)
    utility_join_desired = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    risk_tolerance = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    vw_amount = BooleanField(required=False)
    advanced_market = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))
    class_stocks = BooleanField(required=False)
    class_bonds = BooleanField(required=False)
    class_eafe = BooleanField(required=False)
    class_ff_bl = BooleanField(required=False)
    class_ff_bm = BooleanField(required=False)
    class_ff_bh = BooleanField(required=False)
    class_ff_sl = BooleanField(required=False)
    class_ff_sm = BooleanField(required=False)
    class_ff_sh = BooleanField(required=False)
    class_reits_e = BooleanField(required=False)
    class_reits_m = BooleanField(required=False)
    class_baa = BooleanField(required=False)
    class_aaa = BooleanField(required=False)
    class_t10yr = BooleanField(required=False)
    class_t1yr = BooleanField(required=False)
    class_t1mo = BooleanField(required=False)
    class_tips10yr = BooleanField(required=False)
    class_gold = BooleanField(required=False)
    class_risk_free = BooleanField(required=False)
    ret_risk_free_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    generate_start_year = IntegerField(
        widget=TextInput(attrs={'class': 'year_input'}))
    generate_end_year = IntegerField(
        widget=TextInput(attrs={'class': 'year_input'}))
    validate_start_year = IntegerField(
        widget=TextInput(attrs={'class': 'year_input'}))
    validate_end_year = IntegerField(
        widget=TextInput(attrs={'class': 'year_input'}))
    ret_equity_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    ret_bonds_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    expense_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    neg_validate_all_adjust_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    validate_equity_vol_adjust_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    inherit = BooleanField(required=False)
    utility_inherit_years = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0)
    utility_dead_limit_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    utility_bequest_consume = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    advanced_well_being = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))
    consume_discount_rate_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    upside_discount_rate_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    utility_method = ChoiceField(
        choices=(('floor_plus_upside', ''), ('ce', ''), ('slope', ''), ('eta', ''), ('alpha', '')))
    utility_join_slope_ratio_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    utility_eta_1 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50)
    utility_eta_2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=8) # 10 fails due to fp rounding and inverse_utility.
    utility_ce = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=Decimal('1.02'), # 1.01 fails.
        max_value=Decimal('1.5'))
    utility_slope_double_withdrawal = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=1,
        max_value=1e10) # 1e20 fails.
    utility_eta = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50) # 100 fails.
    utility_alpha = DecimalField(
        widget=TextInput(attrs={'class': 'large_numeric_input'}),
        min_value=0,
        max_value=100) # 1000 fails.

    def coppa(sel, dob):
        if dob == None:
            return None
        if isinstance(dob, int):
            age = dob
        else:
            now_year = datetime.utcnow().timetuple().tm_year
            age = now_year - dob.tm_year
            dob = strftime('%Y-%m-%d', dob) # Ensure can be serailized.
        if age <= 13:
            raise ValidationError('Children under 13 prohibited as per COPPA.')
        return dob

    def clean_dob(self):
        return self.coppa(self.cleaned_data['dob'])

    def clean_sex2(self):
        sex2 = self.cleaned_data['sex2']
        if sex2 == '':
            return None
        else:
            return sex2

    def clean_dob2(self):
        return self.coppa(self.cleaned_data['dob2'])

    def clean(self):
        cleaned_data = super(ScenarioBaseForm, self).clean()
        if self._errors:
            return cleaned_data
        #if self._readonly:
        #    for field in self.readonly_fields:
        #        cleaned_data[field] = default_params[field]
        sex2 = cleaned_data.get('sex2')
        dob2 = cleaned_data.get('dob2')
        if sex2 == None and dob2 != None or sex2 != None and dob2 == None:
            raise ValidationError('Invalid spouse/partner.')
        if cleaned_data['utility_join_desired'] < Decimal('0.002') * cleaned_data['utility_join_required']:
            # Prevent singular matrix when solve in UtilityJoinSlope.java.
            raise ValidationError('Desired consumption too small. Increase desired consumption.')
        if cleaned_data['withdrawal'] == 0:
            raise ValidationError('Zero annual retirement withdrawal amount')
        if cleaned_data['inherit'] and cleaned_data['utility_method'] == 'floor_plus_upside' and cleaned_data['utility_eta_2'] <= 1:
            raise ValidationError('Bequest requires well-being coefficient of relative risk aversion >= 1.')
        # Don't worry about other utility methods, unlikely to have a coefficient <= 1; bequest will just be ignored.
        classes = sum(int(cleaned_data[asset_class]) for asset_class in all_asset_classes())
        if classes < 2:
            raise ValidationError('Must select at least two asset classes to analyze.')
        too_early = asset_class_names(too_early_for_asset_classes(cleaned_data, cleaned_data['generate_start_year']))
        if too_early:
            raise ValidationError('No data available for analysis start year - deselect ' + ', '.join(too_early) + ', or edit analysis start year in market parameters.')
        too_late = asset_class_names(too_late_for_asset_classes(cleaned_data, cleaned_data['generate_end_year']))
        if too_late:
            raise ValidationError('No data available for analysis end year - deselect ' + ', '.join(too_late) + ', or edit analysis end year in market parameters.')
        if cleaned_data['generate_end_year'] - cleaned_data['generate_start_year'] + 1 < 40:
            raise ValidationError('Too little analysis data available - edit analysis period in market parameters.')
        too_early = asset_class_names(too_early_for_asset_classes(cleaned_data, cleaned_data['validate_start_year']))
        if too_early:
            raise ValidationError('No data available for simulation start year - deselect ' + ', '.join(too_early) + ', or edit simulation start year in market parameters.')
        too_late = asset_class_names(too_late_for_asset_classes(cleaned_data, cleaned_data['validate_end_year']))
        if too_late:
            raise ValidationError('No data available for simulation end year - deselect ' + ', '.join(too_late) + ', or edit simulation end year in market parameters.')
        if cleaned_data['validate_end_year'] - cleaned_data['validate_start_year'] + 1 < 40:
            raise ValidationError('Too little simulation data available - edit simulation period in market parameters.')
        # Require a minimal defined benefit to avoid negative infinities.
        if cleaned_data['defined_benefit_social_security'] == 0 and cleaned_data['defined_benefit_pensions'] == 0 and cleaned_data['defined_benefit_fixed_annuities'] == 0:
            raise ValidationError('You have no Social Security or other guaranteed income.')
        if cleaned_data['utility_inherit_years'] <= 0:
            raise ValidationError('Bequest share parameter must be positive.')
        if cleaned_data['utility_method'] == 'floor_plus_upside' and cleaned_data['upside_discount_rate_pct'] < cleaned_data['consume_discount_rate_pct']:
            raise ValidationError('Upside discount rate is less than consumption and bequest discount rate')
        return cleaned_data

class ScenarioAaForm(ScenarioBaseForm):
    p_traditional_iras = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    p_roth_iras = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    p = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
      # No autofocus.  Would interfere with start mega_form.
    contribution = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    contribution_growth_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))

def check_retirement_year(cleaned_data):
    dob = cleaned_data.get('dob')
    dob2 = cleaned_data.get('dob2')
    retirement_year = cleaned_data.get('retirement_year')
    now_year = datetime.utcnow().timetuple().tm_year
    if isinstance(dob, int):
        retirement_age = dob + retirement_year - now_year
    else:
        dob = strptime(dob, '%Y-%m-%d')
        retirement_age = retirement_year - dob.tm_year
    if retirement_age >= 100:
        raise ValidationError('Too old for retirement year.')
    if dob2 == None:
        pass
    else:
        if isinstance(dob2, int):
            retirement_age = dob2 + retirement_year - now_year
        else:
            dob2 = strptime(dob2, '%Y-%m-%d')
            retirement_age = retirement_year - dob2.tm_year
        if retirement_age >= 100:
            raise ValidationError('Spouse/partner too old for retirement year.')

class ScenarioNumberForm(ScenarioBaseForm):

    def clean(self):
        cleaned_data = super(ScenarioNumberForm, self).clean()
        if self._errors:
            return cleaned_data
        check_retirement_year(cleaned_data)
        return cleaned_data

    retirement_number = BooleanField(widget=HiddenInput())

class ScenarioEditForm(ScenarioAaForm):

    def clean(self):
        cleaned_data = super(ScenarioEditForm, self).clean()
        if self._errors:
            return cleaned_data
        check_retirement_year(cleaned_data)
        return cleaned_data

    retirement_number = BooleanField(required=False)

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
        if cleaned_data['table'] == 'adjust' and cleaned_data['le'] == None:
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
        widget=RadioSelect(renderer=VerticalRadioRenderer))
    joint_payout_percent = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=100)

    table = ChoiceField(
        choices=(('iam', 'Comparable to the average annuitant of the same sex and age.'), ('ssa_cohort', 'Comparable to the general population of the same sex and age.'), ('adjust', 'Adjust life table to match specified life expectancy.'), ),
        widget=RadioSelect(renderer=VerticalRadioRenderer))
    ae = ChoiceField(
        choices = (('none', 'no'), ('summary', 'summary'), ('full', 'age specific'), ))
    le = DecimalField(
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

class AllocForm(Form):

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
        cleaned_data = super(AllocForm, self).clean()
        if any(self.db.errors):
            raise ValidationError('Error in defined benefits table.')
        if self._errors:
            return cleaned_data
        cleaned_data['db'] = tuple(f.cleaned_data for f in self.db.forms)
        sex2 = cleaned_data.get('sex2')
        age2 = cleaned_data.get('age2')
        if sex2 == None and age2 != None or sex2 != None and age2 == None:
            raise ValidationError('Invalid spouse/partner.')
        if sex2 == None and any((db['who'] == 'spouse' or float(db['joint_payout_pct']) != 0) and (float(db['amount']) != 0) for db in cleaned_data['db']):
            raise ValidationError('Spousal defind benefits but no spouse present')
        return cleaned_data

    class DbForm(Form):
        description = ChoiceField(
            choices=(
                ('Social Security', 'Social Security'),
                ('Pension', 'Pension'),
                ('Income annuity', 'Income annuity')))
        who = ChoiceField(
            choices = (('self', ''), ('spouse', '')),
            widget=RadioSelect(renderer=HorizontalRadioRenderer))
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
            widget=RadioSelect(renderer=HorizontalRadioRenderer))
        joint_payout_pct = DecimalField(
            widget=TextInput(attrs={'class': 'percent_input'}),
            min_value=0,
            max_value=100)

    def __init__(self, data=None, *args, **kwargs):
        super(AllocForm, self).__init__(*args, data=data, **kwargs)
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
        choices = (('', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    age2 = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110,
        required=False)
    date = CharField(
        widget=TextInput(attrs={'class': 'dob_input'}))

    DbFormSet = formset_factory(DbForm, extra=8, max_num=8)
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
    contribution_growth_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    contribution_vol_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    equity_contribution_corr_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=-99,
        max_value=99) # 100 fails.

    retirement_age = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=110)
    joint_income_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    desired_income = DecimalField(
        widget=TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    purchase_income_annuity = BooleanField(required=False)

    equity_ret_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}))
    equity_vol_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    equity_se_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    equity_range_factor = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0)
    expense_pct = DecimalField(
        widget=TextInput(attrs={'class': 'percent_input'}),
        min_value=0)

    gamma = DecimalField(
        widget=TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50)

    advanced_calculations = BooleanField(required=False,
        widget=CheckboxInput(attrs={'class': 'advanced_button'}))
