from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.forms.forms import NON_FIELD_ERRORS
from django.http import HttpResponseRedirect
from django.shortcuts import render

from oaa.forms import AccountEditPasswordForm

@login_required
def account_edit_password(request):
    if request.method == 'POST':
        form = AccountEditPasswordForm(request.POST)
        if form.is_valid():
            old_password = form.cleaned_data['old_password']
            password = form.cleaned_data['password']
            user = request.user
            if authenticate(username=user.username, password=old_password) != None:
                user.set_password(password)
                user.save()
                return HttpResponseRedirect(reverse('scenarios'))
            else:
                form.full_clean()
                form._errors[NON_FIELD_ERRORS] = form.error_class(['Invalid password.'])
    else:
        form = AccountEditPasswordForm()
    return render(request, 'account_edit_password.html', {
        'form': form,
    })
