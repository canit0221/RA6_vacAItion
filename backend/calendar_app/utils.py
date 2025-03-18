import requests
import datetime
import logging
import re

# 로깅 설정
logger = logging.getLogger(__name__)

# 기상청 API 정보 (단기 예보 API 제거)
KMA_MID_API = "http://apis.data.go.kr/1360000/MidFcstInfoService/getMidFcst"
SERVICE_KEY = "r%2BPaRCx%2FnPqwl4wHoqkGLV%2B3V8E0yU8angC8RSjJGIxrHqvEI3qVYQwWJb3lP5xjY38zDp0UKaAsQw9mptNzqQ%3D%3D"

# (1) 날씨 상태를 아이콘으로 변환하는 함수
def get_weather_icon(sky=None, pty=None, description=None):
    try:
        # 중기예보에서만 사용하는 부분만 남김
        if description:  # 중기예보에서 wf(날씨 상태) 값을 변환
            # "맑음"이나 "맑겠" 등의 단어 포함 여부 체크
            if "맑" in description:
                return "☀️"
            elif "구름" in description:
                return "🌤️"
            elif "흐림" in description:
                return "☁️"
            elif "비" in description:
                return "🌧️"
            elif "눈" in description:
                return "❄️"
            else:
                return "❓"
        else:
            return "❓"
    except Exception as e:
        logger.error(f"날씨 아이콘 변환 오류: {str(e)}")
        return "❓"  # 오류 발생 시 기본 아이콘 반환

# 단기예보 함수 제거 (get_short_term_weather)

# (2) 중기예보 텍스트 분석 함수
def parse_weather_forecast(description):
    """중기예보 텍스트를 분석하여 날짜별 날씨 상태를 추출"""
    weather_periods = []
    
    # 날짜 패턴: 숫자+일(요일)~숫자+일(요일) 또는 숫자+일(요일)
    # 날씨 상태: 맑음, 구름많음, 흐림, 비, 눈 등
    date_patterns = [
        r'(\d+)일\(.\)~(\d+)일\(.\)은\s+([^,\.]+)',  # 범위 패턴 (예: 22일(금)~23일(토)은 전국이 대체로 맑겠으나)
        r'(\d+)일\(.\)은\s+([^,\.]+)'               # 단일 날짜 패턴 (예: 27일(목)은 대체로 흐리겠습니다)
    ]
    
    # 모든 패턴에 대해 검색
    for pattern in date_patterns:
        matches = re.finditer(pattern, description)
        for match in matches:
            groups = match.groups()
            
            if len(groups) == 3:  # 범위 패턴 (시작일, 종료일, 날씨)
                start_day = int(groups[0])
                end_day = int(groups[1])
                weather_state = groups[2]
                
                # 날씨 상태 정규화
                weather_type = get_weather_type(weather_state)
                
                # 날짜 범위 저장
                weather_periods.append({
                    'start_day': start_day,
                    'end_day': end_day,
                    'weather_type': weather_type
                })
                
            elif len(groups) == 2:  # 단일 날짜 패턴 (날짜, 날씨)
                day = int(groups[0])
                weather_state = groups[1]
                
                # 날씨 상태 정규화
                weather_type = get_weather_type(weather_state)
                
                # 단일 날짜 저장
                weather_periods.append({
                    'start_day': day,
                    'end_day': day,
                    'weather_type': weather_type
                })
        
    return weather_periods

def get_weather_type(text):
    """텍스트에서 날씨 유형 추출"""
    if "맑" in text:
        return "sunny"
    elif "구름" in text or "구름많" in text:
        return "cloudy"
    elif "흐림" in text or "흐리" in text:
        return "overcast"
    elif "비" in text:
        return "rainy"
    elif "눈" in text:
        return "snow"
    else:
        return "unknown"

def get_weather_icon_for_date(date_obj, weather_periods, description):
    """특정 날짜에 해당하는 날씨 아이콘 반환"""
    day = date_obj.day
    
    # 날짜에 해당하는 날씨 기간 찾기
    for period in weather_periods:
        if period['start_day'] <= day <= period['end_day']:
            weather_type = period['weather_type']
            
            # 날씨 유형에 따른 아이콘 반환
            if weather_type == "sunny":
                return "☀️"
            elif weather_type == "cloudy":
                return "🌤️"
            elif weather_type == "overcast":
                return "☁️"
            elif weather_type == "rainy":
                return "🌧️"
            elif weather_type == "snow":
                return "❄️"
    
    # 일치하는 기간을 찾지 못한 경우 기존 방식으로 처리
    return get_weather_icon(description=description)

# (3) 중기예보 가져오기
def get_mid_term_weather(stnId=108):
    try:
        today = datetime.datetime.today().strftime("%Y%m%d")
        tmFc = f"{today}0600"
        
        # Postman에서 성공한 요청 형식 사용
        direct_url = f"http://apis.data.go.kr/1360000/MidFcstInfoService/getMidFcst?serviceKey={SERVICE_KEY}&pageNo=1&numOfRows=10&dataType=JSON&stnId={stnId}&tmFc={tmFc}"
        
        response = requests.get(direct_url, timeout=15)
        
        if response.status_code != 200:
            return []
            
        data = response.json()
        
        weather_data = []
        
        if "response" in data and "body" in data["response"] and "items" in data["response"]["body"]:
            items = data["response"]["body"]["items"]["item"]
            
            # 날씨 설명 가져오기
            weather_description = ""
            if items and len(items) > 0 and "wfSv" in items[0]:
                weather_description = items[0]["wfSv"]
                
                # 날씨 텍스트 분석
                weather_periods = parse_weather_forecast(weather_description)
                
                # 오늘 날짜 기준으로 10일치 날짜 생성
                start_date = datetime.datetime.today()
                
                for i in range(10):  # 10일치 날씨 데이터 생성
                    date = start_date + datetime.timedelta(days=i)
                    date_str = date.strftime("%Y%m%d")
                    
                    # 해당 날짜의 날씨 아이콘 결정
                    icon = get_weather_icon_for_date(date, weather_periods, weather_description)
                    
                    daily_weather = {
                        "date": date_str,
                        "temperature": "20",  # 기본 온도 값
                        "rain_probability": "10",  # 기본 강수확률
                        "icon": icon,
                        "description": weather_description
                    }
                    weather_data.append(daily_weather)
            else:
                return []
        else:
            return []
            
        return weather_data
    except Exception as e:
        return []

# (4) 날씨 데이터 가져오기 (중기예보만 사용)
def get_full_weather():
    try:
        # 중기예보만 사용
        weather_data = get_mid_term_weather()
        
        if weather_data:
            return weather_data
        else:
            return generate_sample_weather_data()
    except Exception as e:
        return generate_sample_weather_data()

# (5) 샘플 날씨 데이터 생성 (API 실패 시 사용)
def generate_sample_weather_data():
    today = datetime.datetime.today()
    sample_data = []
    
    # 10일치 샘플 데이터 생성
    for i in range(10):
        date = today + datetime.timedelta(days=i)
        date_str = date.strftime("%Y%m%d")
        
        # 기본 아이콘 순환 (맑음, 구름많음, 흐림)
        icons = ["☀️", "🌤️", "☁️"]
        
        sample_data.append({
            "date": date_str,
            "temperature": "20",  # 기본 온도
            "rain_probability": "10",  # 기본 강수확률
            "icon": icons[i % 3],  # 아이콘 순환
            "description": "API 연결 실패로 인한 샘플 데이터"
        })
    
    return sample_data