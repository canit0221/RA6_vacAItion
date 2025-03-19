import os
import time
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from .base import GraphState
from .data_loader import load_data

# 환경 변수 로드
load_dotenv()

def hybrid_retriever(state: GraphState) -> GraphState:
    """하이브리드 검색 노드
    
    벡터 검색과 키워드 필터링을 결합하여 검색 결과를 제공합니다.
    
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
    
    # 쿼리가 없는 경우 검색 건너뛰기
    if not question:
        print("쿼리가 비어있어 검색을 건너뜁니다.")
        return {**state, "retrieved_docs": []}
    
    # 카테고리 정보 추출
    district = query_info.get("district")
    category = query_info.get("category")
    minor_keywords = query_info.get("minor_keywords", [])
    
    print(f"검색어: '{question}'")
    print(f"지역: {district}")
    print(f"카테고리: {category}")
    print(f"소분류 키워드: {minor_keywords}")
    
    # 데이터 로드
    query_type = "event" if is_event else "general"
    docs, vectorstore = load_data(query_type)
    
    # 벡터 검색 결과
    vector_results = vectorstore.similarity_search(question, k=5)
    
    # 키워드 필터링
    filtered_docs = []
    
    # 구 필터링
    if district:
        district_name = district.replace("서울 ", "")
        for doc in docs:
            content = doc.page_content.lower()
            location = doc.metadata.get("location", "").lower()
            if (district.lower() in content or district_name.lower() in content or
                district.lower() in location or district_name.lower() in location):
                filtered_docs.append(doc)
    else:
        filtered_docs = docs
    
    # 마이너 키워드 필터링 (이벤트가 아닐 때만)
    if not is_event and minor_keywords and filtered_docs:
        keyword_groups = {
            "숨은": ["숨은", "숨겨진", "알려지지 않은", "비밀", "히든", "hidden", "secret", "잘 모르는", "남들이 모르는", "나만 아는", "나만 알고 있는", "붐비지 않는", "한적한"],
            "우연": ["우연히", "우연한", "우연히 발견한", "우연히 알게 된", "우연히 찾은", "우연히 방문한", "우연히 가게 된"],
            "로컬": ["로컬", "현지인", "주민", "동네", "단골", "local", "근처", "주변"]
        }
        
        minor_filtered = []
        for doc in filtered_docs:
            content = doc.page_content.lower()
            for keyword_type in minor_keywords:
                keywords = keyword_groups.get(keyword_type, [])
                if any(keyword in content for keyword in keywords):
                    minor_filtered.append(doc)
                    break
                    
        if minor_filtered:
            filtered_docs = minor_filtered
    
    # 최종 결과가 없으면 벡터 검색 결과 사용
    if not filtered_docs:
        filtered_docs = vector_results
        
    # 최대 6개 문서로 제한
    final_docs = filtered_docs[:6]
    
    elapsed_time = time.time() - start_time
    print(f"검색 시간: {elapsed_time:.2f}초")
    print(f"최종 검색 결과: {len(final_docs)}개 문서")
    print("=== 하이브리드 검색 완료 ===\n")
    
    # 상태 업데이트
    return {
        **state,
        "retrieved_docs": final_docs
    } 