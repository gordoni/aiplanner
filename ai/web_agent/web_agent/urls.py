# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from django.conf.urls import url

from app import views

urlpatterns = [
    url(r'^start$', views.home, name = 'start'),
    url(r'^episode$', views.episode, name = 'episode'),
    url(r'^step$', views.step, name = 'step'),
    url(r'^finish$', views.finish, name = 'finish'),
]
