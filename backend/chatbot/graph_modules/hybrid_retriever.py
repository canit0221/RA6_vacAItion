import os
import time
import re
import numpy as np
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from .base import GraphState
from .data_loader import load_data
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Tuple
import logging

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

    # 가중치 설정
    vector_weight = 0.4
    keyword_weight = 0.6

    # 카테고리별 가중치 동적 조정
    category = query_info.get("category")
    if category == "맛집":
        vector_weight = 0.2  # 맛집 카테고리일 때는 키워드 가중치 더 높임
        keyword_weight = 0.8
        logger.debug("맛집 카테고리 감지: 키워드 가중치 상향 조정됨 (0.8)")

    # 쿼리가 없는 경우 검색 건너뛰기
    if not question:
        logger.warning("쿼리가 비어있어 검색을 건너뜁니다.")
        return {**state, "retrieved_docs": []}

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
                if keyword_type in ["숨은", "우연", "로컬", "특별한", "감성"]:
                    score += 0.3  # 각 그룹당 0.3의 가중치
                    found_keyword_types.append(keyword_type)

        return min(score, 1.0), found_keyword_types  # 최대 점수는 1.0

    # 1. 쿼리 분석
    # 쿼리에서 구 정보가 없는 경우, query_info에서 가져온 값 사용
    if not district:
        district = extract_district(question)

    # 카테고리 정보가 없는 경우, 쿼리에서 추출
    if not category:
        category = extract_category(question)

    logger.info(f"최종 검색 조건 - 지역: {district}, 카테고리: {category}")

    # 2. 첫 번째 단계: 벡터 검색
    vector_start = time.time()
    logger.info("벡터 검색 실행 중...")

    # 벡터 검색 과정 수행
    docs_and_scores = []
    try:
        docs_and_scores = vectorstore.similarity_search_with_score(
            question, k=min(15, len(docs))
        )
        logger.info(f"벡터 검색 결과: {len(docs_and_scores)}개 문서")
    except Exception as e:
        logger.error(f"벡터 검색 오류: {str(e)}")
        docs_and_scores = [(doc, 1.0) for doc in docs[: min(15, len(docs))]]

    docs_with_scores = []
    for doc, score in docs_and_scores:
        vector_score = 1.0 - score  # 거리를 유사도로 변환
        docs_with_scores.append((doc, vector_score))

    # 3. 키워드 기반 필터링
    keyword_start = time.time()
    logger.info("키워드 기반 필터링 중...")

    # 지역 기반 필터링
    filtered_docs = []
    if district:
        district_name = district.replace("서울 ", "")
        for doc, score in docs_with_scores:
            content = doc.page_content.lower()
            if (
                district.lower() in content
                or district_name.lower() in content
                or district.lower() in doc.metadata.get("location", "").lower()
                or district_name.lower() in doc.metadata.get("location", "").lower()
            ):
                filtered_docs.append((doc, score))
        logger.info(f"지역 필터링 결과: {len(filtered_docs)}개 문서")
    else:
        filtered_docs = docs_with_scores
        logger.debug("지역 필터가 없어 모든 문서 사용")

    # 카테고리 기반 필터링 (이벤트가 아닐 경우)
    if not is_event and category:
        category_filtered = []
        category_keywords = categories.get(category, [])
        for doc, score in filtered_docs:
            content = doc.page_content.lower()
            if any(keyword in content for keyword in category_keywords):
                category_filtered.append((doc, score))
        if category_filtered:  # 필터링 결과가 있는 경우만 적용
            filtered_docs = category_filtered
            logger.info(f"카테고리 필터링 결과: {len(filtered_docs)}개 문서")
        else:
            logger.info(f"카테고리 '{category}' 필터링 결과가 없어 이전 결과 유지")

    # 4. 마이너 키워드 점수 계산 및 적용
    final_results = []
    logger.debug("마이너 키워드 점수 계산 중...")

    for doc, vector_score in filtered_docs:
        # 문서에서 마이너 키워드 점수 계산
        minor_score, found_types = check_minor_keywords_in_doc(doc.page_content)

        # 최종 점수 계산 (벡터 점수 * 벡터 가중치 + 마이너 점수 * 키워드 가중치)
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

    # 상위 결과 선택 (최대 5개)
    top_k = min(5, len(final_results))
    selected_results = final_results[:top_k]

    # 결과 출력
    logger.info(f"\n=== 상위 {top_k}개 결과 ===")
    for i, result in enumerate(selected_results, 1):
        doc = result["doc"]
        minor_types = result["minor_types"]

        # 문서 내용 요약 (첫 50자)
        content_preview = (
            doc.page_content[:50] + "..."
            if len(doc.page_content) > 50
            else doc.page_content
        )

        logger.info(f"\n{i}. 문서 (점수: {result['score']:.4f}):")
        logger.info(f"   - 내용 미리보기: {content_preview}")
        logger.info(
            f"   - 벡터 점수: {result['vector_score']:.4f}, 마이너 점수: {result['minor_score']:.4f}"
        )

        if minor_types:
            logger.info(f"   - 발견된 마이너 키워드 유형: {', '.join(minor_types)}")
            # 마이너 키워드 예시 추출 및 출력
            for keyword_type in minor_types:
                keywords = minor_keyword_groups[keyword_type]
                found_keywords = [
                    kw for kw in keywords if kw in doc.page_content.lower()
                ]
                if found_keywords:
                    logger.info(
                        f"     * {keyword_type} 예시: {', '.join(found_keywords[:3])}"
                    )
        else:
            logger.info("   - 마이너 키워드가 발견되지 않았습니다")

    # 최종 선택된 문서들만 추출
    retrieved_docs = [result["doc"] for result in selected_results]

    # 처리 시간 출력
    total_time = time.time() - start_time
    logger.info(f"\n=== 검색 완료 (총 {total_time:.2f}초) ===")

    return {**state, "retrieved_docs": retrieved_docs}
