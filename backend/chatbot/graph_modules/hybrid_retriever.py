from .base import GraphState
from .data_loader import load_data

def hybrid_retriever(state: GraphState) -> GraphState:
    """하이브리드 검색 노드
    
    벡터 검색과 키워드 필터링을 결합하여 검색 결과를 제공합니다.
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        업데이트된 그래프 상태
    """
    question = state["question"]
    is_event = state.get("is_event", False)
    query_info = state.get("query_info", {})
    
    # 데이터 로드
    query_type = "event" if is_event else "general"
    docs, vectorstore = load_data(query_type)
    
    # 벡터 검색 결과
    vector_results = vectorstore.similarity_search(question, k=5)
    
    # 키워드 필터링
    district = query_info.get("district")
    category = query_info.get("category")
    minor_keywords = query_info.get("minor_keywords", [])
    
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
                
        print(f"구 이름으로 필터링된 문서 수: {len(filtered_docs)}개")
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
            print(f"마이너 키워드로 필터링된 문서 수: {len(filtered_docs)}개")
    
    # 최종 결과가 없으면 벡터 검색 결과 사용
    if not filtered_docs:
        filtered_docs = vector_results
        
    # 최대 3개 문서로 제한
    final_docs = filtered_docs[:3]
    
    print(f"최종 검색 결과: {len(final_docs)}개 문서")
    
    # 상태 업데이트
    return {
        **state,
        "retrieved_docs": final_docs
    } 