from django.http import HttpResponseRedirect
from django.contrib import auth
from django.core.urlresolvers import reverse

def logout(request):
    auth.logout(request)
    response = HttpResponseRedirect(reverse('home'))
    response.delete_cookie('p')  # Makes testing esier if we can get back the original state by logging out.
    #response.delete_cookie('rc')
    return response
