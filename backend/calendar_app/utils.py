import requests
import datetime
import logging
import re

# 로깅 설정
logger = logging.getLogger(__name__)

# 기상청 API 정보
KMA_MID_API = "http://apis.data.go.kr/1360000/MidFcstInfoService/getMidFcst"
KMA_SHORT_API = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
SERVICE_KEY = "r%2BPaRCx%2FnPqwl4wHoqkGLV%2B3V8E0yU8angC8RSjJGIxrHqvEI3qVYQwWJb3lP5xjY38zDp0UKaAsQw9mptNzqQ%3D%3D"

def get_base_time():
    """아침, 점심, 저녁 기준으로 `base_time` 설정"""
    now = datetime.datetime.now()
    hour = now.hour

    if hour < 6:
        return "2300"
    elif hour < 12:
        return "0500"
    elif hour < 18:
        return "1100"
    else:
        return "1700"

# (1) 날씨 상태를 아이콘으로 변환하는 함수 (중기예보용)
def get_weather_icon(sky=None, pty=None, description=None):
    try:
        logger.info(f"날씨 아이콘 변환 - sky: {sky}, pty: {pty}, description: {description}")
        
        # 단기예보의 경우 (sky와 pty가 주어진 경우)
        if sky is not None and pty is not None:
            # 문자열로 변환
            sky_str = str(sky)
            pty_str = str(pty)
            
            if pty_str == "1":
                icon = "🌧️"  # 비
            elif pty_str == "2":
                icon = "🌦️"  # 비/눈
            elif pty_str == "3":
                icon = "❄️"  # 눈
            elif pty_str == "4":
                icon = "🌩️"  # 소나기
            else:
                icon = "☀️" if sky_str == "1" else "🌤️" if sky_str == "3" else "☁️"
            
            logger.info(f"단기예보 아이콘 결정: {icon} (sky={sky_str}, pty={pty_str})")
            return icon
                
        # 중기예보의 경우 (description이 주어진 경우)
        elif description:
            icon = None
            if "맑" in description:
                icon = "☀️"
            elif "구름" in description:
                icon = "🌤️"
            elif "흐림" in description:
                icon = "☁️"
            elif "비" in description:
                icon = "🌧️"
            elif "눈" in description:
                icon = "❄️"
            else:
                icon = "❓"
                
            logger.info(f"중기예보 아이콘 결정: {icon} (description에서)")
            return icon
        else:
            logger.warning("아이콘 결정에 필요한 데이터 없음")
            return "❓"
    except Exception as e:
        logger.error(f"날씨 아이콘 변환 오류: {str(e)}")
        return "❓"  # 오류 발생 시 기본 아이콘 반환

# (2) 단기예보 가져오기
def get_short_term_weather(nx=60, ny=127):
    """단기 예보에서 필요한 데이터만 필터링하여 가져오기"""
    try:
        today = datetime.datetime.today().strftime("%Y%m%d")
        base_time = get_base_time()
        
        params = {
            "serviceKey": SERVICE_KEY,
            "numOfRows": "300",  # 더 많은 데이터를 위해 증가
            "pageNo": "1",
            "dataType": "JSON",
            "base_date": today,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }
        
        logger.info(f"단기예보 API 호출: 날짜={today}, 기준시간={base_time}")
        response = requests.get(KMA_SHORT_API, params=params, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"단기예보 API 오류: 상태 코드 {response.status_code}")
            return get_sample_hourly_weather()  # 샘플 데이터 반환
            
        data = response.json()
        
        if "response" not in data or "body" not in data["response"] or "items" not in data["response"]["body"]:
            logger.error("단기예보 API 응답 형식 오류")
            return get_sample_hourly_weather()  # 샘플 데이터 반환

        items = data["response"]["body"]["items"]["item"]
        
        # 날짜-시간별 데이터 저장 (키: "날짜_시간")
        weather_data = {}
        
        # 4시간 간격으로 6개 시간대 설정 (하루 24시간 커버)
        target_times = ["0000", "0400", "0800", "1200", "1600", "2000"]
        
        for item in items:
            date = item["fcstDate"]
            time = item["fcstTime"]
            
            # API가 제공하는 시간이 정확히 4시간 간격이 아닐 수 있으므로 가장 가까운 시간대로 매핑
            # 예: 0300은 0400에 가까우므로 0400으로 처리
            matching_time = get_nearest_time(time, target_times)
            
            if not matching_time:
                continue
                
            # 날짜_시간 형식의 키 생성
            key = f"{date}_{matching_time}"
            
            # 해당 키의 데이터가 없으면 초기화
            if key not in weather_data:
                weather_data[key] = {
                    "date": date,
                    "time": matching_time,
                    "temperature": None,
                    "sky": None,
                    "pty": None,
                    "rain_probability": None,
                    "icon": None
                }
            
            # 각 카테고리별 데이터 저장
            if item["category"] == "TMP":  # 기온
                value = item["fcstValue"]
                if value != "-999":
                    weather_data[key]["temperature"] = value
            elif item["category"] == "POP":  # 강수 확률
                value = item["fcstValue"]
                if value != "-999":
                    weather_data[key]["rain_probability"] = value
            elif item["category"] == "SKY":  # 하늘 상태
                value = item["fcstValue"]
                if value != "-999":
                    weather_data[key]["sky"] = value
            elif item["category"] == "PTY":  # 강수 형태
                value = item["fcstValue"]
                if value != "-999":
                    weather_data[key]["pty"] = value
        
        # 아이콘 생성 및 필요 없는 필드 제거
        result = []
        
        for key, item in weather_data.items():
            # sky와 pty 데이터로 아이콘 생성
            if item["sky"] and item["pty"] is not None:
                item["icon"] = get_weather_icon(item["sky"], item["pty"])
            elif item["sky"]:  # sky만 있는 경우
                item["icon"] = get_weather_icon(sky=item["sky"], pty="0")
            elif item["pty"] is not None:  # pty만 있는 경우
                item["icon"] = get_weather_icon(sky="1", pty=item["pty"])
            else:
                item["icon"] = "☀️"  # 기본 아이콘
            
            # 필요 없는 필드 제거
            item.pop("sky", None)
            item.pop("pty", None)
            
            # 필수 데이터가 모두 있는 경우만 결과에 포함
            if item["temperature"] and item["rain_probability"] and item["icon"]:
                result.append(item)
        
        # 날짜와 시간순으로 정렬
        result.sort(key=lambda x: (x["date"], x["time"]))
        
        # 결과가 없으면 샘플 데이터 반환
        if not result:
            logger.warning("처리된 날씨 데이터가 없습니다. 샘플 데이터 사용")
            return get_sample_hourly_weather()
            
        logger.info(f"단기예보 처리 결과: {len(result)}개 항목 생성")
        return result
    except Exception as e:
        logger.error(f"단기예보 처리 오류: {str(e)}")
        return get_sample_hourly_weather()  # 오류 발생 시 샘플 데이터 반환

def get_nearest_time(time_str, target_times):
    """
    주어진 시간에 가장 가까운 목표 시간대 반환
    예: "0230"이 주어지면 ["0000", "0400", ...]에서 "0400" 반환
    """
    if time_str in target_times:
        return time_str
        
    hour = int(time_str[:2])
    
    # 가장 가까운 목표 시간대 찾기
    target_hours = [int(t[:2]) for t in target_times]
    
    # 시간 차이 계산 (24시간 기준, 순환)
    distances = []
    for target_hour in target_hours:
        # 정방향 거리
        forward_dist = (target_hour - hour) % 24
        # 역방향 거리
        backward_dist = (hour - target_hour) % 24
        # 더 작은 거리 선택
        distances.append(min(forward_dist, backward_dist))
    
    # 가장 가까운 시간대 인덱스
    nearest_idx = distances.index(min(distances))
    return target_times[nearest_idx]

def get_sample_hourly_weather():
    """6개 시간대(4시간 간격)의 샘플 날씨 데이터 생성"""
    today = datetime.datetime.today().strftime("%Y%m%d")
    
    # 4시간 간격 6개 시간대
    times = ["0000", "0400", "0800", "1200", "1600", "2000"]
    
    # 온도 변화 패턴 (일반적인 하루 온도 변화)
    temperatures = ["2", "0", "4", "8", "6", "3"]
    
    # 날씨 아이콘 변화 패턴
    icons = ["🌤️", "❄️", "☁️", "☀️", "🌤️", "☁️"]
    
    # 강수확률 변화 패턴
    rain_probs = ["10", "30", "20", "5", "10", "15"]
    
    sample_data = []
    
    for i, time in enumerate(times):
        sample_data.append({
            "date": today,
            "time": time,
            "temperature": temperatures[i],
            "rain_probability": rain_probs[i],
            "icon": icons[i]
        })
    
    return sample_data

# (3) 중기예보 텍스트 분석 함수
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

# (4) 중기예보 가져오기
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
        logger.error(f"중기예보 처리 오류: {str(e)}")
        return []

# (5) 날씨 데이터 가져오기 (단기예보 + 중기예보 결합)
def get_full_weather():
    try:
        # 오늘 날짜
        today = datetime.datetime.today()
        today_str = today.strftime("%Y%m%d")
        logger.info(f"날씨 데이터 가져오기 시작 - 오늘 날짜: {today_str}")
        
        # 1. 단기예보 데이터 가져오기
        short_term_data = get_short_term_weather()
        logger.info(f"단기예보 데이터 개수: {len(short_term_data)}")
        
        # 2. 중기예보 데이터 가져오기
        mid_term_data = get_mid_term_weather()
        logger.info(f"중기예보 데이터 개수: {len(mid_term_data) if mid_term_data else 0}")
        
        if not mid_term_data:
            mid_term_data = generate_sample_weather_data()
            logger.info("중기예보 데이터 없음, 샘플 데이터 사용")
        
        # 3. 오늘 날짜에 단기예보 적용, 나머지 날짜에 중기예보 적용
        final_weather_data = []
        
        # 단기예보에서 오늘 데이터 추출 및 로깅
        logger.info(f"단기예보 데이터 모두 출력: {short_term_data}")
        
        # 단기예보에서 오늘 데이터만 추출
        today_data = None
        for item in short_term_data:
            logger.info(f"단기예보 항목 날짜 비교: {item['date']} vs 오늘({today_str})")
            if item["date"] == today_str:
                if "icon" in item and item["icon"] is not None:
                    today_data = item
                    logger.info(f"오늘 단기예보 데이터 찾음: {item}")
                    break
                else:
                    logger.warning(f"오늘 단기예보 데이터에 아이콘 없음: {item}")
        
        # 오늘 날짜 단기예보 추가
        if today_data:
            final_weather_data.append(today_data)
            logger.info(f"오늘 날씨 단기예보 적용: {today_str} - {today_data['icon']}")
        else:
            logger.warning("오늘 단기예보 데이터를 찾지 못함")
            # 중기예보에서 오늘 데이터 사용
            for item in mid_term_data:
                if item["date"] == today_str:
                    final_weather_data.append(item)
                    logger.info(f"오늘 날씨 중기예보로 대체: {today_str} - {item['icon']}")
                    break
        
        # 나머지 날짜는 중기예보 적용
        for item in mid_term_data:
            # 오늘 날짜는 이미 추가했으므로 건너뜀
            if item["date"] == today_str:
                continue
            final_weather_data.append(item)
        
        # 날짜순 정렬
        final_weather_data.sort(key=lambda x: x["date"])
        
        logger.info(f"최종 날씨 데이터 개수: {len(final_weather_data)}")
        logger.info(f"최종 날씨 데이터: {final_weather_data}")
        
        return final_weather_data
    except Exception as e:
        logger.error(f"날씨 데이터 처리 오류: {str(e)}")
        return generate_sample_weather_data()

# (6) 샘플 날씨 데이터 생성 (API 실패 시 사용)
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