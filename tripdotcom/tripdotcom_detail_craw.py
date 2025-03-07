from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.common.keys import Keys
from tqdm import tqdm
from datetime import datetime
import re


# ----함수 정의---
# 특수문자 제거 함수
def clean_text(text):
    text = re.sub(r'[^\w\s\[\]().,~\-:년월일]', '', text)
    text = ' '.join(text.split())
    return text


# ----크롤링 시작----
# 웹드라이버 설정
options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

## 크롬 드라이버 실행
driver = webdriver.Chrome(options=options)
driver.implicitly_wait(3)  # 페이지 로딩 대기

# 크롤링 시작 시간 기록
start_time = datetime.now()
print(f"크롤링 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# 크롤링할 페이지 URL
url = "https://kr.trip.com/events/2764875-2025-03-south-korea-collection/"
driver.get(url)  # 페이지 접속
time.sleep(5)  # 페이지 로딩 대기

# 서울 지역 선택
try:
    # 위치 선택 버튼 클릭
    location_button = driver.find_element(By.XPATH, "//div[@class='select-tagname']/span[text()='위치']/..")
    location_button.click()
    time.sleep(2)

    # 서울 옵션 선택
    seoul_option = driver.find_element(By.XPATH, "//div[contains(@class, 'city-item') and contains(text(), '서울')]")
    seoul_option.click()
    time.sleep(3)  # 결과 로딩 대기
except Exception as e:
    print("지역 선택 중 오류 발생:", e)

# 스크롤 다운을 위한 함수
def scroll_down():
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
    time.sleep(2)  # 스크롤 후 로딩 대기

# 데이터를 저장할 리스트
data_list = []

page_num = 1
while True:
    print(f"=== {page_num}페이지 크롤링 중 ===")
    # 스크롤을 내리면서 크롤링 (최대 3번 스크롤)
    for _ in range(3):
        scroll_down()

    # 카드 리스트 크롤링 (HTML 구조에 맞게 수정)
    print("카드 리스트 찾는 중...")
    cardlist = driver.find_element(By.CLASS_NAME, "cardlist")  # cardlist 클래스 찾기
    cards = cardlist.find_elements(By.CLASS_NAME, "card-item")  # card-item 클래스로 카드 찾기

    print(f"발견된 전체 카드 수: {len(cards)}")

    # ended 태그가 없는 카드만 필터링
    active_cards = []
    for card in cards:
        try:
            # ended 클래스가 있는지 확인
            ended_tags = card.find_elements(By.CLASS_NAME, "end")
            if not ended_tags:  # ended 태그가 없는 경우만 추가
                active_cards.append(card)
                # if len(active_cards) >= 3:  # 6개 채우면 중단
                #     break
        except Exception as e:
            continue

    # 크롤링한 데이터를 저장할 리스트
    for card in tqdm(active_cards, desc="카드 상세 정보 크롤링 중"):
        try:
            # 카드에서 기본 정보 추출
            title = card.find_element(By.CLASS_NAME, "title").text.strip()
            time_info = card.find_element(By.CLASS_NAME, "time").text.strip()
            location = card.find_element(By.CLASS_NAME, "location").text.strip()
            tag = card.find_element(By.CLASS_NAME, "tags").text.strip()

            # 제목에서 | 이전 부분만 사용
            if '|' in title:
                title = title.split('|')[0].strip()

            # 상세 페이지 링크 찾기
            link = card.find_element(By.TAG_NAME, "a").get_attribute("href")
            
            # 새 탭에서 상세 페이지 열기
            driver.execute_script(f"window.open('{link}', '_blank');")
            time.sleep(3)
            
            # 새 탭으로 전환
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            
            # 상세 내용 크롤링
            try:
                content = ""
                content_div = driver.find_element(By.ID, "content")
                paragraphs = content_div.find_elements(By.TAG_NAME, "p")
                
                if paragraphs:
                    content = "\n\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                else:
                    content = "상세 내용을 가져올 수 없습니다."
                    
            except Exception as e:
                content = "상세 내용을 가져올 수 없습니다."
            
            # 카드 상세 페이지에서 주소 추가
            try:
                address_div = driver.find_element(By.CLASS_NAME, "address-left")

                if address_div:
                    address = address_div.text.strip()
                else:
                    address = "주소를 가져올 수 없습니다."
            except Exception as e:
                address = "주소를 가져올 수 없습니다."


            # 데이터 리스트에 추가
            data_list.append({
                "tag": tag,
                "title": title,
                "time": time_info,
                "location": location,
                "address": address,
                "content": content
            })
            
            # 원래 탭으로 돌아가기 전에 현재 탭 닫기
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(1)
            
        except Exception as e:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

    # 다음 페이지 버튼 찾기
    try:
        next_button = driver.find_element(By.XPATH, "//button[contains(@class, 'btn-next')]")
        if 'disabled' in next_button.get_attribute('class'):
            print("마지막 페이지 도달")
            break
        next_button.click()
        time.sleep(3)
    except Exception as e:
        print("다음 페이지 버튼을 찾을 수 없음:", e)
        break

    page_num += 1

# 브라우저 종료
driver.quit()

# 중복 제거
seen_events = set()
unique_data_list = []
for event in data_list:
    # 이벤트의 고유 식별자 생성
    event_key = f"{event['tag']}_{event['title']}_{event['time']}_{event['location']}_{event['address']}"
    if event_key not in seen_events:
        seen_events.add(event_key)
        unique_data_list.append(event)

print(f"중복 제거 전 데이터 수: {len(data_list)}")
print(f"중복 제거 후 데이터 수: {len(unique_data_list)}")
print(f"제거된 중복 데이터 수: {len(data_list) - len(unique_data_list)}")

data_list = unique_data_list

# 크롤링 종료 시간 기록
end_time = datetime.now()
duration = end_time - start_time
print(f"크롤링 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"총 소요 시간: {duration}")
print(f"총 {len(data_list)}개의 이벤트가 크롤링되었습니다.")



with open("trip_data/tripdotcom/seoul_events_data_raw.txt", "w", encoding="utf-8") as f:
    # 헤더에서 atmosphere와 companions 제거
    f.write("tag, title, time, location, address, content\n")
    
    for event in data_list:
        # atmosphere와 companions 관련 처리 제거
        f.write(f"{clean_text(event['tag'])}, \"{clean_text(event['title'])}\", {clean_text(event['time'])}, {clean_text(event['location'])}, {clean_text(event['address'])}, \"{clean_text(event['content'])}\"\n")

print("크롤링 완료 - 결과가 txt 파일로 저장되었습니다.")