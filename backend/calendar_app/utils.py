import requests
import datetime
import logging
import re

# 로깅 설정
logger = logging.getLogger(__name__)

# 기상청 API 정보
KMA_MID_API = "http://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst"
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
# 단기예보에서 하루에 6번 데이터만 가져오기
NEEDED_TIMES = ["0600", "0900", "1200", "1500", "1800", "2100"]

# SKY 코드에 따른 아이콘 매핑
SKY_ICON_MAP = {
    "1": "☀️",  # 맑음
    "3": "🌤️",  # 구름 많음
    "4": "☁️"   # 흐림
}

# PTY 코드에 따른 아이콘 매핑 (강수 형태)
PTY_ICON_MAP = {
    "0": None,  # 강수 없음
    "1": "🌧️",  # 비
    "2": "🌦️",  # 비/눈
    "3": "❄️",  # 눈
    "4": "🌩️"   # 소나기
}

def get_short_term_weather(nx=60, ny=127):
    """단기예보 (오늘~3일 후)에서 하루 6번 아이콘만 반환"""
    try:
        today = datetime.datetime.today().strftime("%Y%m%d")  # 오늘 날짜
        base_time = "0500"  # 예보 발표 시간
        
        logger.info(f"단기예보 API 호출: 날짜={today}, 기준시간={base_time}")
        
        # Postman과 동일한 방식으로 URL 직접 구성
        url = f"{KMA_SHORT_API}?serviceKey={SERVICE_KEY}"
        url += f"&numOfRows=1000&pageNo=1&dataType=JSON"
        url += f"&base_date={today}&base_time={base_time}"
        url += f"&nx={nx}&ny={ny}"
        
        logger.info(f"요청 URL: {url}")
        
        response = requests.get(url, timeout=15)
        
        logger.info(f"단기예보 API 응답 상태 코드: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"단기예보 API 오류: 상태 코드 {response.status_code}")
            return []
            
        data = response.json()
        
        if "response" not in data or "body" not in data["response"] or "items" not in data["response"]["body"]:
            logger.error("단기예보 API 응답 형식 오류")
            return []
            
        items = data["response"]["body"]["items"]["item"]
        logger.info(f"API 응답 항목 수: {len(items)}")
        
        # 날짜-시간별 데이터 저장
        weather_data = {}
        today_int = int(today)  # 오늘 날짜 정수형
        
        # 먼저 필요한 날짜와 시간 조합 생성 (오늘부터 3일간, 6개 시간대)
        needed_date_times = set()
        for i in range(4):  # 오늘 포함 4일간
            target_date = datetime.datetime.today() + datetime.timedelta(days=i)
            target_date_str = target_date.strftime("%Y%m%d")
            for time in NEEDED_TIMES:
                needed_date_times.add(f"{target_date_str}_{time}")
        
        logger.info(f"필요한 날짜/시간 조합: {len(needed_date_times)}개")
        
        # 모든 예보 항목 처리
        for item in items:
            fcst_date = item["fcstDate"]  # 예보 날짜 (YYYYMMDD)
            fcst_time = item["fcstTime"]  # 예보 시간 (HHMM)
            
            # 오늘부터 3일 후까지만 필터링
            if int(fcst_date) < today_int or int(fcst_date) > today_int + 3:
                continue
            
            # 정확히 지정된 6개 시간대만 필터링
            if fcst_time not in NEEDED_TIMES:
                continue
                
            # 날짜_시간 형식의 키 생성
            key = f"{fcst_date}_{fcst_time}"
            
            # 해당 키의 데이터가 없으면 초기화
            if key not in weather_data:
                weather_data[key] = {
                    "date": fcst_date,
                    "time": fcst_time,
                    "temperature": None,
                    "rain_probability": None,
                    "sky": None,
                    "pty": None,
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
        
        logger.info(f"필터링 후 날짜/시간별 데이터: {len(weather_data)}개")
        
        # 두 번째 루프: 아이콘 생성 및 최종 결과물 구성
        result = []
        
        for key, item in weather_data.items():
            # 아이콘 결정 로직
            icon = None
            
            # 강수 형태(PTY)가 있고 강수가 있는 경우 (비, 눈 등)
            if item["pty"] and item["pty"] != "0":
                icon = PTY_ICON_MAP.get(item["pty"], "❓")
            # 하늘 상태(SKY)로 아이콘 결정
            elif item["sky"]:
                icon = SKY_ICON_MAP.get(item["sky"], "❓")
            else:
                icon = "☀️"  # 기본 아이콘을 맑음으로 설정
            
            item["icon"] = icon
            
            # 필수 데이터가 없는 경우 기본값 설정
            if not item["temperature"]:
                item["temperature"] = "15"
            if not item["rain_probability"]:
                item["rain_probability"] = "10"
            
            # 필요 없는 필드 제거
            item.pop("sky", None)
            item.pop("pty", None)
            result.append(item)
        
        # 날짜와 시간순으로 정렬
        result.sort(key=lambda x: (x["date"], x["time"]))
        
        logger.info(f"최종 단기예보 데이터: {len(result)}개 항목")
        
        # 결과가 없으면 샘플 데이터 생성
        if not result:
            logger.warning("처리된 날씨 데이터가 없어 샘플 데이터 생성")
            sample_data = []
            for i in range(3):  # 오늘부터 2일간
                date = datetime.datetime.today() + datetime.timedelta(days=i)
                date_str = date.strftime("%Y%m%d")
                for time in NEEDED_TIMES:  # 6개 시간대
                    sample_data.append({
                        "date": date_str,
                        "time": time,
                        "temperature": "15",
                        "rain_probability": "10",
                        "icon": "☀️"  # 기본 아이콘
                    })
            return sample_data
            
        return result
    except Exception as e:
        logger.error(f"단기예보 처리 오류: {str(e)}")
        return []

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

# (3) 중기예보 가져오기
def get_mid_term_weather():
    """중기예보 (4~10일 후) 데이터 가져오기"""
    try:
        reg_id = "11B00000"  # 서울/경기 지역
        today = datetime.datetime.today().strftime("%Y%m%d")
        tmFc = f"{today}0600"
        
        # API URL 직접 구성
        url = f"{KMA_MID_API}?serviceKey={SERVICE_KEY}"
        url += f"&numOfRows=10&pageNo=1&dataType=JSON"
        url += f"&regId={reg_id}&tmFc={tmFc}"
        
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return []
            
        data = response.json()
        
        if "response" not in data or "body" not in data["response"] or "items" not in data["response"]["body"]:
            return []

        items = data["response"]["body"]["items"]["item"]
        
        if not items or len(items) == 0:
            return []
            
        # 첫 번째 아이템 사용
        forecast_item = items[0]
        
        # 결과 저장
        weather_data = []
        
        # 4~10일 후 날씨 데이터 생성
        for i in range(4, 11):
            forecast_date = datetime.datetime.today() + datetime.timedelta(days=i)
            date_str = forecast_date.strftime("%Y%m%d")
            
            # 날씨 상태 키
            am_sky_key = f"wf{i}Am"
            pm_sky_key = f"wf{i}Pm"
            sky_key = f"wf{i}"  # 일별 통합 키
            
            # 날씨 상태 가져오기 (AM/PM/일별 모두 확인)
            sky_description = None
            if am_sky_key in forecast_item:
                sky_description = forecast_item[am_sky_key]
            elif pm_sky_key in forecast_item:
                sky_description = forecast_item[pm_sky_key]
            elif sky_key in forecast_item:
                sky_description = forecast_item[sky_key]
            
            if sky_description:
                # 날씨 아이콘 결정
                icon = get_weather_icon(description=sky_description)
                
                # 온도 추출 시도 (없을 경우 기본값 사용)
                temp_min_key = f"taMin{i}"
                temp_max_key = f"taMax{i}"
                
                temp_min = forecast_item.get(temp_min_key, "")
                temp_max = forecast_item.get(temp_max_key, "")
                
                # 온도 표시 (최저/최고 온도가 있는 경우)
                temperature = ""
                if temp_min and temp_max:
                    temperature = f"{temp_min}~{temp_max}"
                elif temp_min:
                    temperature = temp_min
                elif temp_max:
                    temperature = temp_max
                else:
                    temperature = "15"  # 기본값
                
                # 강수확률 추출 시도
                am_rain_key = f"rnSt{i}Am"
                pm_rain_key = f"rnSt{i}Pm"
                rain_key = f"rnSt{i}"
                
                rain_probability = "10"  # 기본값
                if am_rain_key in forecast_item and pm_rain_key in forecast_item:
                    am_prob = forecast_item[am_rain_key]
                    pm_prob = forecast_item[pm_rain_key]
                    rain_probability = str(max(int(am_prob), int(pm_prob)))
                elif am_rain_key in forecast_item:
                    rain_probability = forecast_item[am_rain_key]
                elif pm_rain_key in forecast_item:
                    rain_probability = forecast_item[pm_rain_key]
                elif rain_key in forecast_item:
                    rain_probability = forecast_item[rain_key]
                
                daily_weather = {
                    "date": date_str,
                    "temperature": temperature,
                    "rain_probability": rain_probability,
                    "icon": icon,
                    "description": sky_description
                }
                weather_data.append(daily_weather)
            else:
                # 날씨 데이터가 없는 경우 기본값 설정
                daily_weather = {
                    "date": date_str,
                    "temperature": "15",
                    "rain_probability": "10",
                    "icon": "❓",  # 기본 아이콘을 물음표로 변경
                    "description": "정보 없음"
                }
                weather_data.append(daily_weather)
        
        return weather_data
    except Exception as e:
        return []

# (5) 날씨 데이터 가져오기 (단기예보 + 중기예보 결합)
def get_full_weather():
    try:
        # 오늘 날짜
        today = datetime.datetime.today()
        today_str = today.strftime("%Y%m%d")
        logger.info(f"날씨 데이터 가져오기 시작 - 오늘 날짜: {today_str}")
        
        # 1. 단기예보 데이터 가져오기 (오늘~3일 후)
        short_term_data = get_short_term_weather()
        logger.info(f"단기예보 데이터 개수: {len(short_term_data)}")
        
        # 2. 중기예보 데이터 가져오기 (4~10일 후)
        mid_term_data = get_mid_term_weather()
        logger.info(f"중기예보 데이터 개수: {len(mid_term_data) if mid_term_data else 0}")
        
        # 3. 결과 데이터 준비
        final_weather_data = []
        
        # 4. 단기예보 데이터 처리 (날짜별로 그룹화)
        short_term_by_date = {}
        for item in short_term_data:
            date = item["date"]
            if date not in short_term_by_date:
                short_term_by_date[date] = []
            short_term_by_date[date].append(item)
        
        logger.info(f"단기예보 날짜 수: {len(short_term_by_date)}")
        
        # 5. 단기예보 데이터 먼저, 그 다음 중기예보 데이터 적용
        # 단기예보와 중기예보 날짜 추출
        short_term_dates = set(short_term_by_date.keys())
        mid_term_dates = set(item["date"] for item in mid_term_data) if mid_term_data else set()
        
        # 단기예보 날짜 먼저 처리 (오늘~3일)
        for date in sorted(short_term_dates):
            items = short_term_by_date[date]
            final_weather_data.extend(items)
            logger.info(f"날짜 {date}에 단기예보 {len(items)}개 항목 추가")
        
        # 중기예보 날짜 처리 (단기예보에 없는 날짜만)
        for date in sorted(mid_term_dates):
            if date not in short_term_dates:  # 단기예보에 없는 날짜만
                mid_items = [item for item in mid_term_data if item["date"] == date]
                final_weather_data.extend(mid_items)
                logger.info(f"날짜 {date}에 중기예보 {len(mid_items)}개 항목 추가")
        
        # 날짜순, 시간순 정렬
        final_weather_data.sort(key=lambda x: (x["date"], x.get("time", "0000")))
        
        logger.info(f"최종 날씨 데이터 개수: {len(final_weather_data)}개 항목")
        
        return final_weather_data
    except Exception as e:
        logger.error(f"날씨 데이터 처리 오류: {str(e)}")
        return []

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