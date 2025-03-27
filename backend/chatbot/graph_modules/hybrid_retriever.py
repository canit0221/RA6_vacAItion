import os
import time
import re
import numpy as np
from pathlib import Path
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from .base import GraphState
from .data_loader import load_data
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Tuple
import logging
from django.apps import apps
import asyncio
from channels.db import database_sync_to_async
import json
from datetime import datetime

# 위치 에이전트 모듈 가져오기
from .location_agent import extract_district_from_place, get_place_info

# 로거 설정
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()


def hybrid_retriever(state: GraphState) -> GraphState:
    """하이브리드 검색 노드

    벡터 검색과 키워드 필터링을 결합하여 검색 결과를 제공합니다.
    가중치 기반 검색을 통해 더 정확한 결과를 제공합니다.
    마이너한 장소 추천을 위한 기능을 포함합니다.

    Args:
        state: 현재 그래프 상태

    Returns:
        업데이트된 그래프 상태
    """
    logger.info("=== 하이브리드 검색 시작 ===")
    start_time = time.time()

    question = state["question"]
    is_event = state.get("is_event", False)
    query_info = state.get("query_info", {})

    # 세션 ID 확인 - 기본값은 "default_session"
    session_id = state.get("session_id", "default_session")
    logger.info(f"현재 세션 ID: {session_id}")

    # 세션 객체 가져오기
    ChatSession = apps.get_model("chatbot", "ChatSession")
    ChatMessage = apps.get_model("chatbot", "ChatMessage")

    # 장소 및 동행자 정보 초기화
    schedule_place = None
    schedule_companion = None
    date_from_session = None
    recommended_places = []

    # 세션에서 날짜 정보 가져오기 시도
    try:
        if session_id and session_id != "default_session":
            session = ChatSession.objects.filter(id=session_id).first()

            if session:
                # 세션에서 URL 파라미터 정보 확인
                url_params = session.url_params if hasattr(session, "url_params") else None
                logger.info(f"세션에서 가져온 URL 파라미터: {url_params}")

                # URL 파라미터에서 date 정보 추출 시도
                if url_params and isinstance(url_params, dict) and "date" in url_params:
                    date_from_session = url_params.get("date")
                    logger.info(f"URL 파라미터에서 가져온 날짜 정보: {date_from_session}")

                    # 날짜 정보로 일정 조회 - 필요한 시점에 함수 import
                    if date_from_session:
                        logger.info(f"일정 조회 함수 호출: 날짜 = {date_from_session}")
                        try:
                            # 순환 참조를 방지하기 위해 필요한 시점에 함수 import
                            from calendar_app.get_schedule_info import get_schedule_info

                            schedule_place, schedule_companion = get_schedule_info(date_from_session)
                            logger.info(f"일정에서 가져온 장소 정보: {schedule_place}")
                            logger.info(f"일정에서 가져온 동행자 정보: {schedule_companion}")
                        except Exception as e:
                            logger.error(f"일정 정보 조회 중 오류 발생: {e}")

                # 데이터베이스에서 세션의 추천 장소 목록 가져오기
                recommended_places = session.get_recommended_places() if hasattr(session, "get_recommended_places") else []
                logger.info(f"데이터베이스에서 가져온 이전에 추천한 장소 수: {len(recommended_places)}")
            else:
                logger.info(f"세션 {session_id}를 찾을 수 없어 빈 추천 목록을 사용합니다.")
        else:
            # 세션 정보가 없는 경우 빈 목록 사용
            logger.info("세션 ID가 없어 빈 추천 목록을 사용합니다.")
    except Exception as e:
        logger.error(f"세션 정보 로드 중 오류 발생: {e}")

    # 가중치 설정
    vector_weight = 0.6  # RAG_minor_sep.py와 같은 값으로 변경
    keyword_weight = 0.4

    # 카테고리별 가중치 동적 조정
    category = query_info.get("category")
    if category == "맛집":
        vector_weight = 0.3  # 맛집 카테고리일 때는 키워드 가중치 더 높임
        keyword_weight = 0.7
        logger.debug("맛집 카테고리 감지: 키워드 가중치 상향 조정됨 (0.7)")

    # 쿼리가 없는 경우 검색 건너뛰기
    if not question and not schedule_place:
        logger.warning("쿼리와 일정 장소 정보가 모두 비어있어 검색을 건너뜁니다.")
        return {**state, "retrieved_docs": [], "recommended_places": recommended_places}

    # 카테고리 정보 추출
    district = query_info.get("district")

    logger.info(f"검색어: '{question}'")
    logger.info(f"지역: {district}")
    logger.info(f"카테고리: {category}")
    logger.debug(f"가중치 설정 - 벡터: {vector_weight}, 키워드: {keyword_weight}")

    # 데이터 로드 - 싱글톤 패턴 적용으로 각 요청마다 데이터를 새로 로드하지 않음
    query_type = "event" if is_event else "general"
    docs, vectorstore = load_data(query_type)

    # 로드된 문서 수 로깅
    logger.debug(f"로드된 문서 수: {len(docs)}")

    # 서울시 구 리스트 정의
    districts = [
        "서울 종로구",
        "서울 중구",
        "서울 용산구",
        "서울 성동구",
        "서울 광진구",
        "서울 동대문구",
        "서울 중랑구",
        "서울 성북구",
        "서울 강북구",
        "서울 도봉구",
        "서울 노원구",
        "서울 은평구",
        "서울 서대문구",
        "서울 마포구",
        "서울 양천구",
        "서울 강서구",
        "서울 구로구",
        "서울 금천구",
        "서울 영등포구",
        "서울 동작구",
        "서울 관악구",
        "서울 서초구",
        "서울 강남구",
        "서울 송파구",
        "서울 강동구",
    ]

    # 카테고리 설정
    categories = {
        "카페": [
            "카페",
            "커피",
            "브런치",
            "디저트",
            "티룸",
            "스터디카페",
            "베이커리",
            "아이스크림",
        ],
        "맛집": [
            "맛집",
            "음식점",
            "식당",
            "레스토랑",
            "맛있는",
            "먹거리",
            "밥집",
            "저녁",
            "점심",
            "한식",
            "양식",
            "일식",
            "중식",
        ],
        "공연": ["공연", "연극", "뮤지컬", "오페라", "극장", "공연장", "연주회"],
        "전시": ["전시", "전시회", "갤러리", "미술관", "박물관", "아트", "작품"],
        "콘서트": ["콘서트", "공연장", "라이브", "음악", "페스티벌", "버스킹"],
    }

    # 토큰화 함수 정의
    def tokenize(text: str) -> List[str]:
        """텍스트를 토큰화하는 함수"""
        return re.findall(r"[\w\d가-힣]+", text.lower())

    # 마이너 장소 키워드 그룹 정의 - 확장된 버전
    minor_keyword_groups = {
        "숨은": [
            "숨은",
            "숨겨진",
            "알려지지 않은",
            "비밀",
            "히든",
            "hidden",
            "secret",
            "잘 모르는",
            "남들이 모르는",
            "나만 아는",
            "나만 알고 있는",
            "붐비지 않는",
            "한적한",
            "조용한",
            "언급 안 된",
            "아는 사람만",
            "뜨지 않은",
            "인기 없는",
            "신상",
            "새로운",
            "찾기 힘든",
            "모르는",
            "생소한",
            "덜 알려진",
        ],
        "우연": [
            "우연히",
            "우연한",
            "우연히 발견한",
            "우연히 알게 된",
            "우연히 찾은",
            "우연히 방문한",
            "우연히 가게 된",
            "발견한",
            "찾아낸",
            "마주친",
            "지나가다",
            "우연",
            "찾게 된",
            "발견",
            "들리게 된",
            "알게 된",
            "마주하게 된",
            "발견하게 된",
            "우연의 일치",
        ],
        "로컬": [
            "로컬",
            "현지인",
            "주민",
            "동네",
            "단골",
            "local",
            "근처",
            "주변",
            "지역",
            "골목",
            "골목길",
            "동네 주민",
            "지역 맛집",
            "사람들이 모르는",
            "주민들",
            "동네 사람들",
            "단골손님",
            "토박이",
            "지역 특색",
            "로컬 맛집",
            "지역민",
            "사람",
            "주민 추천",
            "동네 가게",
            "동네 사람들만",
            "동네에서 유명한",
            "지역 주민들이 찾는",
        ],
        "특별한": [
            "특별한",
            "독특한",
            "색다른",
            "이색",
            "이색적인",
            "특이한",
            "유니크한",
            "남다른",
            "기발한",
            "창의적인",
            "특색 있는",
            "새로운 시도",
            "참신한",
            "기존에 없던",
            "새로운 개념",
            "특별함",
            "특별하게",
            "유일한",
            "오직",
            "톡톡 튀는",
            "차별화된",
            "남들과 다른",
            "이색테마",
            "독특함",
        ],
        "감성": [
            "감성",
            "감성적인",
            "분위기",
            "분위기 좋은",
            "예쁜",
            "아름다운",
            "인스타",
            "인스타그램",
            "인스타그래머블",
            "포토",
            "포토존",
            "사진",
            "사진찍기",
            "감성있는",
            "감성장소",
            "감성공간",
            "감성카페",
            "인스타감성",
            "포토스팟",
            "영화같은",
            "그림같은",
            "무드",
            "라이팅",
            "조명",
            "뷰",
            "전망",
        ],
    }

    # 중요 맛집 키워드 확장
    important_food_keywords = [
        "맛집",
        "음식점",
        "식당",
        "레스토랑",
        "맛있는",
        "먹거리",
        "메뉴",
        "요리",
        "맛있게",
        "맛집추천",
        "배고픈",
        "배고파",
        "먹을만한",
        "식사",
        "저녁",
        "점심",
        "브런치",
        "아침",
        "식도락",
        "음식",
        "분위기좋은",
        "유명한",
        "유명 맛집",
        "맛있다",
        "맛집 추천",
        "맛있을",
        "푸짐한",
        "맛있어",
        "맛있게",
        "맛집 여행",
        "맛있어요",
        "맛있다고",
        "추천 맛집",
        "인기 맛집",
        "인기",
        "인기있는",
        "맛도",
        "맛도 있고",
        "데이트",
        "데이트코스",
        "가족",
        "가족모임",
        "회식",
    ]
    
    # 향상된 쿼리 생성 함수
    def generateQuery(question, place, companion):
        logger.info(f"\n검색 쿼리 생성 중...")
        logger.info(f"- 원본 질문: '{question}'")
        logger.info(f"- 일정 장소: '{place}'")
        logger.info(f"- 일정 동행자: '{companion}'")

        # 개선된 쿼리 구성 방식으로 변경 - 장소와 동행자를 질문 앞에 추가
        enhanced_query_parts = []

        # 장소 정보가 있으면 먼저 추가 (위치 강조)
        if place:
            enhanced_query_parts.append(f"{place}")
            logger.info(f"- 장소 정보를 쿼리 앞에 추가: '{place}'")

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
            logger.info(f"- 동행자 정보를 쿼리에 추가: '{companion_text}' (원본: {companion})")

        # 원본 질문은 마지막에 추가
        if question:
            enhanced_query_parts.append(question)
            logger.info(f"- 원본 질문 추가: '{question}'")

        # 최종 향상된 쿼리
        enhanced_query = " ".join(enhanced_query_parts)

        if not enhanced_query:
            enhanced_query = question
            logger.info(f"- 향상된 쿼리 구성 실패, 원본 질문 사용: '{enhanced_query}'")
        else:
            logger.info(f"- 최종 향상된 쿼리: '{enhanced_query}'")

        return enhanced_query

    # 카테고리 추출 함수
    def extract_category(query: str) -> str:
        """쿼리에서 카테고리 키워드 추출"""
        query = query.lower()
        for cat_name, keywords in categories.items():
            if any(keyword in query for keyword in keywords):
                return cat_name
        return None

    # 구 이름 추출 함수
    def extract_district(query: str) -> str:
        """쿼리에서 서울시 구 이름을 추출"""
        for district in districts:
            if district in query:
                return district

            # '서울 ' 접두사 없이 구 이름만 검색
            district_name = district.replace("서울 ", "")
            if district_name in query and "구" in district_name:
                return district
        return None

    # 문서에서 마이너 키워드 점수 계산 함수 (RAG_minor_sep.py 방식으로 수정)
    def check_minor_keywords_in_doc(doc_content: str) -> Tuple[float, List[str]]:
        """
        문서 내용에서 마이너 키워드 존재 여부 확인 및 점수 계산
        반환값: (점수, 발견된 키워드 유형 리스트)
        """
        score = 0.0
        doc_content = doc_content.lower()
        found_keyword_types = []

        for keyword_type, keywords in minor_keyword_groups.items():
            if any(keyword in doc_content for keyword in keywords):
                if keyword_type in ["숨은", "우연", "로컬", "특별한", "감성"]:
                    score += 0.4  # RAG_minor_sep.py와 같이 0.4로 변경
                    found_keyword_types.append(keyword_type)

        return min(score, 1.0), found_keyword_types  # 최대 점수는 1.0

    # 쿼리에서 마이너 키워드 타입 추출 함수 (RAG_minor_sep.py의 _extract_minor_type 함수와 유사하게 구현)
    def extract_minor_type(query: str) -> List[str]:
        """쿼리에서 마이너 추천 타입 추출"""
        query = query.lower()
        minor_types = []
        
        for minor_type, keywords in minor_keyword_groups.items():
            if any(keyword in query for keyword in keywords):
                minor_types.append(minor_type)
        
        return minor_types

    # 벡터 점수 계산 함수 (RAG_minor_sep.py의 _calculate_vector_scores 함수와 유사하게 구현)
    def calculate_vector_scores(query: str, filtered_docs: List) -> List[float]:
        """벡터 유사도 점수 계산"""
        try:
            query_embedding = np.array(vectorstore.embedding_function.embed_query(query)).reshape(1, -1)
            
            # 문서 임베딩을 검색하고 거리 계산
            if hasattr(vectorstore, 'index'):
                # FAISS 인덱스가 있는 경우
                doc_indices = [i for i, doc in enumerate(docs) if doc in filtered_docs]
                if doc_indices:
                    # 필터링된 문서 인덱스만 사용
                    D, indices = vectorstore.index.search(query_embedding, min(len(doc_indices), 50))
                    vector_scores = [1 - (d / (np.max(D[0]) + 1e-6)) for d in D[0]]
                    
                    # 인덱스와 점수 매핑
                    scores_map = {}
                    for idx, score in zip(indices[0], vector_scores):
                        if idx < len(docs) and docs[idx] in filtered_docs:
                            doc_idx = filtered_docs.index(docs[idx])
                            scores_map[doc_idx] = score
                    
                    # 필터링된 문서 순서에 맞게 점수 재정렬
                    final_scores = []
                    for i in range(len(filtered_docs)):
                        final_scores.append(scores_map.get(i, 0.5))  # 기본값 0.5
                    
                    return final_scores
            
            # 직접 유사도 계산 (fallback)
            logger.info("직접 벡터 유사도 계산 수행")
            vectors = vectorstore.similarity_search_with_score(query, k=len(filtered_docs))
            scores = [1.0 - score for _, score in vectors]
            return scores
            
        except Exception as e:
            logger.error(f"벡터 점수 계산 중 오류 발생: {str(e)}")
            # 오류 발생 시 동일한 점수 반환
            return [0.5] * len(filtered_docs)

    # 키워드 점수 계산 함수 (RAG_minor_sep.py의 _calculate_keyword_scores 함수와 유사하게 구현)
    def calculate_keyword_scores(query: str, filtered_docs: List) -> List[float]:
        """BM25 기반 키워드 매칭 점수 계산"""
        tokenized_query = tokenize(query)
        filtered_tokenized_docs = [tokenize(doc.page_content) for doc in filtered_docs]
        
        # BM25 객체 초기화
        try:
            filtered_bm25 = BM25Okapi(filtered_tokenized_docs)
            
            # 기본 키워드 점수 계산
            base_scores = filtered_bm25.get_scores(tokenized_query)
            
            # 문서 내용의 마이너 키워드 점수 계산
            minor_scores = []
            for doc in filtered_docs:
                minor_score, _ = check_minor_keywords_in_doc(doc.page_content)
                minor_scores.append(minor_score)
            
            # 최종 점수 계산 (BM25 점수 * 0.5 + 마이너 키워드 점수 * 0.5)
            final_scores = [
                base_score * 0.5 + minor_score * 0.5
                for base_score, minor_score in zip(base_scores, minor_scores)
            ]
            
            # 점수 정규화
            if final_scores:
                max_score = max(final_scores) + 1e-6
                normalized_scores = [score / max_score for score in final_scores]
                return normalized_scores
            return [0.0] * len(filtered_docs)
            
        except Exception as e:
            logger.error(f"키워드 점수 계산 중 오류 발생: {str(e)}")
            # 오류 발생 시 마이너 점수만 반환
            return minor_scores if 'minor_scores' in locals() else [0.0] * len(filtered_docs)

    # 문서 관련성 계산 함수 (RAG_minor_sep.py의 get_relevant_documents 함수와 유사하게 구현)
    def get_relevant_documents(query: str, recommended_places: List[str] = []) -> List:
        """최종적으로 검색된 문서들을 키워드 스코어까지 반영하여 정렬"""
        search_start = time.time()
        logger.info("\n=== 검색 프로세스 시작 ===")
        logger.info(f"입력 쿼리: {query}")
        logger.info(f"이전 추천 장소 수: {len(recommended_places)}")

        # 1. 쿼리에서 구 이름과 카테고리 추출
        extracted_district = extract_district(query) or district
        extracted_category = extract_category(query) or category
        minor_types = extract_minor_type(query)

        # 위치 에이전트를 사용하여 장소 기반 구 정보 추출
        place_info = get_place_info(query)
        place_name = place_info.get("place")
        agent_district = place_info.get("district")

        if agent_district:
            logger.info(f"✅ 에이전트에서 추출한 장소: {place_name}")
            logger.info(f"✅ 에이전트에서 추출한 구 정보: {agent_district}")
            extracted_district = agent_district  # 에이전트에서 추출한 구 정보 우선 적용
        
        if extracted_district:
            logger.info(f"\n1. 구 이름 추출: '{extracted_district}' 발견")
            if extracted_category:
                logger.info(f"2. 카테고리 추출: '{extracted_category}' 발견")
            if minor_types and extracted_category not in ["전시", "공연", "콘서트"]:
                logger.info(f"3. 마이너 키워드 추출: {', '.join(minor_types)} 발견")
            district_name = extracted_district.replace("서울 ", "")

            # 3. 키워드 기반 필터링
            keyword_start = time.time()
            logger.info("\n4. 키워드 기반 필터링 중...")

            # 1단계: 구 이름으로 필터링
            district_filtered_docs = []
            for doc in docs:
                content = doc.page_content.lower()
                location = doc.metadata.get("location", "").lower()
                address = doc.metadata.get("address", "").lower()
                if (extracted_district.lower() in content or district_name.lower() in content or
                    extracted_district.lower() in location or district_name.lower() in location or
                    extracted_district.lower() in address or district_name.lower() in address):
                    district_filtered_docs.append(doc)
            
            logger.info(f"   - 구 이름으로 필터링된 문서 수: {len(district_filtered_docs)}개")

            if len(district_filtered_docs) == 0:
                logger.info("   - 구 관련 문서를 찾지 못했습니다. 일반 벡터 검색을 수행합니다.")
                return vectorstore.similarity_search(query, k=3)

            # 2단계: 마이너 키워드로 필터링 (이벤트가 아닐 때만)
            filtered_docs = district_filtered_docs
            if extracted_category not in ["전시", "공연", "콘서트"]:
                minor_filtered_docs = []
                for doc in district_filtered_docs:
                    content = doc.page_content.lower()
                    has_minor_keyword = False
                    found_keywords = []
                    for keyword_type, keywords in minor_keyword_groups.items():
                        if any(keyword in content for keyword in keywords):
                            has_minor_keyword = True
                            found_keywords.append(keyword_type)
                    if has_minor_keyword:
                        minor_filtered_docs.append(doc)
                
                logger.info(f"   - 마이너 키워드로 필터링 후 문서 수: {len(minor_filtered_docs)}개")
                if len(minor_filtered_docs) >= 3:  # 충분한 결과가 있을 때만 적용
                    filtered_docs = minor_filtered_docs
                else:
                    logger.info("   - 마이너 키워드가 포함된 문서를 충분히 찾지 못했습니다. 구 기반 필터링 결과로 계속 진행합니다.")
            
            # 3단계: 이미 추천한 장소 필터링
            logger.info("\n추천 이력 기반 필터링 중...")
            non_recommended_docs = []
            excluded_count = 0

            for doc in filtered_docs:
                # 장소 식별자 생성
                place_id = doc.metadata.get("id", "")
                place_name = doc.metadata.get("name", "")
                place_identifier = ""

                if place_id and place_name:
                    place_identifier = f"{place_id}:{place_name}"
                elif place_id:
                    place_identifier = place_id
                elif place_name:
                    place_identifier = place_name
                else:
                    # 콘텐츠 해시의 일부 사용
                    place_identifier = str(hash(doc.page_content))[:10]

                # 이미 추천한 장소인지 확인
                if place_identifier not in recommended_places:
                    non_recommended_docs.append(doc)
                else:
                    excluded_count += 1

            logger.info(f"   - 이미 추천된 {excluded_count}개 장소 제외 후 {len(non_recommended_docs)}개 문서 남음")
            
            # 필터링된 문서가 3개 미만인 경우 경고
            if len(non_recommended_docs) < 3:
                logger.warning("   - 경고: 추천할 새로운 장소가 3개 미만입니다.")
                
            # 필터링된 문서가 없으면 구 기반 필터링 결과 사용
            if len(non_recommended_docs) == 0:
                logger.info("   - 추천할 새로운 장소가 없어 구 기반 필터링 결과 사용")
                non_recommended_docs = district_filtered_docs
            
            # 4. 하이브리드 점수 계산
            scoring_start = time.time()
            logger.info("\n5. 하이브리드 점수 계산 중...")

            # 벡터 유사도 점수 계산
            logger.info("   - 벡터 점수 계산 중...")
            vector_scores = calculate_vector_scores(query, non_recommended_docs)

            # 키워드 매칭 점수 계산
            logger.info("   - 키워드 점수 계산 중...")
            keyword_scores = calculate_keyword_scores(query, non_recommended_docs)

            # 최종 점수 계산 (가중 평균)
            final_scores = [
                (doc, vector_weight * vs + keyword_weight * ks)
                for doc, vs, ks in zip(non_recommended_docs, vector_scores, keyword_scores)
            ]

            # 점수 기준 정렬
            final_scores.sort(key=lambda x: x[1], reverse=True)
            top_k = min(3, len(final_scores))  # 최대 3개 결과로 제한
            top_results = [doc for doc, _ in final_scores[:top_k]]

            # 선택된 문서들의 마이너 키워드 출력 (이벤트가 아닐 때만)
            if extracted_category not in ["전시", "공연", "콘서트"]:
                logger.info("\n=== 선택된 문서의 마이너 키워드 ===")
                for i, doc in enumerate(top_results, 1):
                    keywords_found = []
                    doc_content = doc.page_content.lower()
                    logger.info(f"\n문서 {i} 분석:")
                    for group, keywords in minor_keyword_groups.items():
                        found_keywords = [kw for kw in keywords if kw in doc_content]
                        if found_keywords:
                            keywords_found.append(group)
                            logger.info(f"   - {group} 키워드 발견: {', '.join(found_keywords[:3])}")
                    if keywords_found:
                        logger.info(f"   => 최종 발견된 키워드 유형: {', '.join(keywords_found)}")
                        # 마이너 키워드가 쿼리와 일치하는 경우 강조
                        matching_types = set(keywords_found) & set(minor_types)
                        if matching_types:
                            logger.info(f"   ⭐ 쿼리와 일치하는 키워드: {', '.join(matching_types)}")
                    else:
                        logger.info("   => 마이너 키워드가 발견되지 않았습니다.")

            scoring_time = time.time() - scoring_start
            total_time = time.time() - search_start

            logger.info(f"\n=== 검색 시간 분석 ===")
            logger.info(f"키워드 필터링 시간: {keyword_start - search_start:.2f}초")
            logger.info(f"하이브리드 점수 계산 시간: {scoring_time:.2f}초")
            logger.info(f"전체 검색 시간: {total_time:.2f}초")
            logger.info(f"   - 최종 검색 결과: {len(top_results)}개 문서")

            # 추천 장소 식별자 생성 및 반환
            new_recommended_places = []
            for doc in top_results:
                place_id = doc.metadata.get("id", "")
                place_name = doc.metadata.get("name", "")
                if place_id and place_name:
                    place_identifier = f"{place_id}:{place_name}"
                elif place_id:
                    place_identifier = place_id
                elif place_name:
                    place_identifier = place_name
                else:
                    place_identifier = str(hash(doc.page_content))[:10]
                new_recommended_places.append(place_identifier)
            
            logger.info(f"추가된 새 추천 장소 ID: {new_recommended_places}")

            return top_results, new_recommended_places

        logger.info("   - 구 이름이 감지되지 않았습니다. 일반 벡터 검색을 수행합니다.")
        basic_results = vectorstore.similarity_search(query, k=3)
        new_recommended_places = [str(hash(doc.page_content))[:10] for doc in basic_results]
        return basic_results, new_recommended_places

    # 1. 쿼리 분석
    # 쿼리에서 구 정보가 없는 경우, query_info에서 가져온 값 사용
    if not district:
        district = extract_district(question)

    # 카테고리 정보가 없는 경우, 쿼리에서 추출
    if not category:
        category = extract_category(question)

    # 마이너 키워드 유형 추출
    minor_types = extract_minor_type(question)
    
    logger.info(f"최종 검색 조건 - 지역: {district}, 카테고리: {category}, 마이너 키워드: {', '.join(minor_types) if minor_types else '없음'}")
    
    # 강화된 쿼리 생성
    enhanced_query = generateQuery(question, schedule_place, schedule_companion)
    logger.info(f"생성된 향상된 쿼리: '{enhanced_query}'")

    # RAG_minor_sep.py 스타일의 get_relevant_documents 함수 사용하여 검색 수행
    retrieved_docs, new_recommended_places = get_relevant_documents(enhanced_query, recommended_places)

    # 세션에 새로 추가된 장소들을 저장
    if session_id and session_id != "default_session" and new_recommended_places:
        try:
            session = ChatSession.objects.filter(id=session_id).first()
            if session and hasattr(session, "add_recommended_place"):
                # 새로 추천된 장소 추가
                for place in new_recommended_places:
                    session.add_recommended_place(place)
                logger.info(f"세션 {session_id}에 {len(new_recommended_places)}개의 새로운 장소가 저장되었습니다.")
            else:
                logger.info(f"세션 {session_id}을 찾을 수 없어 추천 장소를 저장하지 못했습니다.")
        except Exception as e:
            logger.error(f"추천 장소 저장 중 오류 발생: {e}")

    # 처리 시간 출력
    total_time = time.time() - start_time
    logger.info(f"\n=== 검색 완료 (총 {total_time:.2f}초) ===")
    
    # 현재까지 추천한 장소 목록
    all_recommended_places = recommended_places + new_recommended_places if recommended_places else new_recommended_places
    logger.info(f"현재까지 추천한 장소 수: {len(all_recommended_places)}")

    return {**state, "retrieved_docs": retrieved_docs, "recommended_places": all_recommended_places}
