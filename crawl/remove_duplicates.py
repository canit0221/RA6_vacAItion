def remove_duplicate_links(input_file, output_file):
    # 입력 파일 읽기
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 각 블로그 포스트를 분리
    posts = content.split("https://")

    # 첫 번째 빈 요소 제거
    if posts[0] == "":
        posts = posts[1:]

    # 각 포스트의 URL을 추출
    seen_urls = set()
    filtered_posts = []

    for post in posts:
        # URL 추출 (첫 줄의 탭이나 공백 이전까지)
        url = "https://" + post.split("\t")[0].split(" ")[0]

        # URL이 중복되지 않은 경우만 추가
        if url not in seen_urls:
            seen_urls.add(url)
            filtered_posts.append(post)

    # 다시 하나의 문자열로 합치기
    new_content = "".join(["https://" + post for post in filtered_posts])

    # 새 파일에 저장
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(
        f"중복 제거 완료! 총 {len(filtered_posts)}개의 고유한 포스트가 {output_file}에 저장되었습니다."
    )


if __name__ == "__main__":
    input_file = "crawled_contents/seoul copy.txt"
    output_file = "crawled_contents/seoul copy_no_duplicates.txt"
    remove_duplicate_links(input_file, output_file)
