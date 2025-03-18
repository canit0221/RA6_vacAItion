from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q
from datetime import datetime
from .models import Schedule
from .serializers import ScheduleSerializer

class ScheduleListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """모든 일정 조회"""
        schedules = Schedule.objects.filter(user=request.user)
        serializer = ScheduleSerializer(schedules, many=True)
        return Response(serializer.data)

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
        """특정 일정 조회"""
        schedule = self.get_object(pk, request.user)
        if not schedule:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ScheduleSerializer(schedule)
        return Response(serializer.data)

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
    
        

