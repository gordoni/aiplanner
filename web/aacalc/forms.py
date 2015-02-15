from datetime import datetime
from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from time import strftime, strptime

from aacalc.utils import all_asset_classes, asset_class_names, too_early_for_asset_classes, too_late_for_asset_classes
from aacalc.views.utils import default_params

class HorizontalRadioRenderer(forms.RadioSelect.renderer):
    def render(self):
        return mark_safe(u'\n'.join([u'%s\n' % w for w in self]))

class DobOrAgeField(forms.CharField):

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

class ScenarioBaseForm(forms.Form):
    sex = forms.ChoiceField(
        choices = (('male', 'male'), ('female', 'female')))
    dob = DobOrAgeField(
        widget=forms.TextInput(attrs={'class': 'dob_input'}))
    sex2 = forms.ChoiceField(
        choices = (('', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    dob2 = DobOrAgeField(
        widget=forms.TextInput(attrs={'class': 'dob_input'}),
        required=False)
    advanced_position = forms.BooleanField(required=False,
        widget=forms.CheckboxInput(attrs={'class': 'advanced_button'}))
    defined_benefit_social_security = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    defined_benefit_pensions = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    defined_benefit_fixed_annuities = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    tax_rate_cg_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    tax_rate_div_default_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    cost_basis_method = forms.ChoiceField(
        choices=(('hifo', 'HIFO (highest-in first-out)'), ('avgcost', 'Average Cost'), ('fifo', 'FIFO (first-in first-out)')),
        widget=forms.RadioSelect(renderer=HorizontalRadioRenderer))
    advanced_goals = forms.BooleanField(required=False,
        widget=forms.CheckboxInput(attrs={'class': 'advanced_button'}))
    retirement_year = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'year_input'}),
        min_value=1900)
    withdrawal = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    utility_join_required = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=1)
    utility_join_desired = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    risk_tolerance = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}))
    vw_amount = forms.BooleanField(required=False)
    advanced_market = forms.BooleanField(required=False,
        widget=forms.CheckboxInput(attrs={'class': 'advanced_button'}))
    class_stocks = forms.BooleanField(required=False)
    class_bonds = forms.BooleanField(required=False)
    class_eafe = forms.BooleanField(required=False)
    class_ff_bl = forms.BooleanField(required=False)
    class_ff_bm = forms.BooleanField(required=False)
    class_ff_bh = forms.BooleanField(required=False)
    class_ff_sl = forms.BooleanField(required=False)
    class_ff_sm = forms.BooleanField(required=False)
    class_ff_sh = forms.BooleanField(required=False)
    class_reits_e = forms.BooleanField(required=False)
    class_reits_m = forms.BooleanField(required=False)
    class_baa = forms.BooleanField(required=False)
    class_aaa = forms.BooleanField(required=False)
    class_t10yr = forms.BooleanField(required=False)
    class_t1yr = forms.BooleanField(required=False)
    class_t1mo = forms.BooleanField(required=False)
    class_tips10yr = forms.BooleanField(required=False)
    class_gold = forms.BooleanField(required=False)
    class_risk_free = forms.BooleanField(required=False)
    ret_risk_free_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}))
    generate_start_year = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'year_input'}))
    generate_end_year = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'year_input'}))
    validate_start_year = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'year_input'}))
    validate_end_year = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'year_input'}))
    ret_equity_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}))
    ret_bonds_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}))
    expense_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    neg_validate_all_adjust_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}))
    validate_equity_vol_adjust_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    inherit = forms.BooleanField(required=False)
    utility_inherit_years = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0)
    utility_dead_limit_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    utility_bequest_consume = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    advanced_well_being = forms.BooleanField(required=False,
        widget=forms.CheckboxInput(attrs={'class': 'advanced_button'}))
    consume_discount_rate_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    upside_discount_rate_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0)
    utility_method = forms.ChoiceField(
        choices=(('floor_plus_upside', ''), ('ce', ''), ('slope', ''), ('eta', ''), ('alpha', '')))
    utility_join_slope_ratio_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}),
        min_value=0,
        max_value=100)
    utility_eta_1 = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50)
    utility_eta_2 = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50)
    utility_ce = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=Decimal('1.02'), # 1.01 fails.
        max_value=Decimal('1.5'))
    utility_slope_double_withdrawal = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=1,
        max_value=1e10) # 1e20 fails.
    utility_eta = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=50) # 100 fails.
    utility_alpha = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'large_numeric_input'}),
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
            raise ValidationError('Desired consumption too small. Increae desired consumption.')
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
    p_traditional_iras = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    p_roth_iras = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    p = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
      # No autofocus.  Would interfere with start mega_form.
    contribution = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'p_input'}),
        min_value=0)
    contribution_growth_pct = forms.DecimalField(
        widget=forms.TextInput(attrs={'class': 'percent_input'}))

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

    retirement_number = forms.BooleanField(widget=forms.HiddenInput())

class ScenarioEditForm(ScenarioAaForm):

    def clean(self):
        cleaned_data = super(ScenarioEditForm, self).clean()
        if self._errors:
            return cleaned_data
        check_retirement_year(cleaned_data)
        return cleaned_data

    retirement_number = forms.BooleanField(required=False)

class LeForm(forms.Form):

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
        dob2 = cleaned_data.get('dob2')
        if sex2 == None and dob2 != None or sex2 != None and dob2 == None:
            raise ValidationError('Invalid spouse/partner.')
        return cleaned_data

    sex = forms.ChoiceField(
        choices = (('male', 'male'), ('female', 'female')))
    dob = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=100)
    sex2 = forms.ChoiceField(
        choices = (('', 'none'), ('male', 'male'), ('female', 'female')),
        required=False)
    dob2 = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'small_numeric_input'}),
        min_value=0,
        max_value=100,
        required=False)
