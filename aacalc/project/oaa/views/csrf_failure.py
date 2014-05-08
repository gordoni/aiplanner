from django.shortcuts import render

def csrf_failure(request, reason=''):
    return render(request, 'notice.html', { 'msg': 'Cookies need to be enabled to use this site.' })
