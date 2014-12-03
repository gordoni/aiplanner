from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'oaa.views.home', name='home'),
    # url(r'^oaa/', include('oaa.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'oaa.views.home.home', name='home'),
    url(r'^about$', 'oaa.views.about.about', name='about'),
    url(r'^privacy_policy$', 'oaa.views.privacy_policy.privacy_policy', name='privacy_policy'),
    url(r'^scenarios/edit$', 'oaa.views.scenario_edit.scenario_edit', {'mode': 'edit'}, name='scenario_edit'),
    url(r'^scenarios/results$', 'oaa.views.scenario_run.scenario_run', name='scenario_run'),
    url(r'^calculators/aa$', 'oaa.views.scenario_edit.scenario_edit', {'mode': 'aa'}, name='start_aa'),
    url(r'^calculators/number$', 'oaa.views.scenario_edit.scenario_edit', {'mode': 'number'}, name='start_number'),
    url(r'^calculators/le$', 'oaa.views.le.le', name='start_le'),
    url(r'^docs/?$', RedirectView.as_view(url='/about')), # use reverse_lazy in Django 1.5+.
    url(r'^docs/(.*)$', 'oaa.views.docs.docs', name='docs'),
    url(r'^sample$', 'oaa.views.sample.sample', name='sample'),
    url(r'^healthcheck$', 'oaa.views.healthcheck.healthcheck'),
)
