from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q
from datetime import datetime
from .models import Schedule, RecommendedPlace
from .serializers import ScheduleSerializer
from .utils import get_full_weather  # 날씨 데이터 가져오는 함수
import json
import logging
import traceback

logger = logging.getLogger(__name__)

# 날씨 아이콘과 텍스트 매핑
WEATHER_ICON_TO_TEXT = {
    "☀️": "맑음",
    "🌤️": "구름조금",
    "⛅": "구름많음",
    "☁️": "흐림",
    "🌧️": "비",
    "❄️": "눈",
    "🌨️": "비/눈",
    "🌦️": "소나기",
    "🌫️": "안개",
    "⚡": "번개",
    "🌪️": "폭풍",
}


class ScheduleListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        사용자의 일정 목록 조회 + 날씨 데이터 포함

        query params:
        - date: 특정 날짜의 일정만 조회 (선택, YYYY-MM-DD 형식)
        """
        date = request.query_params.get("date")

        if date:
            # 특정 날짜 일정 조회
            schedules = Schedule.objects.filter(user=request.user, date=date)
        else:
            # 모든 일정 조회
            schedules = Schedule.objects.filter(user=request.user)

        # 날씨 데이터 가져오기
        weather_data = get_full_weather()  # 1~10일치 날씨 데이터 가져오기

        # 날짜 형식 통일 (YYYYMMDD -> YYYY-MM-DD)
        for item in weather_data:
            if "date" in item and len(item["date"]) == 8 and item["date"].isdigit():
                item["date"] = (
                    f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                )

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
                schedule["weather"] = weather_dict[
                    schedule_date
                ]  # 해당 날짜의 날씨 추가

        return Response(
            {
                "schedules": schedule_data,
                "weather": weather_data,  # 전체 날씨 데이터도 포함
            }
        )

    def post(self, request):
        """일정 생성"""
        serializer = ScheduleSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # 날씨 데이터 가져오기
                weather_data = get_full_weather()

                # 날짜 형식 통일
                for item in weather_data:
                    if (
                        "date" in item
                        and len(item["date"]) == 8
                        and item["date"].isdigit()
                    ):
                        item["date"] = (
                            f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                        )

                # 날짜별 날씨 데이터 매핑
                weather_dict = {item["date"]: item for item in weather_data}

                # 해당 날짜의 날씨 정보 찾기
                schedule_date = request.data.get("date", "")
                if schedule_date and len(schedule_date) > 10:
                    schedule_date = schedule_date[:10]

                # 날씨 정보 찾기
                weather_info = weather_dict.get(schedule_date, {})

                # 날씨 아이콘과 상태 추출
                weather_icon = weather_info.get("icon", "")

                # 날씨 상태 텍스트 결정
                weather_main = weather_info.get("weather_main", "")
                if not weather_main:
                    weather_main = weather_info.get("description", "")
                if not weather_main and weather_icon in WEATHER_ICON_TO_TEXT:
                    weather_main = WEATHER_ICON_TO_TEXT[weather_icon]
                if not weather_main:
                    weather_main = weather_info.get("sky", "")

                # 날씨 정보와 함께 일정 저장
                schedule = serializer.save(
                    user=request.user,
                    weather_main=weather_main,
                    weather_icon=weather_icon,
                )

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {"error": f"일정을 저장하는 중 오류가 발생했습니다: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ScheduleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        """해당 pk의 일정을 조회하고 사용자 일치 여부 확인"""
        return get_object_or_404(Schedule, pk=pk, user=user)

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
            if "date" in item and len(item["date"]) == 8 and item["date"].isdigit():
                item["date"] = (
                    f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                )

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
        serializer = ScheduleSerializer(schedule, data=request.data)

        if serializer.is_valid():
            try:
                # 날씨 데이터 가져오기
                weather_data = get_full_weather()

                # 날짜 형식 통일
                for item in weather_data:
                    if (
                        "date" in item
                        and len(item["date"]) == 8
                        and item["date"].isdigit()
                    ):
                        item["date"] = (
                            f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:8]}"
                        )

                # 날짜별 날씨 데이터 매핑
                weather_dict = {item["date"]: item for item in weather_data}

                # 해당 날짜의 날씨 정보 찾기
                schedule_date = request.data.get("date", "")
                if schedule_date and len(schedule_date) > 10:
                    schedule_date = schedule_date[:10]

                # 날씨 정보 찾기
                weather_info = weather_dict.get(schedule_date, {})

                # 날씨 아이콘과 상태 추출
                weather_icon = weather_info.get("icon", "")

                # 날씨 상태 텍스트 결정
                weather_main = weather_info.get("weather_main", "")
                if not weather_main:
                    weather_main = weather_info.get("description", "")
                if not weather_main and weather_icon in WEATHER_ICON_TO_TEXT:
                    weather_main = WEATHER_ICON_TO_TEXT[weather_icon]
                if not weather_main:
                    weather_main = weather_info.get("sky", "")

                # 날씨 정보와 함께 일정 업데이트
                updated_schedule = serializer.save(
                    weather_main=weather_main, weather_icon=weather_icon
                )

                return Response(serializer.data)
            except Exception as e:
                return Response(
                    {"error": f"일정을 수정하는 중 오류가 발생했습니다: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """일정 삭제"""
        schedule = self.get_object(pk, request.user)
        schedule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AddRecommendedPlaceView(APIView):
    """추천 장소를 일정에 추가하는 API"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        채팅 추천 장소를 일정에 추가하고 RecommendedPlace 모델에도 저장

        요청 데이터:
        - date: 일정 날짜 (YYYY-MM-DD)
        - place_name: 장소 이름
        - place_location: 장소 위치
        - recommendation_reason: 추천 이유
        - additional_info: 추가 정보
        - place_url: 장소 URL (선택)
        - place_type: 장소 유형 (일반/이벤트, 기본값: 'general')
        - event_date: 이벤트 날짜 (선택, 이벤트일 경우)
        """
        try:
            # 요청 데이터 파싱
            date = request.data.get("date")
            place_name = request.data.get("place_name")
            place_location = request.data.get("place_location", "")
            recommendation_reason = request.data.get("recommendation_reason", "")
            additional_info = request.data.get("additional_info", "")
            place_url = request.data.get("place_url", "")
            place_type = request.data.get("place_type", "general")
            event_date = request.data.get("event_date", "")

            if not date or not place_name:
                return Response(
                    {
                        "success": False,
                        "message": "날짜와 장소 이름은 필수 항목입니다.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 1. RecommendedPlace 모델에 저장
            recommended_place = RecommendedPlace.objects.create(
                user=request.user,
                date=date,
                place_name=place_name,
                place_location=place_location,
                recommendation_reason=recommendation_reason,
                place_url=place_url,
                place_type=place_type,
                event_date=event_date,
                additional_info=additional_info,
            )

            # 2. 해당 날짜의 일정에 메모로 추가
            schedule = Schedule.objects.filter(user=request.user, date=date).first()

            # 일정 정보 구성
            memo_content = ""
            if place_type == "event":
                # 이벤트 형식
                memo_content = f"[추천된 이벤트]\n이름: {place_name}\n"
                if event_date:
                    memo_content += f"일시: {event_date}\n"
                memo_content += f"장소: {place_location}\n\n"
            else:
                # 일반 장소 형식
                memo_content = (
                    f"[추천된 장소]\n이름: {place_name}\n위치: {place_location}\n\n"
                )

            if recommendation_reason:
                memo_content += f"추천 이유: {recommendation_reason}\n\n"
            if place_url and place_url != "정보 없음":
                memo_content += f"참고 링크: {place_url}\n\n"
            if additional_info:
                memo_content += f"참고 정보: {additional_info}\n\n"

            if schedule:
                # 기존 일정이 있으면 메모에 추가
                if schedule.memo:
                    schedule.memo += "\n\n" + memo_content
                else:
                    schedule.memo = memo_content
                schedule.save()
                return Response(
                    {
                        "success": True,
                        "message": "기존 일정에 추천 장소가 추가되었습니다.",
                        "schedule_id": schedule.id,
                        "recommended_place_id": recommended_place.id,
                        "date": date,
                        "place_name": place_name,
                        "place_location": place_location,
                        "place_type": place_type,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                # 새 일정 생성
                new_schedule = Schedule(
                    user=request.user,
                    date=date,
                    location="",  # 위치 필드는 비워둠
                    companion="",  # 기본값
                    memo=memo_content,
                )
                new_schedule.save()
                return Response(
                    {
                        "success": True,
                        "message": "새 일정에 추천 장소가 추가되었습니다.",
                        "schedule_id": new_schedule.id,
                        "recommended_place_id": recommended_place.id,
                        "date": date,
                        "place_name": place_name,
                        "place_location": place_location,
                        "place_type": place_type,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": f"일정 추가 중 오류가 발생했습니다: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecommendedPlaceListView(APIView):
    """추천된 장소/이벤트 목록 조회 API"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        사용자의 추천된 장소/이벤트 목록 조회

        query params:
        - date: 특정 날짜의 추천 장소만 조회 (선택, YYYY-MM-DD 형식)
        - place_type: 특정 유형의 추천 장소만 조회 (선택, 'general' 또는 'event')
        """
        date = request.query_params.get("date")
        place_type = request.query_params.get("place_type")

        # 기본 쿼리: 사용자의 모든 추천 장소
        query = RecommendedPlace.objects.filter(user=request.user)

        # 날짜 필터 적용
        if date:
            query = query.filter(date=date)

        # 장소 유형 필터 적용
        if place_type:
            query = query.filter(place_type=place_type)

        # 결과 직렬화
        recommended_places = list(
            query.values(
                "id",
                "date",
                "place_name",
                "place_location",
                "recommendation_reason",
                "place_url",
                "place_type",
                "event_date",
                "additional_info",
                "created_at",
            )
        )

        return Response(recommended_places)


class RecommendedPlaceDetailView(APIView):
    """추천된 장소/이벤트 상세 조회/삭제 API"""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        """해당 pk의 추천 장소를 조회하고 사용자 일치 여부 확인"""
        return get_object_or_404(RecommendedPlace, pk=pk, user=user)

    def get(self, request, pk):
        """특정 추천 장소 상세 정보 조회"""
        try:
            place = self.get_object(pk, request.user)
            return Response(
                {
                    "id": place.id,
                    "date": place.date,
                    "place_name": place.place_name,
                    "place_location": place.place_location,
                    "recommendation_reason": place.recommendation_reason,
                    "place_url": place.place_url,
                    "place_type": place.place_type,
                    "event_date": place.event_date,
                    "additional_info": place.additional_info,
                    "created_at": place.created_at,
                }
            )
        except Exception as e:
            if "RecommendedPlace matching query does not exist" in str(e):
                return Response(
                    {"error": "해당 추천 장소가 존재하지 않습니다."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        """추천 장소 삭제"""
        place = self.get_object(pk, request.user)
        place.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
