from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    username = models.CharField(max_length=50, primary_key=True, unique=True)
    nickname = models.CharField(max_length=50, blank=False, null=False, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    user_address = models.CharField(max_length=150, blank=False, null=False)

    def __str__(self):
        return self.username
