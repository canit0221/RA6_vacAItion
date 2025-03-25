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
from django.apps import apps
import asyncio
from channels.db import database_sync_to_async

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
    
    # 세션 ID 확인 - 기본값은 "default_session"
    session_id = state.get("session_id", "default_session")
    print(f"현재 세션 ID: {session_id}")
    
    # 세션 객체 가져오기
    ChatSession = apps.get_model('chatbot', 'ChatSession')
    ChatMessage = apps.get_model('chatbot', 'ChatMessage')
    
    try:
        # 세션 ID가 제공된 경우 데이터베이스에서 세션 정보 가져오기
        if session_id and session_id != "default_session":
            session = ChatSession.objects.filter(id=session_id).first()
            
            if session:
                # 데이터베이스에서 세션의 추천 장소 목록 가져오기
                recommended_places = session.get_recommended_places()
                print(f"데이터베이스에서 가져온 이전에 추천한 장소 수: {len(recommended_places)}")
                print(f"이전에 추천한 장소 목록: {recommended_places}")
            else:
                print(f"세션 {session_id}를 찾을 수 없어 빈 추천 목록을 사용합니다.")
                recommended_places = []
        else:
            # 세션 정보가 없는 경우 빈 목록 사용
            print("세션 ID가 없어 빈 추천 목록을 사용합니다.")
            recommended_places = []
    except Exception as e:
        print(f"세션 정보 로드 중 오류 발생: {e}")
        # 오류 발생 시 빈 목록 사용
        recommended_places = []
    
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
        return {**state, "retrieved_docs": [], "recommended_places": recommended_places}

    # 카테고리 정보 추출
    district = query_info.get("district")

    print(f"검색어: '{question}'")
    print(f"지역: {district}")
    print(f"카테고리: {category}")
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

    # 마이너 키워드 그룹 설정
    minor_keyword_groups = {
        "숨은": [
            "숨은", "숨겨진", "비밀", "알려지지", "알려지지 않은", "비밀스러운", "모르는",
            "비밀의", "숨은 맛집", "숨은 카페", "숨겨진 맛집", "숨겨진 카페", "모르는 사람",
            "아는 사람", "미공개", "비공개", "소수", "소수만", "현지인", "현지인들", "매니아",
            "진짜", "진짜 맛집", "찐", "찐 맛집", "찐 카페", "소문", "소문난", "히든"
        ],
        "우연": [
            "우연", "우연히", "우연의", "우연한", "우연찮게", "발견", "발견한", "지나가다",
            "발견된", "알게 된", "알게된", "몰랐던", "모르는", "올라가다", "내려가다", "보이는",
            "보인", "눈에 띄는", "눈에 띈", "눈에 들어온", "눈에 들어온", "눈에 들어와",
            "발견할", "찾아낸", "어쩌다", "어쩌다가", "변두리", "골목", "골목길", "진입로"
        ],
        "로컬": [
            "로컬", "지역", "지역민", "동네", "거주", "거주민", "사는", "사는 사람", "주민",
            "단골", "단골집", "단골손님", "앞집", "앞동네", "뒷동네", "골목", "골목길", "골목 안",
            "골목 속", "이웃", "이웃들", "이웃집", "이웃 주민", "정기적", "항상", "자주",
            "자주 가는", "우리 동네", "동네 주민", "동네 사람"
        ],
        "특별한": [
            "특별한", "특별하게", "특별함", "독특한", "독특하게", "색다른", "색다르게", "색달라",
            "다른", "남다른", "남달라", "낯선", "새로운", "처음", "새롭게", "익숙치 않은",
            "익숙하지 않은", "특이한", "특이하게", "이색", "이색적인", "기존과 다른", "평범하지 않은",
            "평범치 않은", "차별화된", "차별화", "기억에 남는"
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

    print(f"최종 검색 조건 - 지역: {district}, 카테고리: {category}")

    # 2. 검색 순서 변경: 메타데이터 기반 필터링 먼저 수행
    print("\n2. 메타데이터 기반 필터링 수행 중...")
    
    # 모든 문서를 대상으로 필터링 시작
    filtered_docs = docs
    
    # 2.1. 지역 기반 필터링
    print("   - 지역 기반 필터링 수행 중...")
    if district:
        district_name = district.replace("서울 ", "")
        location_filtered_docs = []
        for doc in filtered_docs:
            content = doc.page_content.lower()
            metadata_location = doc.metadata.get("location", "").lower()
            metadata_address = doc.metadata.get("address", "").lower()
            
            # 지역명이 콘텐츠나 메타데이터에 포함되어 있는지 확인
            if (district.lower() in content or 
                district_name.lower() in content or 
                district.lower() in metadata_location or
                district_name.lower() in metadata_location or
                district.lower() in metadata_address or
                district_name.lower() in metadata_address):
                location_filtered_docs.append(doc)
        
        # 필터링 결과가 적어도 해당 구 내의 결과만 유지 (확장하지 않음)
        if len(location_filtered_docs) < 3:
            print(f"   - 지역 필터링 결과가 적습니다 ({len(location_filtered_docs)}개). 해당 구 내의 결과만 유지합니다.")
        
        filtered_docs = location_filtered_docs
        print(f"   - 지역 필터링 결과: {len(filtered_docs)}개 문서")
    else:
        print("   - 지역 필터가 없어 모든 문서 사용")
    
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
    
    print(f"   - 이미 추천된 {excluded_count}개 장소 제외 후 {len(non_recommended_docs)}개 문서 남음")
    
    # 필터링된 문서 수가 너무 적으면 (3개 미만) 메시지 출력
    if len(non_recommended_docs) < 3:
        print("   - 경고: 추천할 새로운 장소가 거의 없습니다.")
    
    # 4. 벡터 검색 수행 (필터링된 문서만 대상으로)
    vector_start = time.time()
    print("\n4. 벡터 검색 실행 중...")
    
    # 필터링된 문서가 없으면 원본 문서 사용
    docs_to_search = non_recommended_docs if non_recommended_docs else docs
    
    # 벡터 검색 수행
    docs_and_scores = []
    
    # 벡터 검색할 문서가 충분히 있는지 확인
    if len(docs_to_search) >= 3:
        try:
            # 검색 문서 수 증가 (15 -> 30)
            search_k = min(30, len(docs_to_search))
            
            # 벡터스토어를 사용하여 필터링된 문서에서만 검색
            embeddings = OpenAIEmbeddings()
            text_field = "page_content"
            
            # 임시 벡터스토어 생성 (필터링된 문서로만)
            temp_vectorstore = Chroma.from_documents(
                documents=docs_to_search,
                embedding=embeddings,
                collection_name="temp_filtered_collection"
            )
            
            # 임시 벡터스토어에서 검색
            docs_and_scores = temp_vectorstore.similarity_search_with_score(
                question, k=search_k
            )
            print(f"   - 벡터 검색 결과: {len(docs_and_scores)}개 문서")
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
        final_results.append({
            "doc": doc,
            "score": final_score,
            "vector_score": vector_score,
            "minor_score": minor_score,
            "minor_types": found_types
        })
    
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
        content_preview = doc.page_content[:50] + "..." if len(doc.page_content) > 50 else doc.page_content
        
        print(f"\n{i}. 문서 (점수: {result['score']:.4f}):")
        print(f"   - 내용 미리보기: {content_preview}")
        print(f"   - 벡터 점수: {result['vector_score']:.4f}, 마이너 점수: {result['minor_score']:.4f}")
        
        if minor_types:
            print(f"   - 발견된 마이너 키워드 유형: {', '.join(minor_types)}")
            # 마이너 키워드 예시 추출 및 출력
            for keyword_type in minor_types:
                keywords = minor_keyword_groups[keyword_type]
                found_keywords = [kw for kw in keywords if kw in doc.page_content.lower()]
                if found_keywords:
                    print(f"     * {keyword_type} 예시: {', '.join(found_keywords[:3])}")
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
                print(f"세션 {session_id}에 {len(new_recommended_places)}개의 새로운 장소가 저장되었습니다.")
            else:
                print(f"세션 {session_id}을 찾을 수 없어 추천 장소를 저장하지 못했습니다.")
        except Exception as e:
            print(f"추천 장소 저장 중 오류 발생: {e}")
    
    # 처리 시간 출력
    total_time = time.time() - start_time
    print(f"\n=== 검색 완료 (총 {total_time:.2f}초) ===")
    print(f"현재까지 추천한 장소 수: {len(recommended_places) + len(new_recommended_places)}")
    
    # 업데이트된 전체 추천 장소 목록 (기존 + 신규)
    all_recommended_places = recommended_places + new_recommended_places
    
    # 업데이트된 graph state 반환 (추천한 장소 목록 포함)
    return {
        **state, 
        "retrieved_docs": retrieved_docs, 
        "recommended_places": all_recommended_places
    }