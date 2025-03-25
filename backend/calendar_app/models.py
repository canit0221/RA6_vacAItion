from django.db import models
from vacation.settings import AUTH_USER_MODEL


class Schedule(models.Model):
    user = models.ForeignKey(
            AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='schedules'
        )    
    date = models.DateField()
    location = models.CharField(max_length=200)
    companion = models.CharField(max_length=200)
    memo = models.TextField(blank=True, null=True)

    weather_main = models.CharField(max_length=100, blank=True, null=True)
    weather_icon = models.CharField(max_length=20, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} - {self.location}"
