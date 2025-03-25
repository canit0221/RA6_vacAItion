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
            model="gpt-3.5-turbo-0125",
            temperature=0.3,
        )
        
        # 간소화된 프롬프트 템플릿
        system_message = """
        당신은 한국어로 응답하는 여행 및 맛집 추천 전문가입니다.
        사용자의 질문과 검색 결과를 바탕으로 가장 적합한 장소 또는 이벤트를 추천해주세요.
        각 추천에는 장소 이름, 주소, 특징, 그리고 추천 이유를 포함해주세요.
        모든 응답은 한국어로 작성해야 합니다.
        
        <장소 정보 처리 지침>
        1. 장소 이름은 검색 결과에서 원본 그대로 정확히 추출해야 합니다.
           - 장소명을 자의적으로 변경하거나 철자를 바꾸지 마세요.
        
        2. 주소 정보가 "정보 없음"으로 표시된 경우:
           - 장소 이름을 기반으로 실제로 있을 법한 주소를 추론하세요.
           - "강남역점"이나 "서울대입구점"과 같이 지점명이 포함된 경우, 해당 지역의 주소를 포함하세요.
           - "서울특별시 강남구"와 같이 일반적인 형태로 작성하되, 반드시 실제로 존재할 법한 주소여야 합니다.
           - 특히 강남구, 서초구, 마포구 등의 장소가 많이 언급되면 그 지역의 주소를 사용하세요.
        
        3. URL 처리 방법:
           - 검색 결과에 URL이 제공된 경우에만 그대로 사용하세요.
           - URL이 "정보 없음"인 경우 블로그나 인스타그램 URL을 추측하지 말고 그대로 "정보 없음"으로 표시하세요.
        
        4. 일관성 유지:
           - 모든 추천 장소는 동일한 형식과 정보 구조를 유지해야 합니다.
           - 네이버 지도 기반 추천과 데이터베이스 기반 추천을 명확히 구분해 주세요.
           - 필요하더라도 내용을 생략하거나 형식을 변경하지 말고, 일관된 형태를 유지하세요.
        </장소 정보 처리 지침>
        
        <결과 일관성 유지 지침>
        1. 모든 추천은 반드시 다음 형식을 따라야 합니다:
           - 번호 이모티콘과 장소 이름 (굵게 표시)
           - 위치 정보 (이모티콘과 함께 표시)
           - 분류 정보 (이모티콘과 함께 표시)
           - 추천 이유 (이모티콘과 함께 표시)
           - 특징 (해당하는 경우, 이모티콘과 함께 표시)
           - 참고 URL (이모티콘과 함께 표시)
        
        2. 절대 형식을 생략하거나 변경하지 마세요.
           - 특정 정보가 없더라도 해당 항목 자체를 생략하지 말고, "정보 없음"이라고 표시하세요.
           - 데이터베이스 기반 추천에서는 항상 "특징" 항목을 포함하세요.
        
        3. 모든 항목에 적절한 이모티콘을 일관되게 사용하세요.
        </결과 일관성 유지 지침>
        
        <중요: 이미 추천된 장소 제외>
        사용자에게 이미 추천된 장소들이 있습니다. 이 장소들과 유사하거나 동일한 장소는 추천하지 마세요.
        </중요>
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
        
        # 프롬프트 선택 로직 변경: 일반 검색은 시스템 메시지 + 일반 프롬프트, 이벤트 검색은 이벤트 프롬프트만 사용
        if is_event:
            # 이벤트 검색의 경우 이벤트 프롬프트만 단독으로 사용 (시스템 메시지 없이)
            event_system_message = """
            당신은 한국어로 응답하는, 전시회와 공연 등의 이벤트 추천 전문가입니다.
            사용자의 질문과 검색 결과를 바탕으로 가장 적합한 이벤트를 추천해주세요.
            모든 응답은 한국어로 작성해야 합니다.
            
            <이벤트 정보 처리 지침>
            1. 이벤트 이름은 검색 결과에서 정확히 추출해야 합니다.
               - 이벤트명(전시회명, 공연명 등)을 명확하게 추출하세요.
               - 원본 데이터에서 "제목:", "전시:", "공연:", "행사명:" 등의 키워드가 있는 부분을 확인하세요.
            
            2. 주소 정보가 부족한 경우:
               - 이벤트 장소명을 기반으로 적절한 주소를 추론하세요.
               - "XX미술관", "XX극장" 등 장소명이 있으면 실제 위치를 포함하세요.
            
            3. URL 처리 방법:
               - 검색 결과에 URL이 제공된 경우에만 그대로 사용하세요.
               - URL이 없는 경우 "정보 없음"으로 표시하세요.
            </이벤트 정보 처리 지침>
            
            <중요: 이미 추천된 이벤트 제외>
            사용자에게 이미 추천된 이벤트들이 있습니다. 이 이벤트들과 유사하거나 동일한 이벤트는 추천하지 마세요.
            </중요>
            """
            
            # 이벤트 프롬프트 개선
            event_user_template = """
            다음은 검색 시스템에서 찾은 이벤트 정보입니다:
            {context}
            
            위 정보를 바탕으로 총 3곳의 이벤트를 추천해주세요.
            {question}을 고려하여 가장 적합한 이벤트를 추천해주세요.
            
            <중요>
            다음 이벤트들은 이미 추천된 이벤트이므로 추천에서 제외해주세요:
            {recommended_places}
            </중요>
            
            === 추천 이벤트 형식 ===
            각 이벤트는 반드시 아래 형식으로 작성하세요:
            
            1️⃣ <b>[정확한 이벤트/전시회/공연 이름]</b>
            📅 일시: [날짜 및 시간 정보]
            📍 장소: [개최 장소 및 주소]
            💫 추천 이유: [구체적인 추천 이유]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]
            
            2️⃣ <b>[정확한 이벤트/전시회/공연 이름]</b>
            📅 일시: [날짜 및 시간 정보]
            📍 장소: [개최 장소 및 주소]
            💫 추천 이유: [구체적인 추천 이유]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]
            
            3️⃣ <b>[정확한 이벤트/전시회/공연 이름]</b>
            📅 일시: [날짜 및 시간 정보]
            📍 장소: [개최 장소 및 주소]
            💫 추천 이유: [구체적인 추천 이유]
            🔍 참고: [제공된 URL - URL이 없으면 "정보 없음"]
            
            ✨ 추가 팁: [이벤트 관람 시 알아두면 좋을 정보]
            """
            
            # 이벤트 검색은 이벤트 전용 시스템 메시지와 프롬프트 사용
            prompt = ChatPromptTemplate.from_messages([
                ("system", event_system_message),
                ("user", event_user_template)
            ])
            
        else:
            # 일반 검색은 기존의 시스템 메시지와 일반 프롬프트 사용
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("user", general_user_template)
            ])
        
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
                
                # 원본 콘텐츠 저장 (디버깅용)
                original_content = content
                
                # 1. 원본 콘텐츠에서 장소명 추출 개선
                place_name = title
                if content:
                    # 장소명 추출 강화
                    place_keywords = ["이름:", "장소:", "명칭:", "상호:", "점포명:", "가게 이름:", "카페 이름:", "음식점:"]
                    for keyword in place_keywords:
                        if keyword in content:
                            start_idx = content.find(keyword) + len(keyword)
                            end_idx = content.find("\n", start_idx)
                            if end_idx < 0: 
                                end_idx = len(content)
                            extracted = content[start_idx:end_idx].strip()
                            if extracted and len(extracted) > 1:
                                place_name = extracted
                                break
                
                    # 추출 실패 시 첫 줄에서 장소명 찾기 시도
                    if place_name == title:
                        first_line = content.split('\n')[0].strip()
                        if len(first_line) < 50 and len(first_line) > 2:  # 합리적인 장소명 길이
                            place_name = first_line
                
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
                
                # 원본 콘텐츠 저장
                original_content = content
                
                # 1. 이벤트명 추출
                event_name = title
                if not event_name:
                    # 이벤트명 추출 시도
                    event_keywords = ["제목:", "전시:", "공연:", "행사명:", "이벤트명:", "프로그램명:"]
                    for keyword in event_keywords:
                        if keyword in content:
                            start_idx = content.find(keyword) + len(keyword)
                            end_idx = content.find("\n", start_idx)
                            if end_idx < 0: 
                                end_idx = len(content)
                            extracted = content[start_idx:end_idx].strip()
                            if extracted and len(extracted) > 1:
                                event_name = extracted
                                break
                    
                    # 첫 줄에서 이벤트명 찾기 시도
                    if not event_name:
                        first_line = content.split('\n')[0].strip()
                        if len(first_line) < 100 and len(first_line) > 2:
                            event_name = first_line
                
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
일시: {event_date}
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