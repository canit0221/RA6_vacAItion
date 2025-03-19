import os
import random
from .base import GraphState
from dotenv import load_dotenv
from pathlib import Path

# 환경 변수 명시적 로드
def load_env_variables():
    """환경 변수를 명시적으로 로드"""
    # .env 파일 로드
    load_dotenv()
    
    # 환경 변수 확인
    naver_client_id = os.getenv("NAVER_CLIENT_ID")
    naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    return naver_client_id, naver_client_secret

async def naver_search(state: GraphState) -> GraphState:
    """네이버 검색 노드
    
    네이버 지역 검색 API를 통해 장소 정보를 검색합니다.
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        업데이트된 그래프 상태
    """
    question = state["question"]
    
    # 환경 변수 명시적 로드
    naver_client_id, naver_client_secret = load_env_variables()
    
    # API 키가 없으면 빈 결과 반환
    if not naver_client_id or not naver_client_secret:
        print("네이버 API 키를 사용할 수 없습니다. 검색 결과가 제한될 수 있습니다.")
        return {**state, "naver_results": []}
    
    try:
        import aiohttp
        query_info = state.get("query_info", {})
        district = query_info.get("district")
        category = query_info.get("category")
        
        # 검색어 구성
        search_terms = []
        if district:
            district_name = district.split()[-1]
            search_terms.append(district_name)
        if category:
            search_terms.append(category)
            
        final_query = " ".join(search_terms) if search_terms else question
        
        print(f"네이버 검색어: {final_query}")
        
        headers = {
            "X-Naver-Client-Id": naver_client_id,
            "X-Naver-Client-Secret": naver_client_secret,
        }
        
        async with aiohttp.ClientSession() as session:
            url = "https://openapi.naver.com/v1/search/local.json"
            params = {
                "query": final_query,
                "display": "5",
                "start": "1",
                "sort": "comment",
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    for item in data.get("items", []):
                        title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                        address = item.get("address", "")
                        road_address = item.get("roadAddress", "")
                        
                        results.append({
                            "title": title,
                            "address": address,
                            "roadAddress": road_address,
                            "category": item.get("category", ""),
                            "description": item.get("description", ""),
                            "link": item.get("link", ""),
                            "mapx": item.get("mapx", ""),
                            "mapy": item.get("mapy", ""),
                        })
                        
                    print(f"네이버 검색 결과: {len(results)}개")
                    selected_places = random.sample(results, min(3, len(results))) if results else []
                    
                    return {**state, "naver_results": selected_places}
                else:
                    print(f"네이버 API 오류: {response.status}")
                    return {**state, "naver_results": []}
    except Exception as e:
        print(f"네이버 검색 중 오류 발생: {str(e)}")
        return {**state, "naver_results": []} 