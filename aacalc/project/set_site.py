#!/usr/bin/python

from django.contrib.sites.models import Site
from socket import gethostname

site = Site.objects.get(pk=1)
site.domain = gethostname() + '.aacalc.com'
site.name = 'AACalc'
site.save()
