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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} - {self.location}"


class RecommendedPlace(models.Model):
    """채팅봇에서 추천된 장소/이벤트 정보를 저장하는 모델"""
    user = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recommended_places'
    )
    date = models.DateField()
    place_name = models.CharField(max_length=255)
    place_location = models.CharField(max_length=255, blank=True)
    recommendation_reason = models.TextField(blank=True)
    place_url = models.TextField(blank=True)
    place_type = models.CharField(max_length=50, default='general')  # 'general' 또는 'event'
    event_date = models.CharField(max_length=255, blank=True)  # 이벤트 날짜 (텍스트로 저장)
    additional_info = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        
    def __str__(self):
        return f"{self.date} - {self.place_name}"
