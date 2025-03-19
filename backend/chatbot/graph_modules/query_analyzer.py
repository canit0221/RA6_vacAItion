from .base import GraphState, check_query_type, extract_categories_and_districts, extract_minor_keywords

def query_analyzer(state: GraphState) -> GraphState:
    """쿼리 분석 노드
    
    쿼리를 분석하여 이벤트인지 일반 검색인지 판단하고, 카테고리와 지역, 마이너 키워드를 추출합니다.
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        업데이트된 그래프 상태
    """
    question = state["question"]
    
    # 쿼리 타입 확인 (이벤트인지 일반인지)
    query_type = check_query_type(question)
    
    # 카테고리 및 구 이름 추출
    category, district = extract_categories_and_districts(question)
    
    # 마이너 키워드 추출
    minor_keywords = extract_minor_keywords(question)
    
    print(f"쿼리 타입: {query_type}")
    print(f"카테고리: {category}")
    print(f"지역: {district}")
    print(f"마이너 키워드: {minor_keywords}")
    
    # 상태 업데이트
    return {
        **state,
        "is_event": query_type == "event",
        "query_info": {
            "category": category,
            "district": district,
            "minor_keywords": minor_keywords
        }
    } 