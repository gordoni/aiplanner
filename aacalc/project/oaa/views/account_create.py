from django.shortcuts import render

def account_create(request, scenario_id):
    return render(request, 'account_create.html', {
        'scenario_id': scenario_id,
    })
