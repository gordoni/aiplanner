from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render

from oaa.forms import AccountEditForm

@login_required
def account_edit(request):
    user = request.user
    account = user.account
    if request.method == 'POST':
        form = AccountEditForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            msg_marketing = form.cleaned_data['msg_marketing']
            user.email = email
            user.save()
            account.msg_marketing = msg_marketing
            account.save()
            return HttpResponseRedirect(reverse('scenarios'))
    else:
        form = AccountEditForm({
            'email': user.email,
            'msg_marketing': account.msg_marketing,
        })
    return render(request, 'account_edit.html', {
        'form': form,
    })
