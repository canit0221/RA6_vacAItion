import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .base import GraphState, format_documents, format_naver_results

def extract_place_name_with_model(content, meta_title=""):
    """
    LLM을 활용하여 텍스트에서 장소명을 추출하는 함수
    
    Args:
        content: 추출할 텍스트 내용
        meta_title: 메타데이터에서 얻은 제목 (대체용)
        
    Returns:
        추출한 장소명 또는 기본값
    """
    try:
        # OpenAI API 키 가져오기
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("OpenAI API 키가 설정되지 않았습니다.")
            # 기본값으로 사용하는 meta_title이 "장소 N" 형식인지 확인
            if meta_title and (meta_title.startswith("장소 ") and meta_title[3:].isdigit()):
                return "알 수 없는 장소"
            return meta_title
            
        # 콘텐츠 길이 제한 (API 요청 크기 최적화)
        text_to_analyze = content[:1500] if len(content) > 1500 else content
        
        # LLM 모델 초기화 - 가벼운 모델 사용
        llm = ChatOpenAI(
            model="o3-mini",
            api_key=api_key
        )
        
        # LLM에게 전달할 프롬프트
        prompt = f"""
        아래 텍스트는 식당, 카페, 관광지 등에 대한 설명입니다. 이 텍스트에서 정확한 장소/가게 이름만 추출해주세요.
        
        지침:
        1. 장소명은 고유한 상호명, 가게명, 식당명, 카페명, 관광지명 등을 의미합니다.
        2. "장소 1", "장소 2"와 같은 일반적인 명칭은 장소명이 아닙니다.
        3. 특수문자를 포함한 정확한 장소명을 추출해주세요 (예: 카페 C.Through, 노티드 도넛).
        4. 장소명에 지점명이 포함된 경우 함께 추출해주세요 (예: 스타벅스 강남점, 맥도날드 홍대점).
        5. 텍스트 중 하나의 주요 장소명만 추출하세요. 여러 장소가 언급된 경우, 가장 중심이 되는 장소를 선택하세요.
        
        예시:
        - "종묘떡볶이는 종로에서 유명한 맛집입니다" → "종묘떡볶이"
        - "서울 종로구 종로 123번길에 위치한 백년토종삼계탕" → "백년토종삼계탕"
        - "불당동 맛집 신사우물갈비 불당본점은 특별한 양념이 일품" → "신사우물갈비 불당본점"
        - "연남동에 위치한 카페 노멀에서 브런치 메뉴 추천" → "카페 노멀"
        - "장소 1, 장소 2처럼 일반적인 명칭" → "알 수 없음"
        
        텍스트: {text_to_analyze}
        
        장소명만 간결하게 답변해주세요. 장소명을 찾을 수 없으면 "알 수 없음"이라고 정확히 답변해주세요.
        답변에는 설명이나 부가 정보 없이 장소명만 작성해주세요.
        """
        
        # LLM 호출
        response = llm.invoke(prompt).content
        print(f"LLM이 추출한 장소명: {response}")
        
        # 응답 처리
        place_name = response.strip()
        
        # "알 수 없음" 또는 비어있는 응답이면 메타데이터 제목 사용
        if place_name == "알 수 없음" or not place_name:
            # 기본값으로 사용하는 meta_title이 "장소 N" 형식인지 확인
            if meta_title and (meta_title.startswith("장소 ") and meta_title[3:].isdigit()):
                return "알 수 없는 장소"
            return meta_title
        
        # "장소 N" 형식으로 반환된 경우 대체
        if place_name.startswith("장소 ") and place_name[3:].isdigit():
            return "알 수 없는 장소"
            
        return place_name
            
    except Exception as e:
        print(f"장소명 추출 중 오류 발생: {e}")
        # 기본값으로 사용하는 meta_title이 "장소 N" 형식인지 확인
        if meta_title and (meta_title.startswith("장소 ") and meta_title[3:].isdigit()):
            return "알 수 없는 장소"
        return meta_title

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
        session_id = state.get("session_id", "default_session")
        
        # 추천된 장소 목록 가져오기
        recommended_places = state.get("recommended_places", [])
        
        # 세션 ID가 있고 정수형인 경우만 처리
        if isinstance(session_id, int):
            # 세션에서 이미 추천된 장소 목록 가져오기
            try:
                from chatbot.models import ChatSession
                
                # ChatSession 모델에서 세션 ID로 세션 조회
                session = ChatSession.objects.get(id=session_id)
                
                # 이미 추천된 장소 목록 가져오기
                previously_recommended = session.get_recommended_places()
                
                # 중복 제거 (이미 리스트에 있는 이름은 제외)
                if previously_recommended:
                    recommended_places.extend(previously_recommended)
                    # 중복 제거
                    recommended_places = list(set(recommended_places))
                    print(f"이미 추천된 장소 목록: {previously_recommended}")
            except Exception as e:
                print(f"세션에서 추천된 장소 목록을 가져오는 중 오류 발생: {e}")
        
        # 중복 추천 방지를 위한 문자열 생성
        recommended_places_str = ", ".join(recommended_places) if recommended_places else "없음"
        
        print(f"세션 {session_id}에 대해 이미 추천된 장소: {recommended_places_str}")
        
        # 결과가 없는 경우
        if not retrieved_docs and not naver_results:
            print("검색 결과가 없습니다.")
            return {
                **state,
                "answer": "죄송합니다. 질문에 관련된 정보를 찾지 못했습니다. 다른 질문을 해주세요."
            }
        
        # OpenAI API를 사용하여 응답 생성
        llm = ChatOpenAI(
            model="o3-mini",
        )
        
        # 간소화된 프롬프트 템플릿
        system_message = """
        당신은 한국어로 응답하는 여행 및 맛집 추천 전문가입니다.
        사용자의 질문과 검색 결과를 바탕으로 가장 적합한 장소 또는 이벤트를 추천해주세요.
        각 추천에는 장소 이름, 주소, 특징, 그리고 추천 이유를 포함해주세요.
        모든 응답은 한국어로 작성해야 합니다.
        """
        
        # 일반 검색용 프롬프트
        general_user_template = """
        다음은 두 가지 검색 시스템에서 찾은 장소 정보입니다:

            {naver_results}
            {context}

            위 정보를 바탕으로 총 6곳의 장소를 추천해주세요.
            네이버 검색과 RAG 검색 결과를 적절히 조합하여 가장 적합한 장소들을 선별해주세요.
            {question}을 분석해서 적절한 장소를 추천해주세요.
            
            <중요>
            다음 장소들은 이미 추천된 장소이므로 추천에서 제외해주세요:
            {recommended_places}
            </중요>

            === 중요: 추천 결과 형식 지침 ===
            검색 결과에서 추출한 정보를 아래 형식으로 정확히 작성하세요.
            모든 항목은 아래 형식을 반드시 준수해야 합니다.

            ===== 추천 장소 =====

            [네이버 지도 기반 추천]

            1️⃣ <b>[장소명]</b>
            📍 위치: [상세 주소]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [간단한 이유]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]

            2️⃣ <b>[장소명]</b>
            📍 위치: [상세 주소]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [간단한 이유]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]

            3️⃣ <b>[장소명]</b>
            📍 위치: [상세 주소]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [간단한 이유]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]

            [데이터베이스 기반 추천]

            4️⃣ <b>[장소명]</b>
            📍 위치: [상세 주소 - 정보가 없으면 장소명을 기반으로 유추]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [구체적인 추천 이유]
            ✨ 특징: [분위기, 인테리어, 메뉴, 특별한 점 등]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]

            5️⃣ <b>[장소명]</b>
            📍 위치: [상세 주소 - 정보가 없으면 장소명을 기반으로 유추]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [구체적인 추천 이유]
            ✨ 특징: [분위기, 인테리어, 메뉴, 특별한 점 등]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]

            6️⃣ <b>[장소명]</b>
            📍 위치: [상세 주소 - 정보가 없으면 장소명을 기반으로 유추]
            🏷️ 분류: [카테고리]
            💫 추천 이유: [구체적인 추천 이유]
            ✨ 특징: [분위기, 인테리어, 메뉴, 특별한 점 등]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]

            ✨ 추가 팁: [방문 시 알아두면 좋을 일반적인 정보나 팁]  
            """
        
        # 이벤트 검색용 프롬프트
        event_user_template = """
        다음은 검색 시스템에서 찾은 이벤트 정보입니다:
            {context}

            위 정보를 바탕으로 총 3곳의 이벤트를 추천해주세요.
            {question}을 고려하여 가장 적합한 이벤트를 추천해주세요.
            
            <중요>
            다음 이벤트들은 이미 추천된 이벤트이므로 추천에서 제외해주세요:
            {recommended_places}
            </중요>

            === 매우 중요: URL 사용 지침 ===
            1. 제공된 URL만 사용하세요. URL이 없다면 '정보 없음'으로 표시하세요.
            2. 절대로 URL을 직접 생성하거나 추측하지 마세요.
            3. 소셜 미디어나 웹사이트 URL을 임의로 만들지 마세요.

            === 추천 이벤트 ===

            1️⃣ <b>[이벤트 이름]</b>
            📅 일시: [날짜 및 시간]
            📍 장소: [위치]
            💫 추천 이유: [간단한 이유]

            [2️⃣, 3️⃣도 동일한 형식으로 추천]

            ✨ 추가 팁: [방문 시 알아두면 좋을 정보나 꿀팁을 공유해주세요]  
            """
        
        # 쿼리 타입에 따라 적절한 프롬프트 선택
        user_template = event_user_template if is_event else general_user_template
        
        # 프롬프트 템플릿 생성
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", user_template)
        ])
        
        # 응답 생성
        chain = prompt | llm
        
        # 메타데이터가 풍부한 문서 포맷팅
        def format_with_detailed_metadata(docs):
            """문서를 메타데이터와 함께 상세히 포맷팅"""
            # 상위 5개의 문서만 사용 (컨텍스트 길이 제한 문제 해결)
            docs = docs[:5] if len(docs) > 5 else docs
            
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
                
                # 원본 콘텐츠 저장 (디버깅용)
                original_content = content
                
                # LLM으로 장소명 추출
                place_name = extract_place_name_with_model(content, title)
                print(f"[장소 {i}] 추출된 장소명: '{place_name}' (원본 제목: '{title}')")
                
                # 2. URL 추출 전략 개선
                blog_url = ""
                if "line_number" in meta:
                    try:
                        from chatbot.models import NaverBlog
                        line_number = meta.get("line_number")
                        blog_entry = NaverBlog.objects.get(line_number=line_number)
                        if blog_entry.url:
                            # 블로그 URL에서 불필요한 문자 제거
                            blog_url = blog_entry.url.split('\t')[0] if '\t' in blog_entry.url else blog_entry.url
                            print(f"NaverBlog에서 URL 추출: {blog_url}")
                    except Exception as e:
                        print(f"NaverBlog URL 추출 중 오류: {e}")
                
                # URL이 없거나 메타데이터에서 추출 실패한 경우 콘텐츠에서 찾기
                if not blog_url:
                    url_patterns = ["http://", "https://", "www."]
                    url_indicators = ["URL:", "url:", "참고:", "링크:", "사이트:", "홈페이지:"]
                    
                    # URL 표시자 검색
                    for indicator in url_indicators:
                        if indicator in content:
                            start_idx = content.find(indicator) + len(indicator)
                            for end_char in [" ", "\n", "\t"]:
                                end_idx = content.find(end_char, start_idx)
                                if end_idx > 0:
                                    potential_url = content[start_idx:end_idx].strip()
                                    if any(pattern in potential_url for pattern in url_patterns):
                                        blog_url = potential_url
                                        break
                            if blog_url:
                                break
                    
                    # 전체 콘텐츠에서 URL 패턴 검색
                    if not blog_url:
                        import re
                        url_regex = r'https?://[^\s\t\n]+'
                        url_matches = re.findall(url_regex, content)
                        if url_matches:
                            blog_url = url_matches[0]
                
                # URL 형식 확인 및 보정
                if blog_url and not (blog_url.startswith("http://") or blog_url.startswith("https://")):
                    if blog_url.startswith("www."):
                        blog_url = "https://" + blog_url
                
                # 최종 URL 결정
                final_url = blog_url if blog_url else url
                if not final_url or final_url == "None" or len(final_url) < 10:
                    final_url = "정보 없음"
                
                # 3. 주소 정보 추출 개선
                location_info = ""
                if location:
                    location_info += location + " "
                if address:
                    location_info += address + " "
                if address_detail:
                    location_info += address_detail
                
                location_info = location_info.strip()
                
                # 위치 정보가 없는 경우 콘텐츠에서 더 적극적으로 찾기
                if not location_info:
                    import re
                    
                    # 주소 패턴 정의 (더 다양한 패턴 추가)
                    address_patterns = [
                        r'위치\s*:\s*([^\n]+)',
                        r'주소\s*:\s*([^\n]+)',
                        r'장소\s*:\s*([^\n]+)',
                        r'서울[가-힣]*구[가-힣]*동[가-힣0-9]*',
                        r'서울[가-힣]*구[가-힣]*로[가-힣0-9]*',
                        r'서울[가-힣]*구[가-힣]*길[가-힣0-9]*',
                        r'서울[가-힣]*구\s[가-힣]*동\s?[0-9-]+',
                        r'서울[가-힣]*구\s[가-힣]*로\s?[0-9-]+',
                        r'서울특별시[가-힣]*구[가-힣]*동[가-힣0-9]*',
                        r'서울특별시[가-힣]*구[가-힣]*로[가-힣0-9]*',
                        r'서울특별시[가-힣]*구[가-힣]*길[가-힣0-9]*',
                    ]
                    
                    # 패턴 매칭 시도
                    for pattern in address_patterns:
                        matches = re.search(pattern, content)
                        if matches:
                            if '위치' in pattern or '주소' in pattern or '장소' in pattern:
                                location_info = matches.group(1).strip()
                            else:
                                location_info = matches.group(0).strip()
                            break
                    
                    # 여전히 위치 정보가 없는 경우, 키워드 기반 검색
                    if not location_info:
                        address_keywords = ["강남구", "서초구", "종로구", "마포구", "송파구", "서울시", "서울특별시"]
                        for keyword in address_keywords:
                            if keyword in content:
                                start_idx = content.find(keyword)
                                # 뒤로 40자 정도 포함해서 추출 (주소 전체 포함 가능성 높임)
                                end_idx = min(start_idx + 40, len(content))
                                raw_address = content[start_idx:end_idx].strip()
                                # 줄바꿈 있으면 거기까지만
                                if '\n' in raw_address:
                                    raw_address = raw_address.split('\n')[0].strip()
                                location_info = raw_address
                                break
                
                # 4. 카테고리 추출 개선
                category_info = ""
                category_keywords = {
                    "카페": ["카페", "디저트", "커피", "베이커리", "브런치"],
                    "음식점": ["맛집", "식당", "레스토랑", "음식점"],
                    "한식": ["한식", "국밥", "찌개", "한정식", "고기", "삼겹살", "갈비"],
                    "일식": ["일식", "스시", "초밥", "라멘", "우동"],
                    "중식": ["중식", "중국집", "짜장면", "딤섬"],
                    "양식": ["양식", "파스타", "피자", "스테이크"],
                    "베이커리": ["베이커리", "빵집", "제과점"]
                }
                
                for cat, keywords in category_keywords.items():
                    if any(keyword in content.lower() for keyword in keywords):
                        if category_info:
                            category_info += ">" + cat
                        else:
                            category_info = cat
                
                # 형식화된 문서 생성 (필요한 모든 정보 포함)
                formatted_doc = f"""
문서 {i}:
장소명: {place_name}
위치: {location_info if location_info else "정보 없음"}
분류: {category_info if category_info else "정보 없음"}
설명: {content[:250]}{'...' if len(content) > 250 else ''}
URL: {final_url}
원본주소: {original_content[:100] if '서울' in original_content[:100] else ''}
"""
                formatted_docs.append(formatted_doc)
            
            # 모든 문서 정보 합치기
            if formatted_docs:
                return "\n".join(formatted_docs)
            else:
                return "관련 문서를 찾지 못했습니다."
        
        # 이벤트 데이터 처리를 위한 특별 포맷팅 함수
        def format_event_data(docs):
            """이벤트 문서를 메타데이터와 함께 상세히 포맷팅"""
            # 상위 5개의 문서만 사용 (컨텍스트 길이 제한 문제 해결)
            docs = docs[:5] if len(docs) > 5 else docs
            
            formatted_docs = []
            
            for i, doc in enumerate(docs, 1):
                content = doc.page_content
                
                # 모든 메타데이터 수집
                meta = doc.metadata
                url = meta.get("url", "")
                title = meta.get("title", "")
                location = meta.get("location", "")
                address = meta.get("address", "")
                
                # 이벤트 중요 정보: 날짜와 시간
                date = meta.get("date", "")
                time_info = meta.get("time", "")  # time 필드에서 날짜/시간 정보 추출
                
                # 이벤트명은 메타데이터 타이틀 사용
                event_name = title
                print(f"[이벤트 {i}] 이벤트명: '{event_name}'")
                
                # 2. 일시 정보 처리
                event_date = ""
                if time_info:  # time 필드 우선 사용
                    event_date = time_info
                elif date:     # date 필드 차선책
                    event_date = date
                else:
                    # 콘텐츠에서 날짜 패턴 찾기
                    date_patterns = [
                        r'일시\s*:\s*([^\n]+)',
                        r'기간\s*:\s*([^\n]+)',
                        r'날짜\s*:\s*([^\n]+)',
                        r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*~\s*\d{4}년\s*\d{1,2}월\s*\d{1,2}일)',
                        r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)',
                        r'(\d{4}\.\d{1,2}\.\d{1,2}\s*~\s*\d{4}\.\d{1,2}\.\d{1,2})',
                        r'(\d{4}\.\d{1,2}\.\d{1,2})'
                    ]
                    import re
                    for pattern in date_patterns:
                        match = re.search(pattern, content)
                        if match:
                            if '일시' in pattern or '기간' in pattern or '날짜' in pattern:
                                event_date = match.group(1).strip()
                            else:
                                event_date = match.group(0).strip()
                            break
                
                # 3. 장소 정보 처리
                venue_info = ""
                if location:
                    venue_info += location + " "
                if address:
                    venue_info += address
                
                venue_info = venue_info.strip()
                
                # 장소 정보가 없으면 콘텐츠에서 찾기
                if not venue_info:
                    venue_patterns = [
                        r'장소\s*:\s*([^\n]+)',
                        r'위치\s*:\s*([^\n]+)',
                        r'주소\s*:\s*([^\n]+)',
                        r'스페이스\s*([^\n]+)',
                        r'미술관\s*([^\n]+)',
                        r'갤러리\s*([^\n]+)',
                        r'아트센터\s*([^\n]+)',
                        r'씨어터\s*([^\n]+)'
                    ]
                    
                    import re
                    for pattern in venue_patterns:
                        match = re.search(pattern, content)
                        if match:
                            if '장소' in pattern or '위치' in pattern or '주소' in pattern:
                                venue_info = match.group(1).strip()
                            else:
                                start_idx = match.start()
                                # 앞뒤 맥락 포함
                                start_context = max(0, start_idx - 20)
                                end_context = min(len(content), start_idx + 50)
                                context = content[start_context:end_context]
                                venue_info = context.strip()
                            break
                
                # 4. URL 처리
                final_url = url
                if not final_url or final_url == "None" or len(final_url) < 10:
                    # URL 패턴 찾기
                    import re
                    url_regex = r'https?://[^\s\t\n]+'
                    url_matches = re.findall(url_regex, content)
                    if url_matches:
                        final_url = url_matches[0]
                    else:
                        final_url = "정보 없음"
                
                # 이벤트 문서 포맷팅
                formatted_doc = f"""
문서 {i}:
이벤트명: {event_name}
일시: {event_date if event_date else "정보 없음"}
장소: {venue_info if venue_info else "정보 없음"}
설명: {content[:250]}{'...' if len(content) > 250 else ''}
URL: {final_url}
"""
                formatted_docs.append(formatted_doc)
            
            # 모든 문서 정보 합치기
            if formatted_docs:
                return "\n".join(formatted_docs)
            else:
                return "관련 이벤트를 찾지 못했습니다."
        
        # 네이버 검색 결과와 문서 포맷팅
        naver_text = format_naver_results(naver_results)
        
        # 일반 장소 또는 이벤트에 따라 다른 포맷팅 함수 사용
        if is_event:
            docs_text = format_event_data(retrieved_docs)  # 이벤트 전용 포맷팅 사용
        else:
            docs_text = format_with_detailed_metadata(retrieved_docs)  # 일반 장소 포맷팅 사용
        
        context = {
            "question": question,
            "context": docs_text,
            "naver_results": naver_text,
            "recommended_places": recommended_places_str
        }
        
        try:
            print("\n응답 생성 중...")
            result = chain.invoke(context)
            
            # AIMessage 객체에서 content 추출 (langchain 업데이트로 인한 변경 사항)
            if hasattr(result, 'content'):
                answer = result.content
            elif isinstance(result, dict) and 'content' in result:
                answer = result['content']
            elif hasattr(result, '__str__'):
                answer = str(result)
            else:
                answer = f"응답 형식 오류: {type(result)}"
            
            print(f"응답 타입: {type(result)}, 처리 후 타입: {type(answer)}")
            
            # 세션이 유효한 경우 추천된 장소를 세션에 저장
            if isinstance(session_id, int) and isinstance(answer, str):
                try:
                    # 응답에서 장소명 추출
                    from chatbot.models import ChatMessage
                    new_places = ChatMessage.extract_places_from_message(answer)
                    
                    if new_places:
                        print(f"새로 추천된 장소들: {new_places}")
                        
                        # 세션 모델에서 장소 추가
                        try:
                            from django.db import transaction
                            with transaction.atomic():
                                session = ChatSession.objects.get(id=session_id)
                                for place in new_places:
                                    session.add_recommended_place(place)
                                print(f"세션 {session_id}에 {len(new_places)}개 장소 저장 완료")
                        except Exception as e:
                            print(f"장소를 세션에 저장하는 중 오류 발생: {e}")
                except Exception as e:
                    print(f"추천 장소 추출 및 저장 중 오류: {e}")
            
            return {**state, "answer": answer}
        except Exception as e:
            error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            print(error_message)
            return {**state, "answer": error_message}
        
    except Exception as e:
        error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
        print(error_message)
        return {**state, "answer": error_message}

    finally:
        print("=== 응답 생성 완료 ===\n") 