"""장소 정보에서 서울시 구를 추출하는 에이전트 모듈

이 모듈은 LLM을 사용하여 텍스트에서 장소를 식별하고
해당 장소가 서울의 어느 구에 속하는지 반환합니다.
"""

import os
import json
from typing import Optional, Dict, Any, Tuple
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()


def extract_district_from_place(query: str) -> Optional[str]:
    """
    LLM을 사용하여 쿼리에서 장소를 추출하고 해당 장소가 속한 서울시 구를 반환

    Args:
        query: 사용자 쿼리

    Returns:
        서울시 구 정보 (예: "서울시 서대문구"), 찾지 못한 경우 "서울시"
    """
    try:
        # OpenAI API 키 가져오기
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("OpenAI API 키가 설정되지 않았습니다.")
            return None

        # LLM 모델 초기화
        llm = ChatOpenAI(model="o3-mini", api_key=api_key)

        # LLM에게 전달할 프롬프트
        prompt = f"""
        아래 텍스트에서 장소 이름을 추출하고, 그 장소가 서울의 어느 구에 속하는지 알려주세요.
        결과는 JSON 형식으로 반환해주세요. 장소가 없거나 구를 특정할 수 없으면 null을 반환하세요.
        
        텍스트: {query}
        
        다음 JSON 형식으로 응답해주세요:
        {{
            "place": "추출한 장소 이름 또는 null",
            "district": "서울시 OO구 형식으로 반환 또는 null"
        }}
        
        예시:
        - "신촌역 근처 맛집 추천해줘" -> {{"place": "신촌역", "district": "서울시 서대문구"}}
        - "강남역 데이트 코스" -> {{"place": "강남역", "district": "서울시 강남구"}}
        - "여의도 공원에서 피크닉" -> {{"place": "여의도 공원", "district": "서울시 영등포구"}}
        - "맛있는 피자 먹고 싶어" -> {{"place": null, "district": null}}
        
        가능한 서울시 구 목록: 종로구, 중구, 용산구, 성동구, 광진구, 동대문구, 중랑구, 성북구, 강북구, 도봉구, 노원구, 은평구, 서대문구, 마포구, 양천구, 강서구, 구로구, 금천구, 영등포구, 동작구, 관악구, 서초구, 강남구, 송파구, 강동구
        """

        # LLM 호출
        response = llm.invoke(prompt).content
        print(f"LLM 응답: {response}")

        # JSON 파싱
        try:
            result = json.loads(response)
            district = result.get("district")
            place = result.get("place")

            print(f"추출된 장소: {place}, 추출된 구: {district}")
            return district

        except json.JSONDecodeError:
            print("LLM 응답을 JSON으로 파싱할 수 없습니다.")
            return None

    except Exception as e:
        print(f"장소에서 구 정보 추출 중 오류 발생: {e}")
        return None


def get_place_info(query: str) -> Dict[str, Any]:
    """
    텍스트에서 장소와 구 정보를 모두 추출

    Args:
        query: 사용자 쿼리

    Returns:
        장소와 구 정보를 포함하는 딕셔너리
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"place": None, "district": None}

        llm = ChatOpenAI(model="o3-mini", api_key=api_key)

        prompt = f"""
        아래 텍스트에서 장소 이름을 추출하고, 그 장소가 서울의 어느 구에 속하는지 알려주세요.
        결과는 JSON 형식으로 반환해주세요. 장소가 없거나 구를 특정할 수 없으면 null을 반환하세요.
        
        텍스트: {query}
        
        다음 JSON 형식으로 응답해주세요:
        {{
            "place": "추출한 장소 이름 또는 null",
            "district": "서울 OO구 형식으로 반환 또는 null"
        }}
        
        예시:
        - "신촌역 근처 맛집 추천해줘" -> {{"place": "신촌역", "district": "서울 서대문구"}}
        - "강남역 데이트 코스" -> {{"place": "강남역", "district": "서울 강남구"}}
        - "여의도 공원에서 피크닉" -> {{"place": "여의도 공원", "district": "서울 영등포구"}}
        - "맛있는 피자 먹고 싶어" -> {{"place": null, "district": null}}
        
        가능한 서울시 구 목록: 종로구, 중구, 용산구, 성동구, 광진구, 동대문구, 중랑구, 성북구, 강북구, 도봉구, 노원구, 은평구, 서대문구, 마포구, 양천구, 강서구, 구로구, 금천구, 영등포구, 동작구, 관악구, 서초구, 강남구, 송파구, 강동구
        """

        response = llm.invoke(prompt).content

        try:
            result = json.loads(response)
            return {"place": result.get("place"), "district": result.get("district")}
        except json.JSONDecodeError:
            return {"place": None, "district": None}

    except Exception:
        return {"place": None, "district": None}


def extract_location_and_category(query: str) -> Dict[str, str]:
    """
    쿼리에서 장소와 카테고리만 추출하여 간결한 검색어 생성

    Args:
        query: 사용자 쿼리 (예: "신촌역 데이트하기 좋은 맛집 추천해줘")

    Returns:
        간결한 검색어 (예: "신촌역 맛집")와 추출된 정보를 포함한 딕셔너리
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("OpenAI API 키가 설정되지 않았습니다.")
            return {"simplified_query": query, "location": None, "category": None}

        # LLM 모델 초기화
        llm = ChatOpenAI(model="o3-mini", api_key=api_key)

        # LLM에게 전달할 프롬프트
        prompt = f"""
        아래 쿼리에서 장소명과 카테고리(예: 맛집, 카페, 전시, 공연 등)만 추출해주세요.
        추출한 정보를 바탕으로 "장소명 카테고리" 형태의 간결한 검색어를 만들어주세요.
        
        쿼리: {query}
        
        다음 JSON 형식으로 응답해주세요:
        {{
            "simplified_query": "장소명 카테고리 (예: 신촌역 맛집)",
            "location": "추출한 장소명",
            "category": "추출한 카테고리"
        }}
        
        예시:
        - "신촌역 데이트하기 좋은 맛집 추천해줘" -> {{"simplified_query": "신촌역 맛집", "location": "신촌역", "category": "맛집"}}
        - "강남역 주변에 친구랑 가기 좋은 카페 알려줘" -> {{"simplified_query": "강남역 카페", "location": "강남역", "category": "카페"}}
        - "여의도 공원에서 가까운 전시회 있을까?" -> {{"simplified_query": "여의도 전시", "location": "여의도", "category": "전시"}}
        - "재미있는 공연 보고 싶어" -> {{"simplified_query": "공연", "location": null, "category": "공연"}}
        
        장소명이나 카테고리가 없으면 null로 표시하고, simplified_query는 있는 정보만으로 구성하세요.
        """

        # LLM 호출
        response = llm.invoke(prompt).content
        print(f"LLM 검색어 간소화 응답: {response}")

        # JSON 파싱
        try:
            result = json.loads(response)
            simplified_query = result.get("simplified_query", query)
            location = result.get("location")
            category = result.get("category")

            print(
                f"간소화된 검색어: '{simplified_query}' (장소: {location}, 카테고리: {category})"
            )
            return {
                "simplified_query": simplified_query,
                "location": location,
                "category": category,
            }

        except json.JSONDecodeError:
            print("LLM 응답을 JSON으로 파싱할 수 없습니다.")
            return {"simplified_query": query, "location": None, "category": None}

    except Exception as e:
        print(f"검색어 간소화 중 오류 발생: {e}")
        return {"simplified_query": query, "location": None, "category": None}


# 서울시 구별 주요 랜드마크 정보 (필요시 활용)
DISTRICT_LANDMARKS = {
    "종로구": [
        "경복궁",
        "광화문",
        "인사동",
        "북촌한옥마을",
        "창덕궁",
        "종로",
        "안국동",
        "삼청동",
    ],
    "중구": [
        "명동",
        "남대문시장",
        "을지로",
        "동대문",
        "서울역",
        "남산타워",
        "시청",
        "충무로",
    ],
    "용산구": ["이태원", "용산역", "국립중앙박물관", "전쟁기념관", "한남동", "서울역"],
    "성동구": ["왕십리", "성수동", "서울숲", "응봉산", "금호동", "옥수동"],
    "광진구": ["건대입구", "건국대학교", "어린이대공원", "구의역", "광나루", "뚝섬"],
    "동대문구": ["경희대학교", "이문동", "외대", "청량리", "장안동", "제기동", "홍릉"],
    "중랑구": ["망우산", "중랑천", "면목동", "상봉동", "태릉"],
    "성북구": ["고려대학교", "성신여대", "한성대입구", "길음동", "정릉", "돈암동"],
    "강북구": ["북한산", "수유리", "미아동", "번동", "우이동"],
    "도봉구": ["도봉산", "쌍문동", "방학동", "창동"],
    "노원구": ["노원역", "태릉", "상계동", "중계동", "공릉동"],
    "은평구": ["은평뉴타운", "불광동", "연신내", "역촌동", "진관동"],
    "서대문구": ["신촌", "이대", "연대", "연세대학교", "홍제동", "홍은동", "북가좌동"],
    "마포구": ["홍대입구", "합정", "연남동", "망원동", "상암동", "공덕동", "한강공원"],
    "양천구": ["목동", "신정동", "신월동", "목동운동장"],
    "강서구": ["김포공항", "방화동", "화곡동", "발산역", "마곡동"],
    "구로구": ["구로디지털단지", "신도림", "대림동", "구로역"],
    "금천구": ["가산디지털단지", "독산동", "시흥동"],
    "영등포구": ["여의도", "영등포역", "타임스퀘어", "문래동", "당산동"],
    "동작구": ["노량진", "상도동", "사당동", "이수"],
    "관악구": ["서울대학교", "신림동", "봉천동", "낙성대"],
    "서초구": ["강남역", "교대역", "반포동", "방배동", "서초동", "고속터미널"],
    "강남구": [
        "강남역",
        "삼성동",
        "코엑스",
        "청담동",
        "압구정동",
        "역삼동",
        "논현동",
        "신사동",
        "선릉",
    ],
    "송파구": ["잠실", "롯데월드", "석촌호수", "방이동", "올림픽공원", "가락시장"],
    "강동구": ["천호동", "길동", "강일동", "명일동", "둔촌동", "암사동"],
}
