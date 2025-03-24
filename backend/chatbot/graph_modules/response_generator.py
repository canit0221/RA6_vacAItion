import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .base import GraphState, format_documents, format_naver_results


def response_generator(state: GraphState) -> GraphState:
    """응답 생성 노드

    검색 결과를 기반으로 사용자 질문에 대한 응답을 생성합니다.

    Args:
        state: 현재 그래프 상태

    Returns:
        업데이트된 그래프 상태
    """
    print("\n=== 응답 생성 시작 ===")

    try:
        question = state["question"]
        retrieved_docs = state.get("retrieved_docs", [])
        naver_results = state.get("naver_results", [])
        is_event = state.get("is_event", False)

        # 문서 포맷팅
        context = format_documents(retrieved_docs)
        naver_context = format_naver_results(naver_results)

        # LLM 설정 (온도를 높여 더 다양한 응답 생성)
        api_key = os.getenv("OPENAI_API_KEY")
        llm = ChatOpenAI(openai_api_key=api_key, model="o3-mini")

        # 간소화된 프롬프트 템플릿
        system_message = """
        당신은 한국어로 응답하는 여행 및 맛집 추천 전문가입니다.
        사용자의 질문과 검색 결과를 바탕으로 가장 적합한 장소 또는 이벤트를 추천해주세요.
        각 추천에는 장소 이름, 주소, 특징, 그리고 추천 이유를 포함해주세요.
        모든 응답은 한국어로 작성해야 합니다.
        
        특히 장소 이름은 검색 결과에서 원본 그대로 정확히 추출해야 합니다.
        한국어 동음이의어나 비슷한 발음의 글자로 장소 이름이 잘못 표기되지 않도록 각별히 주의하세요.
        예를 들어 '짐승고깃간'을 '짚승고깃간'으로 잘못 추출하지 않도록 합니다.
        장소명은 정확히 원본 텍스트에 등장한 표기를 그대로 사용해야 합니다.
        
        URL도 검색 결과에서 원본 그대로 정확히 추출해야 합니다.
        URL을 추출할 때는 전체 URL을 온전히 복사하여 누락된 부분이 없도록 해야 합니다.
        URL을 묶거나 줄이지 말고, 원본 형태 그대로 포함하세요.
        
        응답 형식은 다음과 같은 규칙을 따라주세요:
        1. 제목이나 중요한 부분은 "<b>텍스트</b>" 형식으로 굵게 표시합니다. 마크다운 형식인 **텍스트**는 사용하지 마세요.
        2. 각 항목은 명확히 구분되어야 합니다.
        3. 이모티콘은 적절히 사용하여 시각적 가독성을 높입니다.
        4. 장소 목록은 번호를 붙여 명확히 구분합니다.
        5. HTML 태그를 사용해서 스타일을 적용하세요. (<b></b>, <i></i>, <u></u> 등)
        6. 문단 구분이 필요한 곳에는 반드시 빈 줄(줄바꿈 두 번)을 넣어주세요.
        7. 설명이 길 경우 중간에 줄바꿈을 적절히 넣어 가독성을 높여주세요.
        """

        # 일반 검색용 프롬프트
        general_user_template = """
        다음은 두 가지 검색 시스템에서 찾은 장소 정보입니다:

            {naver_results}
            {context}

            위 정보를 바탕으로 총 6곳의 장소를 추천해주세요.
            네이버 검색과 RAG 검색 결과를 적절히 조합하여 가장 적합한 장소들을 선별해주세요.
            {question}을 분석해서 적절한 장소를 추천해주세요.

            === 중요: 장소 정보 추출 지침 ===
            1. 각 장소의 주소 정보를 반드시 추출해야 합니다. 
               - 원본 데이터에서 '위치:', '주소:', '서울', '구' 등의 키워드가 포함된 부분을 찾아 정확한 주소를 추출하세요.
               - 전체 텍스트를 분석하여 주소 패턴(구/동/로/길)이 있는 문장을 찾아내세요.
               - 주소가 없을 경우에만 '정보 없음'으로 표시하세요.
            2. '위치: 정보 없음'이 많이 나타난다면, 텍스트 내에서 장소명과 함께 언급된 위치 정보를 적극적으로 찾아내세요.
            3. 장소명은 원본 텍스트에 등장한 정확한 이름을 그대로 사용해야 합니다:
               - 검색 결과에 나타난 장소명을 철자 그대로 정확히 복사하세요. 철자나 띄어쓰기를 임의로 바꾸지 마세요.
               - 비슷한 발음의 한글 글자로 장소명을 바꾸지 마세요. (예: '짐승'을 '짚승'으로 잘못 쓰는 등)
               - 장소명이 영어나 외래어를 포함할 경우, 원본 표기를 정확히 유지하세요.
               - 장소명이 여러 번 등장할 경우, 가장 많이 등장하는 표기법이나 공식 표기법으로 보이는 것을 선택하세요.
               - 장소명이 불확실한 경우 원문 그대로 인용해 표기하세요.
            4. URL 링크는 반드시 원본 텍스트에서 정확히 추출해야 합니다:
               - URL이 'URL:' 또는 '참고:' 키워드 뒤에 나타나는 경우가 많으니 주의 깊게 찾으세요.
               - 추출한 URL은 완전한 형태여야 합니다 (http:// 또는 https:// 포함).
               - URL을 임의로 수정하거나 줄이지 마세요.
               - URL이 없을 경우에만 '정보 없음'으로 표시하세요.
               - 네이버 검색 결과의 경우 URL을 정확히 포함해야 합니다.

            ===== 추천 장소 =====

            [네이버 지도 기반 추천]

            1️⃣ <b>[장소명 - 원본 표기 그대로 정확히 표기]</b>
            📍 위치: [정확한 주소 - 최대한 도로명주소로 표기]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [간단한 이유]
            🔍 참고: [원본 URL 전체를 그대로 복사하여 표기]

            [2️⃣, 3️⃣도 동일한 형식으로 추천]

            [데이터베이스 기반 추천]

            4️⃣ <b>[장소명 - 원본 표기 그대로 정확히 표기]</b>
            📍 위치: [정확한 주소 - 최대한 도로명주소로 표기]
            🏷️ 분류: [카테고리 - 검색 결과에서 유추]
            💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
            ✨ 특징: [분위기, 인테리어, 메뉴, 특별한 점 등]
            🔍 참고: [원본 URL 전체를 그대로 복사하여 표기]

            [5️⃣, 6️⃣도 동일한 형식으로 추천]

            ✨ 추가 팁: [방문 시 알아두면 좋을 정보나 꿀팁을 공유해주세요]  
            """

        # 이벤트 검색용 프롬프트
        event_user_template = """
        질문: {question}
        
        이벤트 검색 결과:
        {context}
        
        위 정보를 바탕으로 질문자의 요구사항에 맞는 이벤트를 추천해주세요.
        각 이벤트에 대해 다음 형식으로 상세히 설명해주시기 바랍니다:
        중요: HTML 태그인 <b>텍스트</b>를 사용하여 중요 정보를 강조하세요.
        중요: 설명이 긴 경우 줄바꿈을 적절히 사용하세요.

        === 중요: 이벤트 정보 추출 지침 ===
        1. 각 이벤트의 주소 정보를 반드시 정확하게 추출해야 합니다. 
           - 원본 데이터에서 '위치:', '주소:' 등의 키워드가 포함된 부분을 찾아 정확한 주소를 추출하세요.
           - 주소가 불완전한 경우 구나 지역명만이라도 추출하세요.
        2. 이벤트 기간과 시간 정보도 정확히 추출하세요.
        3. 이벤트명과 장소명은 원본 텍스트에 등장한 정확한 이름을 그대로 사용해야 합니다:
           - 검색 결과에 나타난 이벤트명과 장소명을 철자 그대로 정확히 복사하세요. 철자나 띄어쓰기를 임의로 바꾸지 마세요.
           - 비슷한 발음의 한글 글자로 이름을 바꾸지 마세요. (예: '짐승'을 '짚승'으로 잘못 쓰는 등)
           - 이름이 영어나 외래어를 포함할 경우, 원본 표기를 정확히 유지하세요.
           - 이름이 여러 번 등장할 경우, 가장 많이 등장하는 표기법이나 공식 표기법으로 보이는 것을 선택하세요.
           - 이름이 불확실한 경우 원문 그대로 인용해 표기하세요.
        4. URL 링크는 반드시 원본 텍스트에서 정확히 추출해야 합니다:
           - URL이 'URL:' 또는 '참고:' 키워드 뒤에 나타나는 경우가 많으니 주의 깊게 찾으세요.
           - 추출한 URL은 완전한 형태여야 합니다 (http:// 또는 https:// 포함).
           - URL을 임의로 수정하거나 줄이지 마세요.
           - URL이 없을 경우에만 '정보 없음'으로 표시하세요.

        💡 <b>종합 추천 의견</b>
        [전체적인 추천 이벤트의 특징을 설명하고, 질문자의 목적에 가장 적합한 순서대로 설명해주세요.]

        [중간에 줄바꿈을 해가며 너무 글 길이가 길지 않게 해주세요. 종합 의견은 2-3개의 문단으로 작성하는 것이 좋습니다.]

        ===== <b>추천 이벤트 목록</b> =====

        1️⃣ <b>[이벤트명 - 원본 표기 그대로 정확히 표기]</b>
        📍 위치: [정확한 주소 - 도로명주소 형식이 좋습니다]
        ⏰ 기간: [진행 기간 - 시작일/종료일 형식]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 이벤트가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
        🎭 분위기: [이벤트의 분위기]
        👥 추천 관람객: [누구와 함께 가면 좋을지]
        🔍 참고: [원본 URL 전체를 그대로 복사하여 표기]
        
        [2️⃣, 3️⃣ 이벤트도 동일한 형식으로 추천]
        
        ✨ 추가 팁: [이벤트 방문 시 알아두면 좋을 정보나 꿀팁을 공유해주세요]
        
        참고: 이벤트는 최대 3개까지만 제공하세요. 검색 결과에 따라 1~3개의 이벤트만 추천해도 됩니다.
        """

        # 쿼리 타입에 따라 적절한 프롬프트 선택
        user_template = event_user_template if is_event else general_user_template

        prompt = ChatPromptTemplate.from_messages(
            [("system", system_message), ("user", user_template)]
        )

        # 응답 생성
        chain = prompt | llm

        # 메타데이터가 풍부한 문서 포맷팅
        def format_with_detailed_metadata(docs):
            """문서를 메타데이터와 함께 상세히 포맷팅"""
            formatted_docs = []

            for i, doc in enumerate(docs, 1):
                content = doc.page_content

                # 모든 메타데이터 수집
                meta = doc.metadata
                url = meta.get("url", "")
                title = meta.get("title", f"장소 {i}")
                location = meta.get("location", "")
                address = meta.get("address", "")
                address_detail = meta.get("address_detail", "")
                date = meta.get("date", "")
                tag = meta.get("tag", "")

                # URL 추출 강화
                if not url or url == "None":
                    # 본문에서 URL 찾기
                    url_patterns = ["http://", "https://", "www."]
                    url_indicators = [
                        "URL:",
                        "url:",
                        "참고:",
                        "링크:",
                        "사이트:",
                        "홈페이지:",
                    ]

                    # URL 표시자가 있는 경우
                    for indicator in url_indicators:
                        if indicator in content:
                            start_idx = content.find(indicator) + len(indicator)
                            # URL의 끝을 찾기 (공백, 줄바꿈 등으로 구분)
                            for end_char in [" ", "\n", "\t"]:
                                end_idx = content.find(end_char, start_idx)
                                if end_idx > 0:
                                    potential_url = content[start_idx:end_idx].strip()
                                    if any(
                                        pattern in potential_url
                                        for pattern in url_patterns
                                    ):
                                        url = potential_url
                                        break
                            if url:  # URL을 찾았으면 루프 종료
                                break

                    # 본문에서 직접 URL 패턴 찾기
                    if not url:
                        for pattern in url_patterns:
                            if pattern in content:
                                start_idx = content.find(pattern)
                                # URL의 끝을 찾기
                                end_idx = len(content)
                                for end_char in [" ", "\n", "\t"]:
                                    temp_end = content.find(end_char, start_idx)
                                    if temp_end > 0 and temp_end < end_idx:
                                        end_idx = temp_end
                                potential_url = content[start_idx:end_idx].strip()
                                if potential_url:
                                    url = potential_url
                                    break

                # URL 형식 확인 및 보정
                if url and not (
                    url.startswith("http://") or url.startswith("https://")
                ):
                    if url.startswith("www."):
                        url = "https://" + url
                    # 그 외의 경우는 잘못된 URL일 가능성이 있음

                # URL이 없는 경우 표시
                if not url or url == "None":
                    url = "URL 정보 없음"

                # 위치 정보 통합
                location_info = "위치 정보 없음"
                if location or address or address_detail:
                    parts = []
                    if location:
                        parts.append(location)
                    if address:
                        parts.append(address)
                    if address_detail:
                        parts.append(address_detail)
                    location_info = " ".join(parts)

                # 위치 정보가 없는 경우 본문에서 찾기
                if location_info == "위치 정보 없음" and content:
                    # 주소 패턴 찾기
                    lower_content = content.lower()
                    address_indicators = [
                        "위치:",
                        "주소:",
                        "서울",
                        "대한민국",
                        "강남구",
                        "종로구",
                        "송파구",
                        "마포구",
                    ]
                    for indicator in address_indicators:
                        if indicator.lower() in lower_content:
                            start_idx = lower_content.find(indicator.lower())
                            if start_idx >= 0:
                                # 주소 정보가 있는 문장 추출
                                end_idx = lower_content.find("\n", start_idx)
                                if end_idx < 0:
                                    end_idx = len(lower_content)
                                address_text = content[start_idx:end_idx].strip()
                                if address_text:
                                    location_info = address_text
                                    break

                # 장소명 추출 강화
                place_name = title
                if content:
                    # 장소명 표시 패턴 찾기
                    place_name_indicators = [
                        "이름:",
                        "장소:",
                        "명칭:",
                        "상호:",
                        "점포명:",
                        "가게 이름:",
                        "카페 이름:",
                        "음식점:",
                    ]
                    for indicator in place_name_indicators:
                        if indicator in content:
                            start_idx = content.find(indicator) + len(indicator)
                            end_idx = content.find("\n", start_idx)
                            if end_idx < 0:
                                end_idx = len(content)
                            extracted_name = content[start_idx:end_idx].strip()
                            if extracted_name:
                                place_name = extracted_name
                                break

                    # "~ 맛집", "~ 카페" 패턴 찾기
                    if "맛집" in content or "카페" in content:
                        lines = content.split("\n")
                        for line in lines:
                            if "맛집" in line or "카페" in line:
                                # 이름으로 추정되는 부분 추출
                                parts = line.split()
                                if len(parts) >= 2:
                                    for part in parts:
                                        if len(part) >= 2 and not any(
                                            keyword in part
                                            for keyword in [
                                                "추천",
                                                "좋은",
                                                "유명",
                                                "인기",
                                            ]
                                        ):
                                            if (
                                                place_name == title
                                            ):  # 아직 추출되지 않은 경우만
                                                place_name = part
                                                break

                # 형식화된 문서 생성
                formatted_doc = f"""
문서 {i}: {place_name}
원본 제목: {title}
내용: {content}
위치: {location_info}
{'날짜: ' + date if date else ''}
{'태그: ' + tag if tag else ''}
URL: {url}
"""
                formatted_docs.append(formatted_doc)

            return "\n\n".join(formatted_docs)

        # 향상된 문서 포맷팅 적용
        if is_event:
            enhanced_context = format_with_detailed_metadata(retrieved_docs)
            response = chain.invoke({"context": enhanced_context, "question": question})
        else:
            enhanced_context = format_with_detailed_metadata(retrieved_docs)
            response = chain.invoke(
                {
                    "context": enhanced_context,
                    "naver_results": naver_context,
                    "question": question,
                }
            )

        # 실제 응답 내용 추출
        answer = response.content if hasattr(response, "content") else str(response)

        # 빈 응답 확인 (완전히 비어있는 경우만 체크)
        if not answer or answer.strip() == "":
            fallback_response = (
                f"죄송합니다, '{question}'에 대한 정보를 찾을 수 없습니다. "
                "다른 질문이나 다른 지역에 대해 물어봐주시겠어요?"
            )
            return {**state, "answer": fallback_response}

        # 상태 업데이트 전에 응답이 문자열인지 확인
        if not isinstance(answer, str):
            answer = str(answer)

        print(f"=== 응답 생성 완료: 길이 {len(answer)} ===")
        print(f"=== 응답 미리보기: {answer[:100]}... ===")

        # 상태 업데이트
        return {**state, "answer": answer}

    except Exception as e:
        error_message = f"응답 생성 중 오류 발생: {str(e)}"
        return {
            **state,
            "answer": f"죄송합니다, 요청을 처리하는 중에 오류가 발생했습니다: {str(e)}",
        }

    finally:
        print("=== 응답 생성 완료 ===\n")
