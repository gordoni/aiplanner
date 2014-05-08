from django.contrib.auth.models import User
from django.db import models

class Account(models.Model):
    '''User additional information.'''
    user = models.OneToOneField(User)
    temp_user = models.BooleanField()
    run_count = models.IntegerField()
    privacy_policy = models.IntegerField()
    license_agreement = models.IntegerField()
    last_fail = models.DateTimeField(null=True)
    msg_marketing = models.BooleanField()  # annual rebalancing reminder email

class Scenario(models.Model):
    account = models.ForeignKey(Account)
    data = models.TextField()
