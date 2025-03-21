from rest_framework import serializers
from .models import Schedule
from datetime import datetime

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ['id', 'date', 'location', 'companion', 'memo', 'weather_main', 'weather_icon', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'weather_main', 'weather_icon']

    def validate_date(self, value):
        """
        날짜 유효성 검사
        """
        if value < datetime.now().date():
            raise serializers.ValidationError("과거 날짜는 선택할 수 없습니다.")
        return value 