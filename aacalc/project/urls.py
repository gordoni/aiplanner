from django.conf.urls.defaults import patterns, include, url
from django.views.generic import RedirectView

from oaa.forms import PolicyPasswordResetForm, PolicySetPasswordForm

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
    url(r'^accounts/login/$', 'oaa.views.session_timeout.session_timout'),  # Session timeout bounce.
    #url(r'^accounts/login/$', 'oaa.views.login.login'),  # Session timeout bounce.
    #url(r'^accounts/login$', 'oaa.views.login.login', name='login'),
    #url(r'^accounts/logout$', 'oaa.views.logout.logout', name='logout'),
    #url(r'^accounts/create/step1$', 'oaa.views.account_create.account_create', {'scenario_id': None}, name='account_create'),
    #url(r'^accounts/create/step1/(\d+)$', 'oaa.views.account_create.account_create', name='account_create_run'),
    #url(r'^accounts/create/step2$', 'oaa.views.account_create_2.account_create_2', {'scenario_id': None}, name='account_create_2'),
    #url(r'^accounts/create/step2/(\d+)$', 'oaa.views.account_create_2.account_create_2', name='account_create_2_run'),
    #url(r'^accounts/create$', 'oaa.views.account_create_2.account_create_2', {'scenario_id': None}, name='account_create'),
    #url(r'^accounts/edit$', 'oaa.views.account_edit.account_edit', name='account_edit'),
    #url(r'^accounts/password/edit$', 'oaa.views.account_edit_password.account_edit_password', name='account_edit_password'),
    #url(r'^accounts/password/reset$', 'django.contrib.auth.views.password_reset', {'password_reset_form': PolicyPasswordResetForm}, name='forgot_password'),
    #url(r'^accounts/password/reset_done$', 'django.contrib.auth.views.password_reset_done'),
    #url(r'^reset/(?P<uidb36>[-\w]+)/(?P<token>[-\w]+)$', 'django.contrib.auth.views.password_reset_confirm', {'set_password_form': PolicySetPasswordForm}),
    #url(r'^accounts/password/reset_complete$', 'django.contrib.auth.views.password_reset_complete'),
    #url(r'^scenarios$', 'oaa.views.scenarios.scenarios', name='scenarios'),
    #url(r'^scenarios/create$', 'oaa.views.scenario_create.scenario_create', name='scenario_create'),
    url(r'^scenarios/edit/(\d+)$', 'oaa.views.scenario_edit.scenario_edit', name='scenario_edit'),
    url(r'^scenarios/results/(\d+)$', 'oaa.views.scenario_run.scenario_run', name='scenario_run'),
    #url(r'^scenarios/delete/(\d+)$', 'oaa.views.scenario_delete.scenario_delete', name='scenario_delete'),
    url(r'^calculators/aa$', 'oaa.views.start.start', {'mode': 'aa'}, name='start_aa'),
    url(r'^calculators/number$', 'oaa.views.start.start', {'mode': 'number'}, name='start_number'),
    url(r'^docs/?$', RedirectView.as_view(url='/about')), # use reverse_lazy in Django 1.5+.
    url(r'^docs/(.*)$', 'oaa.views.docs.docs', name='docs'),
    url(r'^sample$', 'oaa.views.sample.sample', name='sample'),
    url(r'^healthcheck$', 'oaa.views.healthcheck.healthcheck'),
)
