import json
import os
import random
import urllib.request
from .base import GraphState
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, List

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
    검색 결과는 최대 6개까지 반환합니다.
    
    Args:
        state: 현재 그래프 상태
    
    Returns:
        업데이트된 그래프 상태
    """
    print("\n=== 네이버 검색 시작 ===")
    
    question = state["question"]
    
    # 이벤트 쿼리인 경우 검색 스킵
    is_event = state.get("is_event", False)
    if is_event:
        print("이벤트 쿼리이므로 네이버 검색을 건너뜁니다.")
        return {**state, "naver_results": []}
    
    # 환경 변수 명시적 로드
    naver_client_id, naver_client_secret = load_env_variables()
    
    # API 키가 없으면 빈 결과 반환
    if not naver_client_id or not naver_client_secret:
        print("네이버 API 키가 설정되지 않았습니다.")
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
        
        print(f"네이버 검색어: '{final_query}'")
        
        headers = {
            "X-Naver-Client-Id": naver_client_id,
            "X-Naver-Client-Secret": naver_client_secret,
        }
        
        async with aiohttp.ClientSession() as session:
            url = "https://openapi.naver.com/v1/search/local.json"
            params = {
                "query": final_query,
                "display": "10",
                "start": "1",
                "sort": "random",
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("items", [])
                    print(f"네이버 검색 결과: {len(results)}개")
                    
                    # 결과 중 최대 6개를 무작위로 선택 (결과가 6개 미만이면 모두 선택)
                    selected_places = random.sample(results, min(6, len(results))) if results else []
                    
                    # 선택된 장소 정보 가공
                    places = []
                    for item in selected_places:
                        title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                        address = item.get("address", "")
                        road_address = item.get("roadAddress", "")
                        
                        places.append({
                            "title": title,
                            "address": address,
                            "roadAddress": road_address,
                            "category": item.get("category", ""),
                            "description": item.get("description", ""),
                            "link": item.get("link", ""),
                            "mapx": item.get("mapx", ""),
                            "mapy": item.get("mapy", ""),
                            "telephone": item.get("telephone", "")
                        })
                    
                    print(f"최종 선택된 장소: {len(places)}개")
                    print("=== 네이버 검색 완료 ===\n")
                    
                    return {**state, "naver_results": places}
                else:
                    print(f"네이버 API 오류: 상태 코드 {response.status}")
                    return {**state, "naver_results": []}
    except Exception as e:
        print(f"네이버 API 요청 중 오류 발생: {e}")
        return {**state, "naver_results": []} 