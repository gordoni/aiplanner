import os
import sys

from django.core.wsgi import get_wsgi_application

for path in (
    '/home/ubuntu/aacalc/web',
    '/home/ubuntu/aacalc/web/project',
    '/home/ubuntu/aacalc/spia',
):
    if path not in sys.path:
        sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

application = get_wsgi_application()
