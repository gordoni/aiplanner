import os
import sys

from django.core.wsgi import get_wsgi_application

for path in (
    '/home/ubuntu/aiplanner',
    '/home/ubuntu/aiplanner/aacalc',
    '/home/ubuntu/aiplanner/aacalc/project',
):
    if path not in sys.path:
        sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

application = get_wsgi_application()
