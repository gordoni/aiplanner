import os
import sys

from django.core.wsgi import get_wsgi_application

path = '/home/ubuntu/aacalc/web'
if path not in sys.path:
    sys.path.append(path)

path = '/home/ubuntu/aacalc/web/project'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

application = get_wsgi_application()
