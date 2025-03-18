from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q
from datetime import datetime
from .models import Schedule
from .serializers import ScheduleSerializer
from .utils import get_full_weather  # 날씨 데이터 가져오는 함수

class ScheduleListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """모든 일정 조회 + 날씨 데이터 포함"""
        schedules = Schedule.objects.filter(user=request.user)
        weather_data = get_full_weather()  # 1~10일치 날씨 데이터 가져오기

        # JSON 직렬화
        serializer = ScheduleSerializer(schedules, many=True)
        schedule_data = serializer.data

        # 날짜별 날씨 데이터 매핑
        weather_dict = {item["date"]: item for item in weather_data}

        # 일정 데이터에 날씨 추가
        for schedule in schedule_data:
            schedule_date = schedule["date"]  # 일정의 날짜
            if schedule_date in weather_dict:
                schedule["weather"] = weather_dict[schedule_date]  # 해당 날짜의 날씨 추가

        return Response({
            'schedules': schedule_data,
            'weather': weather_data  # 전체 날씨 데이터도 포함 가능
        })

    def post(self, request):
        """새 일정 생성"""
        serializer = ScheduleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ScheduleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Schedule.objects.get(pk=pk, user=user)
        except Schedule.DoesNotExist:
            return None

    def get(self, request, pk):
        """특정 일정 조회 + 해당 날짜의 날씨 데이터 포함"""
        schedule = self.get_object(pk, request.user)
        if not schedule:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ScheduleSerializer(schedule)
        schedule_data = serializer.data

        # 1~10일치 날씨 데이터 가져오기
        weather_data = get_full_weather()
        weather_dict = {item["date"]: item for item in weather_data}

        # 일정에 해당하는 날짜의 날씨 추가
        schedule_date = schedule_data["date"]
        schedule_data["weather"] = weather_dict.get(schedule_date, None)

        return Response(schedule_data)

    def put(self, request, pk):
        """일정 수정"""
        schedule = self.get_object(pk, request.user)
        if not schedule:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ScheduleSerializer(schedule, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """일정 삭제"""
        schedule = self.get_object(pk, request.user)
        if not schedule:
            return Response(
                {"success": False, "message": "인증에 실패했습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        schedule.delete()

        return Response(
                {"success": True, "message": "일정이 삭제되었습니다."},
                status=status.HTTP_200_OK,
            )    
