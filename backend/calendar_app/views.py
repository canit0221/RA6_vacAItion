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
            return Response(status=status.HTTP_404_NOT_FOUND)
        schedule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MonthlyScheduleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """월별 일정 조회"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        
        try:
            date = datetime(int(year), int(month), 1)
            schedules = Schedule.objects.filter(
                user=request.user,
                date__year=date.year,
                date__month=date.month
            )
            serializer = ScheduleSerializer(schedules, many=True)
            return Response(serializer.data)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid year or month parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

class DailyScheduleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """일별 일정 조회"""
        date_str = request.query_params.get('date')
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            schedules = Schedule.objects.filter(
                user=request.user,
                date=date
            )
            serializer = ScheduleSerializer(schedules, many=True)
            return Response(serializer.data)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid date parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

class SearchScheduleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """일정 검색"""
        query = request.query_params.get('q', '')
        if query:
            schedules = Schedule.objects.filter(
                user=request.user
            ).filter(
                Q(location__icontains=query) |
                Q(companion__icontains=query) |
                Q(memo__icontains=query)
            )
            serializer = ScheduleSerializer(schedules, many=True)
            return Response(serializer.data)
        return Response(
            {"error": "Search query is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
