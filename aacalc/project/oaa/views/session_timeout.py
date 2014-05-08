from django.shortcuts import render

def session_timout(request):
    return render(request, 'session_timeout.html')
