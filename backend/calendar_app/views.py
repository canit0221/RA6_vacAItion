from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q
from datetime import datetime
from .models import Schedule
from .serializers import ScheduleSerializer
from .utils import get_full_weather  # 날씨 데이터 가져오는 함수

# 날씨 아이콘과 텍스트 매핑
WEATHER_ICON_TO_TEXT = {
    '☀️': '맑음',
    '🌤️': '구름조금',
    '⛅': '구름많음',
    '☁️': '흐림',
    '🌧️': '비',
    '❄️': '눈',
    '🌨️': '비/눈',
    '🌦️': '소나기',
    '🌫️': '안개',
    '⚡': '번개',
    '🌪️': '폭풍'
}

class ScheduleListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """모든 일정 조회 + 날씨 데이터 포함"""
        schedules = Schedule.objects.filter(user=request.user)
        weather_data = get_full_weather()  # 1~10일치 날씨 데이터 가져오기

        # 날짜 형식 통일 (YYYYMMDD -> YYYY-MM-DD)
        for item in weather_data:
            if 'date' in item and len(item['date']) == 8 and item['date'].isdigit():
                item['date'] = f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"

        # JSON 직렬화
        serializer = ScheduleSerializer(schedules, many=True)
        schedule_data = serializer.data

        # 날짜별 날씨 데이터 매핑
        weather_dict = {item["date"]: item for item in weather_data}

        # 일정 데이터에 날씨 추가
        for schedule in schedule_data:
            schedule_date = schedule["date"]  # 일정의 날짜
            # 날짜 형식 통일
            if schedule_date and len(schedule_date) > 10:
                schedule_date = schedule_date[:10]
                
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
            try:
                # 날씨 데이터 가져오기
                weather_data = get_full_weather()
                
                # 날짜 형식 통일
                for item in weather_data:
                    if 'date' in item and len(item['date']) == 8 and item['date'].isdigit():
                        item['date'] = f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                
                # 날짜별 날씨 데이터 매핑
                weather_dict = {item["date"]: item for item in weather_data}
                
                # 해당 날짜의 날씨 정보 찾기
                schedule_date = request.data.get('date', '')
                if schedule_date and len(schedule_date) > 10:
                    schedule_date = schedule_date[:10]
                
                # 날씨 정보 찾기
                weather_info = weather_dict.get(schedule_date, {})
                
                # 날씨 아이콘과 상태 추출
                weather_icon = weather_info.get('icon', '')
                
                # 날씨 상태 텍스트 결정
                weather_main = weather_info.get('weather_main', '')
                if not weather_main:
                    weather_main = weather_info.get('description', '')
                if not weather_main and weather_icon in WEATHER_ICON_TO_TEXT:
                    weather_main = WEATHER_ICON_TO_TEXT[weather_icon]
                if not weather_main:
                    weather_main = weather_info.get('sky', '')
                
                # 날씨 정보와 함께 일정 저장
                schedule = serializer.save(
                    user=request.user,
                    weather_main=weather_main,
                    weather_icon=weather_icon
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"error": f"일정을 저장하는 중 오류가 발생했습니다: {str(e)}"}, 
                               status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
        
        # 날짜 형식 통일
        for item in weather_data:
            if 'date' in item and len(item['date']) == 8 and item['date'].isdigit():
                item['date'] = f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                
        weather_dict = {item["date"]: item for item in weather_data}

        # 일정에 해당하는 날짜의 날씨 추가
        schedule_date = schedule_data["date"]
        if schedule_date and len(schedule_date) > 10:
            schedule_date = schedule_date[:10]
            
        schedule_data["weather"] = weather_dict.get(schedule_date, None)

        return Response(schedule_data)

    def put(self, request, pk):
        """일정 수정"""
        schedule = self.get_object(pk, request.user)
        if not schedule:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ScheduleSerializer(schedule, data=request.data)
        if serializer.is_valid():
            try:
                # 날씨 데이터 가져오기
                weather_data = get_full_weather()
                
                # 날짜 형식 통일
                for item in weather_data:
                    if 'date' in item and len(item['date']) == 8 and item['date'].isdigit():
                        item['date'] = f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                
                # 날짜별 날씨 데이터 매핑
                weather_dict = {item["date"]: item for item in weather_data}
                
                # 해당 날짜의 날씨 정보 찾기
                schedule_date = request.data.get('date', '')
                if schedule_date and len(schedule_date) > 10:
                    schedule_date = schedule_date[:10]
                
                # 날씨 정보 찾기
                weather_info = weather_dict.get(schedule_date, {})
                
                # 날씨 아이콘과 상태 추출
                weather_icon = weather_info.get('icon', '')
                
                # 날씨 상태 텍스트 결정
                weather_main = weather_info.get('weather_main', '')
                if not weather_main:
                    weather_main = weather_info.get('description', '')
                if not weather_main and weather_icon in WEATHER_ICON_TO_TEXT:
                    weather_main = WEATHER_ICON_TO_TEXT[weather_icon]
                if not weather_main:
                    weather_main = weather_info.get('sky', '')
                
                # 날씨 정보와 함께 일정 업데이트
                updated_schedule = serializer.save(
                    weather_main=weather_main,
                    weather_icon=weather_icon
                )
                
                return Response(serializer.data)
            except Exception as e:
                return Response({"error": f"일정을 수정하는 중 오류가 발생했습니다: {str(e)}"}, 
                               status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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