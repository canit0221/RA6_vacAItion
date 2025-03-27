import json
import os
import random
import urllib.request
from .base import GraphState
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, List
from .location_agent import extract_location_and_category
from django.apps import apps
import asyncio
from channels.db import database_sync_to_async
from functools import wraps
import re
import aiohttp
import logging
from .data_loader import load_data
from langchain_openai import OpenAIEmbeddings

# 로거 설정
logger = logging.getLogger(__name__)

# 환경 변수 명시적 로드
def load_env_variables():
    """환경 변수를 명시적으로 로드"""
    # .env 파일 로드
    load_dotenv()
    
    # 환경 변수 확인
    naver_client_id = os.getenv("NAVER_CLIENT_ID")
    naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    return naver_client_id, naver_client_secret

# 세션에서 URL 파라미터를 가져오는 함수 (비동기 처리를 위해 별도로 분리)
@database_sync_to_async
def get_session_params(session_id):
    """
    세션 ID로부터 URL 파라미터를 비동기적으로 가져오는 함수
    
    Args:
        session_id: 채팅 세션 ID
        
    Returns:
        dict: URL 파라미터 딕셔너리 또는 None
    """
    try:
        ChatSession = apps.get_model("chatbot", "ChatSession")
        session = ChatSession.objects.filter(id=session_id).first()
        
        if session and hasattr(session, "url_params"):
            return session.url_params
        return None
    except Exception as e:
        print(f"URL 파라미터 로드 중 오류 발생: {e}")
        return None

# 위치 정보를 날씨 API에 적합한 형태로 변환
def convert_location_for_weather(location):
    """
    위치 정보를 날씨 API에 적합한 형태로 변환
    
    Args:
        location: 위치 문자열
        
    Returns:
        str: 변환된 위치 문자열
    """
    # 특정 지역 변환
    location_mapping = {
        "서울": "서울",
        "경기": "경기",
        "인천": "인천",
        "강원": "강원",
        "충북": "충청북도",
        "충남": "충청남도",
        "대전": "대전",
        "경북": "경상북도",
        "경남": "경상남도",
        "대구": "대구",
        "울산": "울산",
        "부산": "부산",
        "전북": "전라북도",
        "전남": "전라남도",
        "광주": "광주",
        "제주": "제주"
    }
    
    # 간단한 변환 시도
    for key, value in location_mapping.items():
        if key in location:
            return value
    
    # 특정 구 처리 (서울)
    seoul_districts = ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"]
    for district in seoul_districts:
        if district in location:
            return "서울"
    
    # 기본값
    return location

# get_schedule_info 함수를 비동기적으로 호출하기 위한 래퍼 함수
@database_sync_to_async
def get_schedule_info_async(date_str):
    """
    일정 정보를 비동기적으로 가져오는 함수
    
    Args:
        date_str: 날짜 문자열
        
    Returns:
        (장소, 동행자) 튜플
    """
    try:
        from calendar_app.get_schedule_info import get_schedule_info
        return get_schedule_info(date_str)
    except Exception as e:
        print(f"일정 정보 비동기 로드 중 오류 발생: {e}")
        return None, None

# ID로 일정 정보를 비동기적으로 가져오는 래퍼 함수 추가
@database_sync_to_async
def get_schedule_by_id_async(schedule_id):
    """
    ID로 일정 정보를 비동기적으로 가져오는 함수
    
    Args:
        schedule_id: 일정 ID
        
    Returns:
        (장소, 동행자) 튜플
    """
    try:
        from calendar_app.get_schedule_info import get_schedule_by_id
        return get_schedule_by_id(schedule_id)
    except Exception as e:
        print(f"ID로 일정 정보 비동기 로드 중 오류 발생: {e}")
        return None, None

# 일정 정보와 채팅 내용을 통합한 향상된 쿼리 생성 함수 (hybrid_retriever와 동일한 방식)
def generateQuery(question, place, companion):
    """
    일정 정보(장소, 동행자)와 채팅 내용을 통합한 쿼리 생성
    
    Args:
        question: 원본 질문
        place: 일정에서 추출한 장소
        companion: 일정에서 추출한 동행자
    
    Returns:
        향상된 쿼리 문자열
    """
    print(f"\n검색 쿼리 생성 중...")
    print(f"- 원본 질문: '{question}'")
    print(f"- 일정 장소: '{place}'")
    print(f"- 일정 동행자: '{companion}'")
    
    # 개선된 쿼리 구성 방식으로 변경 - 장소와 동행자를 질문 앞에 추가
    enhanced_query_parts = []
    
    # 장소 정보가 있으면 먼저 추가 (위치 강조)
    if place:
        enhanced_query_parts.append(f"{place}")
        print(f"- 장소 정보를 쿼리 앞에 추가: '{place}'")
    
    # 동행자 정보가 있으면 그 다음에 추가
    if companion:
        companion_text = ""
        if companion == "연인":
            companion_text = "데이트하기 좋은"
        elif companion == "친구":
            companion_text = "친구와 함께"
        elif companion == "가족":
            companion_text = "가족과 함께"
        elif companion == "혼자":
            companion_text = "혼자서 즐기기 좋은"
        else:
            companion_text = f"{companion}와 함께"
        
        enhanced_query_parts.append(companion_text)
        print(f"- 동행자 정보를 쿼리에 추가: '{companion_text}' (원본: {companion})")
    
    # 원본 질문은 마지막에 추가
    if question:
        enhanced_query_parts.append(question)
        print(f"- 원본 질문 추가: '{question}'")
    
    # 최종 향상된 쿼리
    enhanced_query = " ".join(enhanced_query_parts)
    
    if not enhanced_query:
        enhanced_query = question
        print(f"- 향상된 쿼리 구성 실패, 원본 질문 사용: '{enhanced_query}'")
    else:
        print(f"- 최종 향상된 쿼리: '{enhanced_query}'")
    
    return enhanced_query

async def naver_search(state: GraphState) -> GraphState:
    """네이버 검색 노드
    
    유저의 질문에 대한 실시간 정보를 네이버 검색 API를 통해 검색합니다.
    
    Args:
        state: 현재 그래프 상태
    
    Returns:
        검색 결과가 추가된 그래프 상태
    """
    
    question = state["question"]
    print(f"=== 네이버 검색 시작: '{question}' ===")
    
    try:
        import aiohttp
        
        # 일정 정보 가져오기 (hybrid_retriever와 동일한 방식)
        schedule_place = None
        schedule_companion = None
        
        # 세션 ID 확인 및 URL 파라미터 비동기 로드
        session_id = state.get("session_id", "default_session")
        print(f"현재 세션 ID: {session_id}")
        
        if session_id and session_id != "default_session":
            # 비동기 방식으로 URL 파라미터 로드
            url_params = await get_session_params(session_id)
            print(f"세션에서 가져온 URL 파라미터: {url_params}")
            
            # 일정 ID를 우선적으로 사용하여 일정 정보 가져오기
            if url_params and isinstance(url_params, dict) and 'schedule_id' in url_params:
                schedule_id = url_params.get('schedule_id')
                print(f"URL 파라미터에서 가져온 일정 ID: {schedule_id}")
                
                # 일정 ID로 일정 조회 (비동기 처리)
                if schedule_id:
                    print(f"일정 조회 함수 호출 (비동기): 일정 ID = {schedule_id}")
                    try:
                        # 비동기 래퍼를 통해 함수 호출
                        schedule_place, schedule_companion = await get_schedule_by_id_async(schedule_id)
                        print(f"일정 ID에서 가져온 장소 정보: {schedule_place}")
                        print(f"일정 ID에서 가져온 동행자 정보: {schedule_companion}")
                    except Exception as e:
                        print(f"일정 ID 기반 정보 조회 중 오류 발생: {e}")
            
            # 일정 ID로 정보를 가져오지 못한 경우 날짜로 시도
            if not schedule_place and not schedule_companion:
                # URL 파라미터에서 date 정보 추출
                if url_params and isinstance(url_params, dict) and 'date' in url_params:
                    date_from_session = url_params.get('date')
                    print(f"URL 파라미터에서 가져온 날짜 정보: {date_from_session}")
                    
                    # 날짜 정보로 일정 조회 (비동기 처리)
                    if date_from_session:
                        print(f"일정 조회 함수 호출 (비동기): 날짜 = {date_from_session}")
                        try:
                            # 비동기 래퍼를 통해 함수 호출
                            schedule_place, schedule_companion = await get_schedule_info_async(date_from_session)
                            print(f"일정에서 가져온 장소 정보: {schedule_place}")
                            print(f"일정에서 가져온 동행자 정보: {schedule_companion}")
                        except Exception as e:
                            print(f"일정 정보 조회 중 오류 발생: {e}")
        
        # hybrid_retriever와 동일한 방식으로 향상된 쿼리 생성
        enhanced_query = generateQuery(question, schedule_place, schedule_companion)
        print(f"생성된 향상된 쿼리: '{enhanced_query}'")
        
        # 에이전트를 통해 장소와 카테고리 추출
        print("\n에이전트를 통해 장소와 카테고리 추출 중...")
        query_result = extract_location_and_category(enhanced_query)
        simplified_query = query_result.get("simplified_query")
        extracted_location = query_result.get("location")
        extracted_category = query_result.get("category")
        
        print(f"추출된 장소: {extracted_location}")
        print(f"추출된 카테고리: {extracted_category}")
        
        # 추출된 정보를 기반으로 최종 검색어 구성
        search_terms = []
        
        # 장소 정보 우선순위: 추출된 장소 > 일정 장소 > 구 정보
        if extracted_location:
            # 서울 지역 명시적 추가 (지역 제한)
            if not any(region in extracted_location.lower() for region in ["서울", "강남", "종로", "마포", "홍대"]):
                search_terms.append("서울")
            search_terms.append(extracted_location)
        elif schedule_place:
            if not any(region in schedule_place.lower() for region in ["서울", "강남", "종로", "마포", "홍대"]):
                search_terms.append("서울")
            search_terms.append(schedule_place)
        else:
            # 구 정보가 없으면 서울 추가 (기본값)
            query_info = state.get("query_info", {})
            district = query_info.get("district")
            
            if district:
                district_name = district.replace("서울시 ", "").replace("서울 ", "")
                search_terms.append(district_name)
            else:
                search_terms.append("서울")
                
        # 카테고리 정보 우선순위: 추출된 카테고리 > state의 카테고리
        if extracted_category:
            search_terms.append(extracted_category)
        else:
            query_info = state.get("query_info", {})
            category = query_info.get("category")
            if category:
                search_terms.append(category)
            elif "맛집" in enhanced_query or "음식" in enhanced_query or "식당" in enhanced_query:
                search_terms.append("맛집")
                
        final_query = " ".join(search_terms) if search_terms else (question or "서울 맛집")
        print(f"최종 네이버 검색어: '{final_query}'")
        
        headers = {
            "X-Naver-Client-Id": naver_client_id,
            "X-Naver-Client-Secret": naver_client_secret,
        }
        
        async with aiohttp.ClientSession() as session:
            url = "https://openapi.naver.com/v1/search/local.json"
            params = {
                "query": final_query,
                "display": "10",  # 결과 수 증가
                "start": "1",
                "sort": "random",
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("items", [])
                    print(f"네이버 검색 결과: {len(results)}개")
                    
                    # 결과 필터링: 서울 지역 결과만 포함 (지역 정보가 없는 경우 포함)
                    filtered_results = []
                    for item in results:
                        address = item.get("address", "").lower()
                        if not address or "서울" in address or any(region in address for region in ["종로", "강남", "마포", "홍대"]):
                            filtered_results.append(item)
                    
                    print(f"필터링 후 결과: {len(filtered_results)}개")
                    
                    # 결과가 없으면 원본 결과 사용
                    if not filtered_results:
                        filtered_results = results
                        print("서울 지역 결과가 없어 원본 결과 사용")
                    
                    # 결과가 없으면 기본 검색어로 다시 시도
                    if not filtered_results:
                        print("결과가 없어 기본 검색어 '서울 맛집'으로 재시도")
                        params["query"] = "서울 맛집"
                        async with session.get(url, headers=headers, params=params) as retry_response:
                            if retry_response.status == 200:
                                retry_data = await retry_response.json()
                                filtered_results = retry_data.get("items", [])
                    
                    # 결과 중 최대 3개를 선택 (결과가 3개 미만이면 모두 선택)
                    selected_places = filtered_results[:3] if filtered_results else []
                    
                    # 선택된 장소 정보 가공
                    places = []
                    for item in selected_places:
                        title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                        address = item.get("address", "")
                        road_address = item.get("roadAddress", "")
                        
                        places.append({
                            "title": title,
                            "address": address,
                            "roadAddress": road_address,
                            "category": item.get("category", ""),
                            "description": item.get("description", ""),
                            "link": item.get("link", ""),
                            "mapx": item.get("mapx", ""),
                            "mapy": item.get("mapy", ""),
                            "telephone": item.get("telephone", "")
                        })
                    
                    print(f"최종 선택된 장소: {len(places)}개")
                    for i, place in enumerate(places, 1):
                        print(f"{i}. {place['title']} - {place['address']}")
                    print("=== 네이버 검색 완료 ===\n")
                    
                    return {**state, "naver_results": places}
                else:
                    print(f"네이버 API 오류: 상태 코드 {response.status}")
                    return {**state, "naver_results": []}
    except Exception as e:
        print(f"네이버 API 요청 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return {**state, "naver_results": []} 