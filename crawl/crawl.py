# 네이버 검색 API 예제 - 블로그 검색
from datetime import date
import os
import sys
import json
import urllib.request
import urllib.parse
import requests
from bs4 import BeautifulSoup
import time
from tqdm import tqdm
import re


def crawl_blog_content(blog_url):
    try:
        # 과도한 요청 방지를 위한 딜레이
        time.sleep(0.0005)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        # 네이버 블로그 모바일 버전 URL로 변환
        if "blog.naver.com" in blog_url:
            blog_url = blog_url.replace("blog.naver.com", "m.blog.naver.com")

        response = requests.get(blog_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 모바일 버전 네이버 블로그의 본문 내용 찾기
        content = soup.select_one(".se-main-container")  # 일반 에디터
        if not content:
            content = soup.select_one(".post-view")  # 구버전 에디터
        if not content:
            content = soup.select_one("#viewTypeSelector")  # 다른 형식

        if content:
            # HTML 태그 제거 및 텍스트 정리
            text = content.get_text(
                separator="\t", strip=True
            )  # 줄바꿈 대신 탭으로 구분
            return text.replace("\n", "\t")  # 남아있는 줄바꿈을 탭으로 변경
        else:
            return "블로그 내용을 찾을 수 없습니다."

    except Exception as e:
        return f"크롤링 중 오류 발생: {e}"


def clean_blog_content(text):
    """블로그 컨텐츠 정제"""
    # 불필요한 태그/기호 제거
    text = re.sub(r"Previous image|Next image|​", "", text)

    # 연속된 탭을 하나의 공백으로 변경
    text = re.sub(r"\t+", " ", text)

    # 연속된 공백 정리
    text = re.sub(r" +", " ", text)

    # 앞뒤 공백 제거
    text = text.strip()

    # 기본 정보 추출 시도
    place_info = {"name": "", "address": "", "hours": "", "menu": [], "review": text}

    # 주소 추출 시도 (서울 ... 형식)
    address_match = re.search(
        r"서울\s+\S+구\s+\S+[로길]\s*\d+(?:-\d+)?(?:\s+\S+)?", text
    )
    if address_match:
        place_info["address"] = address_match.group()

    # 영업시간 추출 시도
    hours_match = re.search(r"(?:영업시간|운영시간)\s*:?\s*([^\n]+)", text)
    if hours_match:
        place_info["hours"] = hours_match.group(1).strip()

    # 가게명 추출 시도 (주소 앞에 있는 이름)
    if place_info["address"]:
        name_match = re.search(
            r"([^\n]+)(?=.*?" + re.escape(place_info["address"]) + ")", text
        )
        if name_match:
            place_info["name"] = name_match.group(1).strip()

    return place_info


def main():
    # 결과를 저장할 디렉토리 생성
    output_dir = "crawled_contents"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 오늘 날짜를 파일명에 포함
    today = date.today().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"blog_contents_{today}.txt")

    # naver_blog_links.txt 파일에서 URL 읽기
    with open("search_500.txt", "r", encoding="utf-8") as f:
        urls = f.readlines()

    # 결과 파일 생성
    with open(output_file, "w", encoding="utf-8") as f:
        # tqdm으로 진행률 표시 추가
        for url in tqdm(urls, desc="블로그 크롤링 진행률", unit="개"):
            url = url.strip()
            if url:  # 빈 줄 무시
                content = crawl_blog_content(url)
                cleaned_content = clean_blog_content(content)
                # JSON 형식으로 저장
                output = {"url": url, "content": cleaned_content}
                f.write(json.dumps(output, ensure_ascii=False) + "\n")

        print(f"\n모든 컨텐츠가 다음 파일에 저장되었습니다: {output_file}")


if __name__ == "__main__":
    main()
