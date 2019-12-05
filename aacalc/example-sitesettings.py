# Django settings that are unique to this site.
# Includes passwords that shouldn't be put under version control.

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ROOT = '/home/ubuntu/aiplanner'
STATIC_ROOT = '/home/ubuntu/aacalc.data/static'

ADMINS = (
    ('<FirstName> <LastName>', '<user@email.com>'),
)

ALLOWED_HOSTS = [
    '.aacalc.com',
]

# Make this unique, and don't share it with anybody.
SECRET_KEY = '1234567890abcdefghijklmnopqrstuvwxyz1234567890abcd'
