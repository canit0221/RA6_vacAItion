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


def main():
    # 결과를 저장할 디렉토리 생성
    output_dir = "crawled_contents"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 오늘 날짜를 파일명에 포함
    today = date.today().strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"blog_contents_{today}.txt")

    # naver_blog_links.txt 파일에서 URL 읽기
    with open("junggu_blog_links.txt", "r", encoding="utf-8") as f:
        urls = f.readlines()

    # 결과 파일 생성
    with open(output_file, "w", encoding="utf-8") as f:
        # 각 URL에 대해 크롤링 수행
        for i, url in enumerate(urls, 1):
            url = url.strip()
            if url:  # 빈 줄 무시
                print(f"크롤링 중... ({i}/{len(urls)}): {url}")
                content = crawl_blog_content(url)

                # URL과 컨텐츠를 한 줄로 저장
                f.write(f"{url}\t{content}\n")
                print(f"컨텐츠 추가 완료: {url}")

        print(f"\n모든 컨텐츠가 다음 파일에 저장되었습니다: {output_file}")


if __name__ == "__main__":
    main()
