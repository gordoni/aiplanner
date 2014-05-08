from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render

from oaa.forms import AccountCreateForm
from oaa.views.utils import try_account_create

def account_create_2(request, scenario_id):
    if request.method == 'POST':
        ac_form = AccountCreateForm(request.POST)
        if ac_form.is_valid():
            if try_account_create(request, ac_form):
                if scenario_id == None:
                    return HttpResponseRedirect(reverse('scenarios'))
                else:
                    return render(request, 'scenario_wait.html', {
                        'scenario_id': scenario_id,
                    })
    else:
        ac_form = AccountCreateForm()
    return render(request, 'mega_form.html', {
        'ac_form': ac_form,
    })
