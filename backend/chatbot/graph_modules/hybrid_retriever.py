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
    print("\n=== 하이브리드 검색 시작 ===")
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
        print("맛집 카테고리 감지: 키워드 가중치 상향 조정됨 (0.8)")

    # 쿼리가 없는 경우 검색 건너뛰기
    if not question:
        print("쿼리가 비어있어 검색을 건너뜁니다.")
        return {**state, "retrieved_docs": []}

    # 카테고리 정보 추출
    district = query_info.get("district")
    minor_keywords = query_info.get("minor_keywords", [])

    print(f"검색어: '{question}'")
    print(f"지역: {district}")
    print(f"카테고리: {category}")
    print(f"소분류 키워드: {minor_keywords}")
    print(f"가중치 설정 - 벡터: {vector_weight}, 키워드: {keyword_weight}")

    # 데이터 로드
    query_type = "event" if is_event else "general"
    docs, vectorstore = load_data(query_type)

    # 서울시 구 리스트 정의
    districts = [
        "서울 종로구", "서울 중구", "서울 용산구", "서울 성동구", "서울 광진구", "서울 동대문구",
        "서울 중랑구", "서울 성북구", "서울 강북구", "서울 도봉구", "서울 노원구", "서울 은평구",
        "서울 서대문구", "서울 마포구", "서울 양천구", "서울 강서구", "서울 구로구", "서울 금천구",
        "서울 영등포구", "서울 동작구", "서울 관악구", "서울 서초구", "서울 강남구", "서울 송파구", "서울 강동구"
    ]

    # 카테고리 설정
    categories = {
        "카페": ["카페", "커피", "브런치", "디저트", "티룸", "스터디카페", "베이커리", "아이스크림"],
        "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는", "먹거리", "밥집", "저녁", "점심", "한식", "양식", "일식", "중식"],
        "공연": ["공연", "연극", "뮤지컬", "오페라", "극장", "공연장", "연주회"],
        "전시": ["전시", "전시회", "갤러리", "미술관", "박물관", "아트", "작품"],
        "콘서트": ["콘서트", "공연장", "라이브", "음악", "페스티벌", "버스킹"]
    }

    # 토큰화 함수 정의
    def tokenize(text: str) -> List[str]:
        """텍스트를 토큰화하는 함수"""
        return re.findall(r"[\w\d가-힣]+", text.lower())

    # 마이너 장소 키워드 그룹 정의 - 확장된 버전
    minor_keyword_groups = {
        "숨은": [
            "숨은", "숨겨진", "알려지지 않은", "비밀", "히든", "hidden",
            "secret", "잘 모르는", "남들이 모르는", "나만 아는",
            "나만 알고 있는", "붐비지 않는", "한적한", "조용한", "언급 안 된",
            "아는 사람만", "뜨지 않은", "인기 없는", "신상", "새로운",
            "찾기 힘든", "모르는", "생소한", "덜 알려진"
        ],
        "우연": [
            "우연히", "우연한", "우연히 발견한", "우연히 알게 된",
            "우연히 찾은", "우연히 방문한", "우연히 가게 된", "발견한",
            "찾아낸", "마주친", "지나가다", "우연", "찾게 된", "발견", "들리게 된",
            "알게 된", "마주하게 된", "발견하게 된", "우연의 일치"
        ],
        "로컬": [
            "로컬", "현지인", "주민", "동네", "단골", "local", "근처", "주변",
            "지역", "골목", "골목길", "동네 주민", "지역 맛집", "사람들이 모르는",
            "주민들", "동네 사람들", "단골손님", "토박이", "지역 특색",
            "로컬 맛집", "지역민", "사람", "주민 추천", "동네 가게",
            "동네 사람들만", "동네에서 유명한", "지역 주민들이 찾는"
        ],
        "특별한": [
            "특별한", "독특한", "색다른", "이색", "이색적인", "특이한", "유니크한",
            "남다른", "기발한", "창의적인", "특색 있는", "새로운 시도", "참신한",
            "기존에 없던", "새로운 개념", "특별함", "특별하게", "유일한", "오직",
            "톡톡 튀는", "차별화된", "남들과 다른", "이색테마", "독특함"
        ],
        "감성": [
            "감성", "감성적인", "분위기", "분위기 좋은", "예쁜", "아름다운", "인스타",
            "인스타그램", "인스타그래머블", "포토", "포토존", "사진", "사진찍기",
            "감성있는", "감성장소", "감성공간", "감성카페", "인스타감성", "포토스팟",
            "영화같은", "그림같은", "무드", "라이팅", "조명", "뷰", "전망"
        ]
    }

    # 중요 맛집 키워드 확장
    important_food_keywords = [
        "맛집", "음식점", "식당", "레스토랑", "맛있는", "먹거리", "메뉴", "요리",
        "맛있게", "맛집추천", "배고픈", "배고파", "먹을만한", "식사", "저녁", "점심",
        "브런치", "아침", "식도락", "음식", "분위기좋은", "유명한", "유명 맛집", 
        "맛있다", "맛집 추천", "맛있을", "푸짐한", "맛있어", "맛있게", "맛집 여행",
        "맛있어요", "맛있다고", "추천 맛집", "인기 맛집", "인기", "인기있는",
        "맛도", "맛도 있고", "데이트", "데이트코스", "가족", "가족모임", "회식"
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

        for district in districts:
            district_name = district.replace("서울 ", "")
            if district_name in query:
                return district
        return None

    # 마이너 키워드 타입 추출 함수
    def extract_minor_types(query: str) -> List[str]:
        """쿼리에서 마이너 추천 타입 추출"""
        query = query.lower()
        minor_types = []
        
        for minor_type, keywords in minor_keyword_groups.items():
            if any(keyword in query for keyword in keywords):
                minor_types.append(minor_type)
        
        return minor_types

    # 마이너 키워드 점수 계산 함수 - 개선된 버전
    def calculate_minor_keyword_score(doc_content: str, requested_types: List[str] = None) -> Dict[str, Any]:
        """문서 내용에서 마이너 키워드 존재 여부 확인 및 점수 계산"""
        doc_content = doc_content.lower()
        score = 0.0
        found_types = []
        matching_keywords = {}
        
        # 각 마이너 키워드 그룹 검사
        for keyword_type, keywords in minor_keyword_groups.items():
            found_kws = [kw for kw in keywords if kw in doc_content]
            if found_kws:
                # 마이너 키워드가 발견됨
                found_types.append(keyword_type)
                matching_keywords[keyword_type] = found_kws[:3]  # 최대 3개까지 저장
                
                # 가중치 계산 - 요청된 타입이면 더 높은 가중치 부여
                if requested_types and keyword_type in requested_types:
                    score += 0.5  # 요청된 타입은 더 높은 가중치
                else:
                    score += 0.3  # 기본 가중치
        
        # 최대 점수는 1.0으로 제한
        score = min(score, 1.0)
        
        return {
            "score": score,
            "found_types": found_types,
            "matching_keywords": matching_keywords
        }

    # 키워드 매칭 점수 계산 함수 - 마이너 장소에 특화된 버전
    def calculate_keyword_scores(query: str, filtered_docs: List[Any], requested_minor_types: List[str] = None) -> Tuple[List[float], List[Dict]]:
        """BM25 기반 키워드 매칭 점수와 마이너 키워드 정보 계산"""
        # 토큰화
        tokenized_query = tokenize(query)
        filtered_tokenized_docs = [tokenize(doc.page_content) for doc in filtered_docs]
        
        # BM25 객체 생성
        filtered_bm25 = BM25Okapi(filtered_tokenized_docs)
        
        # 기본 키워드 점수 계산
        base_scores = filtered_bm25.get_scores(tokenized_query)
        
        # 맛집 관련 키워드에 가중치 부여
        if category == "맛집":
            # 맛집 키워드가 있는 문서에 추가 가중치
            adjusted_base_scores = []
            for i, doc in enumerate(filtered_docs):
                doc_content = doc.page_content.lower()
                score = base_scores[i]
                
                # 중요 맛집 키워드가 포함된 경우 가중치 2.0배 적용 (강화)
                if any(keyword in doc_content for keyword in important_food_keywords):
                    score *= 2.0
                
                adjusted_base_scores.append(score)
            
            base_scores = adjusted_base_scores
        
        # 문서 내용의 마이너 키워드 분석 및 점수 계산
        minor_keyword_results = []
        for doc in filtered_docs:
            result = calculate_minor_keyword_score(doc.page_content, requested_minor_types)
            minor_keyword_results.append(result)
        
        minor_scores = [result["score"] for result in minor_keyword_results]
        
        # 마이너 키워드 가중치 비율 설정
        # 마이너 키워드 요청이 있으면 가중치 증가
        if requested_minor_types:
            bm25_weight = 0.6  # 마이너 키워드 요청 시 BM25 비중 조금 낮춤
            minor_weight = 0.4  # 마이너 키워드 비중 증가
        else:
            bm25_weight = 0.7 if category == "맛집" else 0.6
            minor_weight = 1.0 - bm25_weight
        
        # 최종 점수 계산
        final_scores = [
            base_score * bm25_weight + minor_score * minor_weight
            for base_score, minor_score in zip(base_scores, minor_scores)
        ]
        
        # 점수 정규화
        if final_scores:
            max_score = max(final_scores) + 1e-6
            final_scores = [score / max_score for score in final_scores]
        
        return final_scores, minor_keyword_results

    # 벡터 유사도 점수 계산 함수
    def calculate_vector_scores(query: str, docs: List[Any]) -> List[float]:
        """벡터 유사도 점수 계산"""
        query_embedding = np.array(vectorstore.embedding_function.embed_query(query)).reshape(1, -1)
        
        # 기존 벡터스토어에서 인덱스 접근 방식에 맞게 수정
        vector_results = vectorstore.similarity_search_with_score(query, k=len(docs))
        
        # 유사도 점수 추출
        vector_scores = []
        doc_score_map = {str(doc.page_content): score for doc, score in vector_results}
        
        for doc in docs:
            # 벡터 결과에서 해당 문서를 찾아 점수 할당
            score = doc_score_map.get(str(doc.page_content), 1.0)  # 기본값은 최대 거리 1.0
            # 점수를 유사도로 변환 (1 - 정규화된 거리)
            vector_scores.append(1.0 - min(score, 1.0))
        
        # 정규화
        if vector_scores:
            max_vector_score = max(vector_scores) + 1e-6
            vector_scores = [score / max_vector_score for score in vector_scores]
        
        return vector_scores

    # ----- 메인 검색 로직 시작 -----
    search_start = time.time()
    print("\n=== 검색 프로세스 시작 ===")
    
    # 1. 쿼리에서 구 이름과 카테고리 추출
    if not district:
        district = extract_district(question)
    if not category:
        category = extract_category(question)
    
    # 마이너 키워드 추출
    requested_minor_types = extract_minor_types(question) if not minor_keywords else minor_keywords
    
    if district:
        print(f"\n1. 구 이름 추출: '{district}' 발견")
        if category:
            print(f"2. 카테고리 추출: '{category}' 발견")
        if requested_minor_types and not is_event:  # 이벤트가 아닐 때만 마이너 키워드 출력
            print(f"3. 마이너 키워드 추출: {', '.join(requested_minor_types)} 발견")
        
        district_name = district.replace("서울 ", "")
        
        # 2. 구 이름으로 필터링
        keyword_start = time.time()
        print("\n4. 키워드 기반 필터링 중...")
        
        district_filtered_docs = []
        for doc in docs:
            content = doc.page_content.lower()
            location = doc.metadata.get("location", "").lower()
            if (district.lower() in content or 
                district_name.lower() in content or 
                district.lower() in location or 
                district_name.lower() in location):
                district_filtered_docs.append(doc)
        
        print(f"   - 구 이름으로 필터링된 문서 수: {len(district_filtered_docs)}개")
        
        # 구 필터링 결과가 없으면 벡터 검색
        if len(district_filtered_docs) == 0:
            print("   - 구 관련 문서를 찾지 못했습니다. 일반 벡터 검색을 수행합니다.")
            filtered_docs = vectorstore.similarity_search(question, k=8)  # 더 많은 후보 문서 검색
        else:
            filtered_docs = district_filtered_docs
            
            # 3. 마이너 키워드 기반 필터링 - 이벤트가 아닌 경우에만
            if not is_event and requested_minor_types:
                minor_filtered_docs = []
                print("\n   - 마이너 키워드 필터링 시작...")
                
                # 각 문서의 마이너 키워드 점수 계산
                for doc in filtered_docs:
                    minor_result = calculate_minor_keyword_score(doc.page_content, requested_minor_types)
                    score = minor_result["score"]
                    
                    # 일정 점수 이상인 문서만 선택
                    if score > 0:
                        minor_filtered_docs.append(doc)
                
                print(f"   - 마이너 키워드로 필터링 후 문서 수: {len(minor_filtered_docs)}개")
                
                # 마이너 필터링 결과가 있으면 적용, 없으면 원래 결과 사용
                if minor_filtered_docs:
                    filtered_docs = minor_filtered_docs
                elif requested_minor_types:
                    # 마이너 필터링 결과가 없지만 마이너 키워드가 요청된 경우,
                    # 구 필터링 결과에서 최대 10개까지만 사용 (다양성 확보)
                    filtered_docs = district_filtered_docs[:min(10, len(district_filtered_docs))]
                    print("   - 마이너 키워드 매칭 문서가 없습니다. 구 기반 필터링 결과 사용")
        
        # 4. 하이브리드 점수 계산
        scoring_start = time.time()
        print("\n5. 하이브리드 점수 계산 중...")
        
        # 벡터 유사도 점수 계산
        vector_scores = calculate_vector_scores(question, filtered_docs)
        
        # 키워드 매칭 점수 및 마이너 키워드 정보 계산
        print("   - 키워드 및 마이너 키워드 점수 계산 중...")
        keyword_scores, minor_keyword_results = calculate_keyword_scores(
            question, filtered_docs, requested_minor_types
        )
        
        # 5. 최종 점수 계산 및 문서 선택
        # 지역과 맛집 키워드 조합에 특별 가중치 부여
        if district and category == "맛집":
            print("   - 지역+맛집 조합에 특별 가중치 적용")
            # 가중치 기반 결합
            final_scores = [
                (doc, vector_weight * vs + keyword_weight * ks * 1.2, minor_result)  # 맛집 키워드 가중치 추가 조정
                for doc, vs, ks, minor_result in zip(filtered_docs, vector_scores, keyword_scores, minor_keyword_results)
            ]
        # 마이너 장소 요청에 특별 가중치 부여
        elif requested_minor_types and not is_event:
            print(f"   - 마이너 장소 요청({', '.join(requested_minor_types)})에 특별 가중치 적용")
            # 마이너 장소 특화 가중치 적용
            final_scores = [
                (doc, vector_weight * 0.8 * vs + keyword_weight * 1.2 * ks, minor_result)  # 키워드 가중치 높이고 벡터 가중치 낮춤
                for doc, vs, ks, minor_result in zip(filtered_docs, vector_scores, keyword_scores, minor_keyword_results)
            ]
        else:
            # 일반 가중치 기반 결합
            final_scores = [
                (doc, vector_weight * vs + keyword_weight * ks, minor_result)
                for doc, vs, ks, minor_result in zip(filtered_docs, vector_scores, keyword_scores, minor_keyword_results)
            ]
        
        # 6. 점수 기준으로 정렬
        final_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 마이너 장소 다양화를 위한 후처리
        if requested_minor_types and not is_event:
            # 상위 10개 결과에서 마이너 키워드 타입별로 가장 높은 점수의 문서 선택
            top_candidates = final_scores[:min(10, len(final_scores))]
            selected_by_type = {}
            
            # 각 마이너 타입별 최고 점수 문서 선택
            for doc, score, minor_result in top_candidates:
                for minor_type in minor_result["found_types"]:
                    if minor_type in requested_minor_types:
                        if minor_type not in selected_by_type or selected_by_type[minor_type][1] < score:
                            selected_by_type[minor_type] = (doc, score, minor_result)
            
            # 타입별 선택 문서 모으기
            diverse_results = []
            for minor_type, (doc, score, minor_result) in selected_by_type.items():
                diverse_results.append((doc, score, minor_result))
            
            # 다양한 마이너 타입이 없거나 부족한 경우, 상위 점수 결과로 보충
            if not diverse_results:
                diverse_results = top_candidates[:3]
            elif len(diverse_results) < 3:
                # 이미 선택된 문서 제외하고 상위 점수 문서로 보충
                selected_docs = {doc for doc, _, _ in diverse_results}
                for doc, score, minor_result in top_candidates:
                    if doc not in selected_docs:
                        diverse_results.append((doc, score, minor_result))
                        if len(diverse_results) >= 3:
                            break
            
            # 최종 3개 결과 선택 (점수 순 정렬)
            diverse_results.sort(key=lambda x: x[1], reverse=True)
            final_results = diverse_results[:3]
        else:
            # 일반 검색인 경우 상위 3개 결과
            final_results = final_scores[:3]
        
        # 최종 문서 리스트 생성
        top_docs = [doc for doc, _, _ in final_results]
        
        # 7. 선택된 문서 분석 - 이벤트가 아닌 경우에만
        if not is_event:
            print("\n=== 선택된 문서 분석 ===")
            for i, (doc, score, minor_result) in enumerate(final_results, 1):
                doc_content = doc.page_content.lower()
                found_types = minor_result["found_types"]
                matching_keywords = minor_result["matching_keywords"]
                
                print(f"\n문서 {i} 분석 (최종 점수: {score:.4f}):")
                print(f"내용: {doc.page_content[:150]}...")
                
                # 마이너 키워드 분석 정보 출력
                if found_types:
                    print(f"   - 발견된 마이너 키워드 타입: {', '.join(found_types)}")
                    
                    # 세부 키워드 매칭 정보 출력
                    for found_type in found_types:
                        matched_keywords = matching_keywords.get(found_type, [])
                        if matched_keywords:
                            print(f"     → {found_type} 키워드: {', '.join(matched_keywords)}")
                    
                    # 요청된 마이너 키워드와 매칭되는 타입 강조
                    matching_requested = set(found_types) & set(requested_minor_types)
                    if matching_requested:
                        print(f"   ⭐ 요청한 마이너 키워드와 일치: {', '.join(matching_requested)}")
                else:
                    print("   - 마이너 키워드가 발견되지 않았습니다.")
        
        scoring_time = time.time() - scoring_start
        total_time = time.time() - search_start
        
        print(f"\n=== 검색 시간 분석 ===")
        print(f"키워드 필터링 시간: {keyword_start - search_start:.2f}초")
        print(f"하이브리드 점수 계산 시간: {scoring_time:.2f}초")
        print(f"전체 검색 시간: {total_time:.2f}초")
        print(f"최종 검색 결과: {len(top_docs)}개 문서")
        
        return {**state, "retrieved_docs": top_docs}
    
    else:
        # 구 이름이 없는 경우 일반 벡터 검색 + 마이너 키워드 가중치
        print("   - 구 이름이 감지되지 않았습니다. 일반 벡터 검색을 수행합니다.")
        
        # 벡터 검색 (더 많은 후보 검색)
        k = 5
        if requested_minor_types and not is_event:
            k = 8  # 마이너 키워드가 요청된 경우 더 많은 후보 검색
        
        vector_results = vectorstore.similarity_search(question, k=k)
        
        # 마이너 키워드 요청이 있고 이벤트가 아닌 경우 마이너 점수 기반 재정렬
        if requested_minor_types and not is_event:
            print("   - 마이너 키워드 기반 재정렬 수행")
            
            # 키워드 점수 및 마이너 키워드 정보 계산
            keyword_scores, minor_keyword_results = calculate_keyword_scores(
                question, vector_results, requested_minor_types
            )
            
            # 벡터 점수는 이미 유사도 순으로 정렬되어 있음 (8개)
            # 내림차순 정규화된 벡터 스코어 만들기
            normalized_vector_scores = [(k - i) / k for i in range(k)]
            
            # 마이너 키워드 요청 시 키워드 가중치 상향
            vector_weight_minor = 0.3
            keyword_weight_minor = 0.7
            
            # 최종 점수 계산
            final_scores = [
                (doc, vector_weight_minor * vs + keyword_weight_minor * ks, minor_result)
                for doc, vs, ks, minor_result in zip(vector_results, normalized_vector_scores, keyword_scores, minor_keyword_results)
            ]
            
            # 점수 기준 정렬
            final_scores.sort(key=lambda x: x[1], reverse=True)
            
            # 마이너 키워드 타입 다양화 선택
            top_candidates = final_scores[:min(8, len(final_scores))]
            selected_by_type = {}
            
            # 각 마이너 타입별 최고 점수 문서 선택
            for doc, score, minor_result in top_candidates:
                for minor_type in minor_result["found_types"]:
                    if minor_type in requested_minor_types:
                        if minor_type not in selected_by_type or selected_by_type[minor_type][1] < score:
                            selected_by_type[minor_type] = (doc, score, minor_result)
            
            # 타입별 선택 문서 모으기
            diverse_results = []
            for minor_type, (doc, score, minor_result) in selected_by_type.items():
                diverse_results.append((doc, score, minor_result))
            
            # 다양한 마이너 타입이 없거나 부족한 경우, 상위 점수 결과로 보충
            if not diverse_results:
                diverse_results = top_candidates[:3]
            elif len(diverse_results) < 3:
                # 이미 선택된 문서 제외하고 상위 점수 문서로 보충
                selected_docs = {doc for doc, _, _ in diverse_results}
                for doc, score, minor_result in top_candidates:
                    if doc not in selected_docs:
                        diverse_results.append((doc, score, minor_result))
                        if len(diverse_results) >= 3:
                            break

            # 점수 순으로 정렬하고 상위 3개 결과 반환
            diverse_results.sort(key=lambda x: x[1], reverse=True)
            top_docs = [doc for doc, _, _ in diverse_results[:3]]
            
            # 선택된 문서 분석
            print("\n=== 선택된 문서 분석 ===")
            for i, (doc, score, minor_result) in enumerate(diverse_results[:3], 1):
                doc_content = doc.page_content.lower()
                found_types = minor_result["found_types"]
                matching_keywords = minor_result["matching_keywords"]
                
                print(f"\n문서 {i} 분석 (최종 점수: {score:.4f}):")
                print(f"내용: {doc.page_content[:150]}...")
                
                # 마이너 키워드 분석 정보 출력
                if found_types:
                    print(f"   - 발견된 마이너 키워드 타입: {', '.join(found_types)}")
                    
                    # 세부 키워드 매칭 정보 출력
                    for found_type in found_types:
                        matched_keywords = matching_keywords.get(found_type, [])
                        if matched_keywords:
                            print(f"     → {found_type} 키워드: {', '.join(matched_keywords)}")
                    
                    # 요청된 마이너 키워드와 매칭되는 타입 강조
                    matching_requested = set(found_types) & set(requested_minor_types)
                    if matching_requested:
                        print(f"   ⭐ 요청한 마이너 키워드와 일치: {', '.join(matching_requested)}")
                else:
                    print("   - 마이너 키워드가 발견되지 않았습니다.")
        else:
            # 일반 검색인 경우 상위 3개 결과
            top_docs = vector_results[:3]
        
        return {**state, "retrieved_docs": top_docs}