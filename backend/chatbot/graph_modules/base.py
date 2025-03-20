from typing import Dict, List, TypedDict, Optional, Tuple
from langchain_core.documents import Document
import re

# 상태 타입 정의
class GraphState(TypedDict):
    question: str
    retrieved_docs: List[Document]
    naver_results: List[Dict]
    query_info: Dict
    is_event: bool
    answer: str


# 토큰화 함수
def tokenize(text: str) -> List[str]:
    """텍스트를 토큰화하는 함수"""
    return re.findall(r"[\w\d가-힣]+", text.lower())


# 카테고리 및 구 이름 추출 함수
def extract_categories_and_districts(query: str) -> Tuple[Optional[str], Optional[str]]:
    """쿼리에서 카테고리와 구 이름 추출"""
    districts = [
        "서울 종로구", "서울 중구", "서울 용산구", "서울 성동구", "서울 광진구", "서울 동대문구",
        "서울 중랑구", "서울 성북구", "서울 강북구", "서울 도봉구", "서울 노원구", "서울 은평구",
        "서울 서대문구", "서울 마포구", "서울 양천구", "서울 강서구", "서울 구로구", "서울 금천구",
        "서울 영등포구", "서울 동작구", "서울 관악구", "서울 서초구", "서울 강남구", "서울 송파구", "서울 강동구"
    ]
    
    categories = {
        "카페": ["카페", "커피", "브런치", "디저트"],
        "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는"],
        "공연": ["공연", "연극", "뮤지컬", "오페라"],
        "전시": ["전시", "전시회", "갤러리", "미술관"],
        "콘서트": ["콘서트", "공연장", "라이브", "음악"]
    }
    
    # 구 이름 추출
    district = None
    for d in districts:
        if d in query:
            district = d
            break
    
    if not district:
        for d in districts:
            district_name = d.replace("서울 ", "")
            if district_name in query:
                district = d
                break
    
    # 카테고리 추출
    category = None
    query_lower = query.lower()
    for cat, keywords in categories.items():
        if any(keyword in query_lower for keyword in keywords):
            category = cat
            break
    
    return category, district


# 이벤트 검사 함수
def check_query_type(query: str) -> str:
    """쿼리 타입을 확인하는 함수"""
    event_keywords = {
        "전시": ["전시", "전시회", "갤러리", "미술관"],
        "공연": ["공연", "연극", "뮤지컬", "오페라"],
        "콘서트": ["콘서트", "라이브", "공연장"]
    }
    
    query_lower = query.lower()
    for category, keywords in event_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return "event"
            
    general_keywords = {
        "카페": ["카페", "커피", "브런치", "디저트"],
        "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는"]
    }
    
    for category, keywords in general_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return "general"
            
    return "general"  # 기본값은 일반 검색


# 마이너 키워드 추출 함수
def extract_minor_keywords(query: str) -> List[str]:
    """쿼리에서 마이너 키워드 추출"""
    keyword_groups = {
        "숨은": ["숨은", "숨겨진", "알려지지 않은", "비밀", "히든", "hidden", "secret", "잘 모르는", "남들이 모르는", "나만 아는", "나만 알고 있는", "붐비지 않는", "한적한"],
        "우연": ["우연히", "우연한", "우연히 발견한", "우연히 알게 된", "우연히 찾은", "우연히 방문한", "우연히 가게 된"],
        "로컬": ["로컬", "현지인", "주민", "동네", "단골", "local", "근처", "주변"]
    }
    
    query_lower = query.lower()
    minor_types = []
    
    for minor_type, keywords in keyword_groups.items():
        if any(keyword in query_lower for keyword in keywords):
            minor_types.append(minor_type)
    
    return minor_types


# 네이버 검색 결과 형식 변환기
def format_naver_results(places: List[Dict]) -> str:
    """네이버 검색 결과를 텍스트로 포맷팅"""
    if not places:
        return "네이버 검색 결과가 없습니다."
        
    result = "=== 네이버 검색 결과 ===\n"
    for i, place in enumerate(places, 1):
        result += f"""
{i}. {place['title']}
   📍 주소: {place['address']}
   🏷️ 분류: {place['category']}
   🔍 링크: {place.get('link', 'N/A')}
"""
    return result


# 문서 형식 변환기
def format_documents(docs: List[Document]) -> str:
    """문서 목록을 텍스트로 포맷팅"""
    if not docs:
        return "관련 문서를 찾지 못했습니다."
        
    result = "=== RAG 검색 결과 ===\n"
    for i, doc in enumerate(docs, 1):
        content = doc.page_content
        
        # 메타데이터에서 정보 추출
        url = doc.metadata.get("url", "None")
        title = doc.metadata.get("title", f"장소 {i}")
        
        # 위치 정보 추출 개선
        location = doc.metadata.get("location", "")
        address = doc.metadata.get("address", "")
        address_detail = doc.metadata.get("address_detail", "")
        
        # 위치 정보 통합
        location_info = "정보 없음"
        if location or address or address_detail:
            parts = []
            if location: 
                parts.append(location)
            if address:
                parts.append(address)
            if address_detail:
                parts.append(address_detail)
            location_info = " ".join(parts)
        
        # 위치 정보가 없는 경우 본문에서 주소 패턴 찾기
        if location_info == "정보 없음" and content:
            # 본문에서 "위치:" 또는 "주소:" 패턴 찾기
            lower_content = content.lower()
            
            # 주소 패턴 검색
            address_indicators = ["위치:", "주소:", "서울", "대한민국"]
            for indicator in address_indicators:
                if indicator.lower() in lower_content:
                    start_idx = lower_content.find(indicator.lower())
                    if start_idx >= 0:
                        # 주소 정보가 있는 문장 추출
                        end_idx = lower_content.find("\n", start_idx)
                        if end_idx < 0:
                            end_idx = len(lower_content)
                        address_text = content[start_idx:end_idx].strip()
                        if address_text:
                            location_info = address_text
                            break
        
        result += f"""
{i}. {title}
   📍 위치: {location_info}
   📝 설명: {content[:200]}{'...' if len(content) > 200 else ''}
   🔍 URL: {url}
"""
    return result 