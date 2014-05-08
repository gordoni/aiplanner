from django.contrib import auth
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.forms.forms import NON_FIELD_ERRORS
from django.http import HttpResponseRedirect
from django.shortcuts import render

from oaa.forms import LoginForm

def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            key = 'login:' + username
            attempts = cache.get(key) or 0
            attempts += 1
            cache.set(key, attempts, 3600)
            if attempts >= 5:
                return render(request, 'notice.html', { 'msg': 'Too many login attempts.' })
            user = auth.authenticate(username=username, password=password)
            if user is not None and user.is_active:
                auth.login(request, user)
                return HttpResponseRedirect(reverse('scenarios'))
            form.full_clean()
            form._errors[NON_FIELD_ERRORS] = form.error_class(['No such user, incorrect password, or account disabled.'])
    else:
        form = LoginForm()
    return render(request, 'login.html', {
        'form': form,
    })
