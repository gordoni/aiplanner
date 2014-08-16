import os
import sys

path = '/home/ubuntu/oaa/aacalc'
if path not in sys.path:
    sys.path.append(path)

path = '/home/ubuntu/oaa/aacalc/project'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
