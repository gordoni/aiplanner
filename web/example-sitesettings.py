# Django settings that are unique to this site.
# Includes passwords that shouldn't be put under version control.

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('My Name', 'myname@myemaildomain'),
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '1234567890abcdefghijklmnopqrstuvwxyz1234567890abcd'

OPAL_HOST = 'localhost'
