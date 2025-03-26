import os
import time
import re
import numpy as np
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from .base import GraphState
from .data_loader import load_data
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Tuple
from django.apps import apps
import asyncio
from channels.db import database_sync_to_async
import json
from datetime import datetime

# 위치 에이전트 모듈 가져오기
from .location_agent import extract_district_from_place, get_place_info

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
    print("\n=== 하이브리드 검색 노드 진입점 ===")

    # 디버깅 정보 출력 제거

    print("=== 하이브리드 검색 시작 ===")
    start_time = time.time()

    question = state["question"]
    is_event = state.get("is_event", False)
    query_info = state.get("query_info", {})

    # 세션 ID 확인 - 기본값은 "default_session"
    session_id = state.get("session_id", "default_session")
    print(f"현재 세션 ID: {session_id}")

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
                url_params = (
                    session.url_params if hasattr(session, "url_params") else None
                )
                print(f"세션에서 가져온 URL 파라미터: {url_params}")

                # URL 파라미터에서 date 정보 추출 시도
                if url_params and isinstance(url_params, dict) and "date" in url_params:
                    date_from_session = url_params.get("date")
                    print(f"URL 파라미터에서 가져온 날짜 정보: {date_from_session}")

                    # 날짜 정보로 일정 조회 - 필요한 시점에 함수 import
                    if date_from_session:
                        print(f"일정 조회 함수 호출: 날짜 = {date_from_session}")
                        try:
                            # 순환 참조를 방지하기 위해 필요한 시점에 함수 import
                            from calendar_app.get_schedule_info import get_schedule_info

                            schedule_place, schedule_companion = get_schedule_info(
                                date_from_session
                            )
                            print(f"일정에서 가져온 장소 정보: {schedule_place}")
                            print(f"일정에서 가져온 동행자 정보: {schedule_companion}")
                        except Exception as e:
                            print(f"일정 정보 조회 중 오류 발생: {e}")

                # 데이터베이스에서 세션의 추천 장소 목록 가져오기
                recommended_places = session.get_recommended_places()
                print(
                    f"데이터베이스에서 가져온 이전에 추천한 장소 수: {len(recommended_places)}"
                )
            else:
                print(f"세션 {session_id}를 찾을 수 없어 빈 추천 목록을 사용합니다.")
        else:
            # 세션 정보가 없는 경우 빈 목록 사용
            print("세션 ID가 없어 빈 추천 목록을 사용합니다.")
    except Exception as e:
        print(f"세션 정보 로드 중 오류 발생: {e}")

    # 가중치 설정
    vector_weight = 0.4
    keyword_weight = 0.6

    # 카테고리별 가중치 동적 조정
    category = query_info.get("category")
    if category == "맛집":
        vector_weight = 0.2  # 맛집 카테고리일 때는 키워드 가중치 더 높임
        keyword_weight = 0.8
        print("맛집 카테고리 감지: 키워드 가중치 상향 조정됨 (0.8)")

    # 쿼리가 없는 경우 검색 건너뛰기
    if not question and not schedule_place:
        print("쿼리와 일정 장소 정보가 모두 비어있어 검색을 건너뜁니다.")
        return {**state, "retrieved_docs": [], "recommended_places": recommended_places}

    # 초기 카테고리 정보 추출
    district = query_info.get("district")

    print(f"검색어: '{question}'")
    print(f"지역: {district}")
    print(f"카테고리: {category}")
    print(f"가중치 설정 - 벡터: {vector_weight}, 키워드: {keyword_weight}")

    # 데이터 로드
    query_type = "event" if is_event else "general"
    docs, vectorstore = load_data(query_type)

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

    # 마이너 키워드 그룹 설정
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
        ],
        "우연": [
            "우연히",
            "우연한",
            "우연히 발견한",
            "우연히 알게 된",
            "우연히 찾은",
            "우연히 방문한",
            "우연히 가게 된",
        ],
        "로컬": ["로컬", "현지인", "주민", "동네", "단골", "local", "근처", "주변"],
    }

    # 카테고리 추출 함수
    def extract_category(query: str) -> str:
        """쿼리에서 카테고리 키워드 추출"""
        query = query.lower()
        for cat_name, keywords in categories.items():
            if any(keyword in query for keyword in keywords):
                return cat_name
        return None

    # 문서에서 마이너 키워드 점수 계산 함수
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
                if keyword_type in [
                    "숨은",
                    "우연",
                    "로컬",
                ]:  # 세 가지 키워드 그룹만 높은 가중치
                    score += 0.4  # 각 그룹당 0.4의 가중치
                    found_keyword_types.append(keyword_type)

        return min(score, 1.0), found_keyword_types  # 최대 점수는 1.0

    # 향상된 쿼리 생성 - URL 파라미터 정보만 활용하도록 간소화
    def generateQuery(question, place, companion):
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
            print(
                f"- 동행자 정보를 쿼리에 추가: '{companion_text}' (원본: {companion})"
            )

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

    # 하이브리드 검색 함수 - URL 파라미터에서 추출한 정보만 사용하도록 수정
    def retrieve(question, place, companion, recommended_places=None):
        print("\n=== 향상된 쿼리 생성 시작 ===")
        print(f"일정에서 추출한 장소: {place}")
        print(f"일정에서 추출한 동행자: {companion}")

        # 향상된 쿼리 생성 (일정 정보 기반)
        enhanced_query = generateQuery(question, place, companion)

        print(f"생성된 향상된 쿼리: '{enhanced_query}'")
        print("=== 향상된 쿼리 생성 완료 ===\n")

        # query_info와 category 변수 가져오기
        category = query_info.get("category")
        is_event = state.get("is_event", False)

        # 벡터 검색 가중치 설정
        vector_weight = 0.4
        keyword_weight = 0.6

        # 카테고리별 가중치 동적 조정
        if category == "맛집":
            vector_weight = 0.2  # 맛집 카테고리일 때는 키워드 가중치 더 높임
            keyword_weight = 0.8
            print("맛집 카테고리 감지: 키워드 가중치 상향 조정됨 (0.8)")

        # 위치 에이전트를 사용하여 장소 기반 구 정보 추출
        print("\n에이전트를 통해 장소 및 구 정보 추출 중...")
        place_info = get_place_info(enhanced_query)
        place_name = place_info.get("place")
        district = place_info.get("district")

        if district:
            print(f"✅ 에이전트에서 추출한 장소: {place_name}")
            print(f"✅ 에이전트에서 추출한 구 정보: {district}")
        else:
            # 에이전트에서 구 정보를 추출하지 못한 경우 query_info의 district 사용
            district = query_info.get("district")
            print(
                f"❌ 에이전트에서 구 정보를 추출하지 못했습니다. 기존 정보 사용: {district}"
            )

        # 카테고리 정보가 없는 경우, 쿼리에서 추출
        if not category:
            category = extract_category(question)
            # 향상된 쿼리에서도 카테고리 추출 시도
            if not category:
                category = extract_category(enhanced_query)

        print(
            f"최종 검색 조건 - 지역: {district}, 카테고리: {category}, 장소: {place}, 동행자: {companion}"
        )

        # 2. 검색 순서 변경: 메타데이터 기반 필터링 먼저 수행
        print("\n2. 메타데이터 기반 필터링 수행 중...")

        # 모든 문서를 대상으로 필터링 시작
        filtered_docs = docs

        # 2.1. 지역 기반 필터링 (에이전트에서 추출한 구 정보를 사용)
        if district:
            print(f"   - 구 정보 '{district}' 기반 필터링 수행 중...")
            district_name = district.replace("서울시 ", "").replace("서울 ", "")
            location_filtered_docs = []
            for doc in filtered_docs:
                content = doc.page_content.lower()
                metadata_location = doc.metadata.get("location", "").lower()
                metadata_address = doc.metadata.get("address", "").lower()

                # 지역명이 콘텐츠나 메타데이터에 포함되어 있는지 확인
                if (
                    district.lower() in content
                    or district_name.lower() in content
                    or district.lower() in metadata_location
                    or district_name.lower() in metadata_location
                    or district.lower() in metadata_address
                    or district_name.lower() in metadata_address
                ):
                    location_filtered_docs.append(doc)

            # 필터링 결과가 적어도 해당 구 내의 결과만 유지 (확장하지 않음)
            if len(location_filtered_docs) < 3:
                print(
                    f"   - 지역 필터링 결과가 적습니다 ({len(location_filtered_docs)}개). 해당 구 내의 결과만 유지합니다."
                )

            filtered_docs = location_filtered_docs
            print(f"   - 지역 필터링 결과: {len(filtered_docs)}개 문서")
        else:
            print("   - 구 정보가 없어 모든 문서 사용")

        # 2.2. 카테고리 기반 필터링
        print("   - 카테고리 기반 필터링 수행 중...")
        if not is_event and category:
            category_keywords = categories.get(category, [])
            category_filtered_docs = []

            for doc in filtered_docs:
                content = doc.page_content.lower()
                if any(keyword in content for keyword in category_keywords):
                    category_filtered_docs.append(doc)

            # 필터링 결과가 있으면 적용
            if category_filtered_docs:
                filtered_docs = category_filtered_docs
                print(f"   - 카테고리 필터링 결과: {len(filtered_docs)}개 문서")
            else:
                print(f"   - 카테고리 '{category}' 필터링 결과가 없어 이전 결과 유지")
        elif is_event:
            print("   - 이벤트 검색이므로 카테고리 필터링 생략")
        else:
            print("   - 카테고리 필터가 없어 이전 결과 유지")

        # 3. 이미 추천한 장소 필터링 (메타데이터에서 장소 식별자 추출)
        print("\n3. 이미 추천한 장소 제외 중...")
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

        print(
            f"   - 이미 추천된 {excluded_count}개 장소 제외 후 {len(non_recommended_docs)}개 문서 남음"
        )

        # 필터링된 문서 수가 너무 적으면 (3개 미만) 메시지 출력
        if len(non_recommended_docs) < 3:
            print("   - 경고: 추천할 새로운 장소가 거의 없습니다.")

        # 4. 벡터 검색 수행 (필터링된 문서만 대상으로)
        vector_start = time.time()
        print("\n4. 벡터 검색 실행 중...")

        # 필터링된 문서가 없으면 원본 문서 사용
        docs_to_search = non_recommended_docs if non_recommended_docs else docs

        # 카테고리가 일반 카테고리이고 이벤트가 아닌 경우, 마이너 키워드로 필터링 수행
        if not is_event and category not in ["전시", "공연", "콘서트"]:
            print("   - 마이너 키워드 필터링 수행 중...")
            minor_filtered_docs = []
            for doc in docs_to_search:
                content = doc.page_content.lower()
                has_minor_keyword = False
                found_keywords = []
                for keyword_type, keywords in minor_keyword_groups.items():
                    if any(keyword in content for keyword in keywords):
                        has_minor_keyword = True
                        found_keywords.append(keyword_type)
                if has_minor_keyword:
                    minor_filtered_docs.append(doc)

            print(
                f"   - 마이너 키워드로 필터링 후 문서 수: {len(minor_filtered_docs)}개"
            )
            if (
                len(minor_filtered_docs) >= 3
            ):  # 충분한 문서가 있는 경우에만 마이너 필터링 결과 사용
                docs_to_search = minor_filtered_docs
            else:
                print("   - 마이너 키워드가 포함된 문서가 충분하지 않아 이전 결과 유지")

        # 벡터 검색 수행
        docs_and_scores = []

        # 벡터 검색할 문서가 충분히 있는지 확인
        if len(docs_to_search) >= 3:
            try:
                # 검색 문서 수 증가 (15 -> 30)
                search_k = min(30, len(docs_to_search))

                # 향상된 쿼리를 검색어로 사용
                search_query = enhanced_query
                print(f"   - 벡터 검색 쿼리: '{search_query}'")
                print(f"   - 검색 대상 문서 수: {len(docs_to_search)}개")

                # 검색 쿼리의 세부 구성요소 로그
                print(f"   - 쿼리 구성 요소:")
                if place:
                    print(f"      - 장소: {place}")
                if companion:
                    print(f"      - 동행자: {companion}")
                if question:
                    print(f"      - 질문: {question}")

                # PostgreSQL 데이터베이스에서 직접 벡터 검색
                try:
                    # Django ORM으로 pgvector 쿼리 실행
                    from chatbot.models import NaverBlog, NaverBlogFaiss
                    from django.db import connection
                    import numpy as np

                    # 임베딩 모델 초기화 (한 번만)
                    embeddings = OpenAIEmbeddings()

                    # 쿼리 텍스트 임베딩 생성
                    print(f"   - 쿼리 임베딩 생성 중: '{search_query}'")
                    query_embedding = embeddings.embed_query(search_query)

                    # 검색 대상 문서의 line_number 목록 추출
                    line_numbers = []
                    for doc in docs_to_search:
                        if "line_number" in doc.metadata:
                            line_numbers.append(doc.metadata["line_number"])

                    # 임베딩 벡터로 검색을 수행할 NaverBlogFaiss 항목 조회
                    selected_docs = []

                    # 필터링된 문서가 있는 경우
                    if line_numbers:
                        # 벡터 유사도 검색을 SQL로 직접 실행 (pgvector 활용)
                        with connection.cursor() as cursor:
                            # 쿼리 문자열 구성 - line_number 기준 필터링 및 벡터 유사도 검색
                            placeholders = ", ".join(["%s"] * len(line_numbers))
                            query = f"""
                            SELECT nb.line_number, nb.page_content, nb.url, 
                                   1 - (nbf.embedding <=> %s::vector) as similarity
                            FROM chatbot_naverblogfaiss nbf
                            JOIN chatbot_naverblog nb ON nbf.line_number_id = nb.line_number
                            WHERE nb.line_number IN ({placeholders})
                            ORDER BY similarity DESC
                            LIMIT {search_k}
                            """

                            # 파라미터 구성: 쿼리 임베딩 + line_number 리스트
                            params = [query_embedding] + line_numbers

                            try:
                                cursor.execute(query, params)
                                results = cursor.fetchall()

                                # 결과 처리
                                for row in results:
                                    line_number, page_content, url, similarity = row

                                    # Document 객체 생성 (원본 문서와 동일한 형태로)
                                    doc = Document(
                                        page_content=page_content,
                                        metadata={
                                            "line_number": line_number,
                                            "url": url,
                                            "type": "general",
                                        },
                                    )

                                    # 유사도 점수와 함께 문서 저장
                                    # 유사도 점수는 이미 1에서 거리를 뺀 값이므로 그대로 사용
                                    docs_and_scores.append((doc, 1.0 - similarity))

                                print(
                                    f"   - pgvector 검색 성공: {len(docs_and_scores)}개 결과"
                                )

                            except Exception as e:
                                print(f"   - pgvector 검색 실패: {str(e)}")
                                # 실패 시 필터링된 문서 전체 사용 (점수 1.0으로 설정)
                                docs_and_scores = [
                                    (doc, 1.0) for doc in docs_to_search[:search_k]
                                ]
                    else:
                        # 필터링된 문서가 없는 경우 원본 문서 사용
                        print("   - 필터링된 문서의 line_number가 없음")
                        docs_and_scores = [
                            (doc, 1.0) for doc in docs_to_search[:search_k]
                        ]

                except Exception as e:
                    print(f"   - PostgreSQL 벡터 검색 오류: {str(e)}")
                    # 실패 시 원본 벡터스토어 사용

                    # 벡터스토어를 사용하여 필터링된 문서에서만 검색
                    print("   - 대체 방법으로 원본 벡터스토어 사용")
                    try:
                        docs_and_scores = vectorstore.similarity_search_with_score(
                            search_query, k=search_k
                        )
                        print(f"   - 벡터 검색 결과: {len(docs_and_scores)}개 문서")
                    except Exception as e2:
                        print(f"   - 벡터스토어 대체 검색도 실패: {str(e2)}")
                        # 오류 발생 시 점수 1.0으로 모든 문서 사용
                        docs_and_scores = [
                            (doc, 1.0) for doc in docs_to_search[:search_k]
                        ]

            except Exception as e:
                print(f"   - 벡터 검색 오류: {str(e)}")
                # 오류 발생 시 점수 1.0으로 모든 문서 사용
                docs_and_scores = [(doc, 1.0) for doc in docs_to_search[:search_k]]
        else:
            print("   - 필터링된 문서가 너무 적어 벡터 검색 스킵")
            # 문서가 너무 적으면 벡터 검색 없이 모든 문서 사용
            docs_and_scores = [(doc, 1.0) for doc in docs_to_search]

        # 거리를 유사도로 변환
        docs_with_scores = []
        for doc, score in docs_and_scores:
            vector_score = 1.0 - score  # 거리를 유사도로 변환
            docs_with_scores.append((doc, vector_score))

        # 5. 마이너 키워드 점수 계산 및 최종 결과 생성
        print("\n5. 마이너 키워드 점수 계산 중...")
        final_results = []

        for doc, vector_score in docs_with_scores:
            # 문서에서 마이너 키워드 점수 계산
            minor_score, found_types = check_minor_keywords_in_doc(doc.page_content)

            # 최종 점수 계산
            final_score = vector_score * vector_weight + minor_score * keyword_weight

            # 결과에 추가 정보 포함
            final_results.append(
                {
                    "doc": doc,
                    "score": final_score,
                    "vector_score": vector_score,
                    "minor_score": minor_score,
                    "minor_types": found_types,
                }
            )

        # 점수 기준 정렬
        final_results.sort(key=lambda x: x["score"], reverse=True)

        # 최종 결과 정리 및 장소 식별자 추출
        print("\n6. 최종 결과 정리 중...")
        new_recommended_places = []

        # 상위 결과 선택 (최대 10개로 증가)
        top_k = min(10, len(final_results))
        selected_results = final_results[:top_k]

        # 결과 출력 및 새로운 추천 장소 식별자 추출
        print(f"\n=== 상위 {top_k}개 결과 ===")
        for i, result in enumerate(selected_results, 1):
            doc = result["doc"]
            minor_types = result["minor_types"]

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
                place_identifier = str(hash(doc.page_content))[:10]

            # 새로운 추천 장소 목록에 추가
            new_recommended_places.append(place_identifier)

            # 문서 내용 요약 (첫 50자)
            content_preview = (
                doc.page_content[:50] + "..."
                if len(doc.page_content) > 50
                else doc.page_content
            )

            print(f"\n{i}. 문서 (점수: {result['score']:.4f}):")
            print(f"   - 내용 미리보기: {content_preview}")
            print(
                f"   - 벡터 점수: {result['vector_score']:.4f}, 마이너 점수: {result['minor_score']:.4f}"
            )

            if minor_types:
                print(f"   - 발견된 마이너 키워드 유형: {', '.join(minor_types)}")
                # 마이너 키워드 예시 추출 및 출력
                for keyword_type in minor_types:
                    keywords = minor_keyword_groups[keyword_type]
                    found_keywords = [
                        kw for kw in keywords if kw in doc.page_content.lower()
                    ]
                    if found_keywords:
                        print(
                            f"     * {keyword_type} 예시: {', '.join(found_keywords[:3])}"
                        )
            else:
                print("   - 마이너 키워드가 발견되지 않았습니다")

        # 최종 선택된 문서들만 추출
        retrieved_docs = [result["doc"] for result in selected_results]

        # 세션에 새로 추가된 장소들을 저장
        if session_id and session_id != "default_session" and new_recommended_places:
            try:
                session = ChatSession.objects.filter(id=session_id).first()
                if session:
                    # 새로 추천된 장소 추가
                    for place in new_recommended_places:
                        session.add_recommended_place(place)
                    print(
                        f"세션 {session_id}에 {len(new_recommended_places)}개의 새로운 장소가 저장되었습니다."
                    )
                else:
                    print(
                        f"세션 {session_id}을 찾을 수 없어 추천 장소를 저장하지 못했습니다."
                    )
            except Exception as e:
                print(f"추천 장소 저장 중 오류 발생: {e}")

        # 처리 시간 출력
        total_time = time.time() - start_time
        print(f"\n=== 검색 완료 (총 {total_time:.2f}초) ===")

        # 새로 추천한 장소 목록
        all_recommended_places = (
            recommended_places + new_recommended_places
            if recommended_places
            else new_recommended_places
        )
        print(f"현재까지 추천한 장소 수: {len(all_recommended_places)}")

        # 업데이트된 graph state 반환
        return {
            **state,
            "retrieved_docs": retrieved_docs,
            "recommended_places": all_recommended_places,
        }

    # URL 파라미터에서 추출한 정보만을 이용해 검색 실행
    return retrieve(question, schedule_place, schedule_companion, recommended_places)
