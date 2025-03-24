from .base import GraphState, extract_categories_and_districts

def query_analyzer(state: GraphState) -> GraphState:
    """쿼리 분석 노드
    
    쿼리를 분석하여 이벤트인지 일반 검색인지 판단하고, 카테고리와 지역, 마이너 키워드를 추출합니다.
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        업데이트된 그래프 상태
    """
    print(f"\n=== 쿼리 분석 시작: '{state['question']}' ===")
    
    question = state["question"]
    
    # 쿼리 타입 확인 (이벤트인지 일반인지)
    from .base import check_query_type
    query_type = check_query_type(question)
    
    # 카테고리 및 구 이름 추출
    category, district = extract_categories_and_districts(question)
    
    print(f"추출된 지역: {district}")
    print(f"추출된 카테고리: {category}")
    print(f"쿼리 유형: {'이벤트' if query_type == 'event' else '일반'}")
    print("=== 쿼리 분석 완료 ===\n")
    
    # 상태 업데이트
    return {
        **state,
        "is_event": query_type == "event",
        "query_info": {
            "category": category,
            "district": district
        }
    } 