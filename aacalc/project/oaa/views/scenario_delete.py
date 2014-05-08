from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect

from oaa.models import Scenario

@login_required
def scenario_delete(request, scenario_id):
    user = request.user
    account = user.account
    try:
        scenario = Scenario.objects.get(id=int(scenario_id), account=account)
    except Scenario.DoesNotExist:
        pass
    else:
        scenario.delete()
    return HttpResponseRedirect(reverse('scenarios'))
