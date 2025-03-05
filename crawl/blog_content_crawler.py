from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # ChromeDriverManager를 service 객체로 전달
    service = webdriver.ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(3)
    return driver


def read_urls_from_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    return urls


def crawl_blog_contents(urls, titles=None, dates=None):
    driver = setup_driver()
    contents = []
    pattern1 = "<[^>]*>"

    try:
        total_urls = len(urls)
        for idx, url in enumerate(urls, 1):
            print(f"크롤링 진행률: {idx}/{total_urls} ({(idx/total_urls)*100:.1f}%)")
            print(f"현재 URL: {url}")

            try:
                driver.get(url)
                time.sleep(3)  # 로딩 대기

                # iframe 전환
                iframe = driver.find_element(By.ID, "mainFrame")
                driver.switch_to.frame(iframe)

                source = driver.page_source
                html = BeautifulSoup(source, "html.parser")

                content = html.select("div.se-main-container")
                content = "".join(str(content))

                # HTML 태그 제거 및 텍스트 정리
                content = re.sub(pattern=pattern1, repl="", string=content)
                pattern2 = """[\n\n\n\n\n// flash 오류를 우회하기 위한 함수 추가\nfunction _flash_removeCallback() {}]"""
                content = content.replace(pattern2, "")
                content = content.replace("\n", " ")  # 줄바꿈을 공백으로 변경
                content = content.replace("\u200b", "")
                contents.append(content)

            except Exception as e:
                print(f"해당 URL 크롤링 실패: {url}")
                print(f"에러 메시지: {str(e)}")
                contents.append("error")
                continue

    except Exception as e:
        print(f"크롤링 중 에러 발생: {str(e)}")

    finally:
        driver.quit()

    # DataFrame 생성 및 CSV 저장
    data = {"url": urls, "content": contents}
    if titles:
        data["title"] = titles
    if dates:
        data["date"] = dates

    df = pd.DataFrame(data)
    df.to_csv("blog_contents.csv", index=False, encoding="utf-8-sig")
    print("크롤링 완료! 결과가 blog_contents.csv 파일에 저장되었습니다.")
    return df


if __name__ == "__main__":
    # naver_blog_links.txt 파일에서 URL 읽어오기
    urls = read_urls_from_file("naver_blog_links.txt")
    crawl_blog_contents(urls)
