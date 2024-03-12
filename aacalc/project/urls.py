from django.conf.urls import url
from django.urls import reverse_lazy
from django.views.generic import RedirectView

from aacalc.views.home import home
from aacalc.views.about import about
from aacalc.views.privacy_policy import privacy_policy
from aacalc.views.alloc import alloc
from aacalc.views.le import le
from aacalc.views.spia import spia
from aacalc.views.docs import docs
from aacalc.views.file import file
from aacalc.views.healthcheck import healthcheck

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = (
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),

    url(r'^$', home, name='home'),
    url(r'^about$', about, name='about'),
    url(r'^privacy_policy$', privacy_policy, name='privacy_policy'),
    #url(r'^calculators/aa$', alloc, {'mode': 'aa'}, name='start_aa'),
    #url(r'^calculators/number$', alloc, {'mode': 'number'}, name='start_number'),
    #url(r'^calculators/retire$', alloc, {'mode': 'retire'}, name='start_retire'),
    url(r'^calculators/aa$', RedirectView.as_view(url='https://www.aiplanner.com', permanent=False)),
    url(r'^calculators/number$', RedirectView.as_view(url='https://www.aiplanner.com', permanent=False)),
    url(r'^calculators/retire$', RedirectView.as_view(url='https://www.aiplanner.com', permanent=False)),
    url(r'^calculators/le$', le, name='start_le'),
    url(r'^calculators/spia$', spia, name='start_spia'),
    url(r'^docs/?$', RedirectView.as_view(url=reverse_lazy('about'), permanent=False)),
    url(r'^docs/(.*)$', docs, name='docs'),
    #url(r'^file/(.*)$', file, name='file'),
    url(r'^healthcheck$', healthcheck),
)
