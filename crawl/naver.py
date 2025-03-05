# 네이버 검색 API 예제 - 블로그 검색
from datetime import date
import os
import sys
import json
import urllib.request
import urllib.parse
import requests
from bs4 import BeautifulSoup


def naver_blog_search(search_word, display=10, sort="date"):
    # API키 호출 환경변수 설정
    client_id = os.getenv("NAVER_ID")
    client_secret = os.getenv("NAVER_SECRET")

    if not client_id or not client_secret:
        print("NAVER_ID, NAVER_SECRET 환경변수를 설정해주세요.")
        sys.exit(1)

    encText = urllib.parse.quote(search_word)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display={display}&sort={sort}"  # JSON 결과
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)

    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if rescode == 200:
            response_body = response.read()
            # JSON으로 파싱하고 결과를 보기 좋게 출력
            json_data = json.loads(response_body.decode("utf-8"))

            print(f"\n검색어 '{search_word}'에 대한 결과:")
            print("-" * 50)

            for item in json_data.get("items", []):
                print(f"제목: {item['title'].replace('<b>', '').replace('</b>', '')}")
                print(f"링크: {item['link']}")
                print(f"작성자: {item['bloggername']}")
                print(f"작성일: {item['postdate']}")

                # 블로그 내용 크롤링 추가
                print("\n[블로그 내용]")
                content = crawl_blog_content(item["link"])
                print(content[:500] + "..." if len(content) > 500 else content)
                print("-" * 50)

        else:
            print(f"Error Code: {rescode}")
    except Exception as e:
        print(f"요청 중 오류 발생: {e}")


search_word = "정동문화사 꿀팁"
naver_blog_search(search_word)


# 검색으로 얻은 url에서 블로그 내용을 크롤링
def crawl_blog_content(blog_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        # 네이버 블로그 모바일 버전 URL로 변환
        if "blog.naver.com" in blog_url:
            blog_url = blog_url.replace("blog.naver.com", "m.blog.naver.com")

        response = requests.get(blog_url, headers=headers)
        response.raise_for_status()  # 오류 상태 코드에 대한 예외 발생

        soup = BeautifulSoup(response.text, "html.parser")

        # 모바일 버전 네이버 블로그의 본문 내용 찾기
        content = soup.select_one(".se-main-container")  # 일반 에디터
        if not content:
            content = soup.select_one(".post-view")  # 구버전 에디터
        if not content:
            content = soup.select_one("#viewTypeSelector")  # 다른 형식

        if content:
            # HTML 태그 제거 및 텍스트 정리
            text = content.get_text(separator="\n", strip=True)
            return text
        else:
            return "블로그 내용을 찾을 수 없습니다."

    except Exception as e:
        return f"크롤링 중 오류 발생: {e}"


# 테스트 실행
if __name__ == "__main__":
    search_word = "정동문화사 꿀팁"
    naver_blog_search(search_word, display=3)  # 테스트를 위해 3개만 검색
