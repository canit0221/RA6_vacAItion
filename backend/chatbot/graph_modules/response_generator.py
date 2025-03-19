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
        llm = ChatOpenAI(openai_api_key=api_key, model="gpt-3.5-turbo")
        
        # 간소화된 프롬프트 템플릿
        system_message = """
        당신은 한국어로 응답하는 여행 및 맛집 추천 전문가입니다.
        사용자의 질문과 검색 결과를 바탕으로 가장 적합한 장소 또는 이벤트를 추천해주세요.
        각 추천에는 장소 이름, 주소, 특징, 그리고 추천 이유를 포함해주세요.
        모든 응답은 한국어로 작성해야 합니다.
        
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
        질문: {question}
        
        RAG 검색 결과:
        {context}
        
        네이버 검색 결과:
        {naver_results}
        
        위 정보를 바탕으로 질문자의 요구사항에 맞는 장소들을 추천해주세요.
        
        중요: 반드시 RAG 검색 결과와 네이버 검색 결과를 모두 활용하여 총 6개의 추천 장소를 제공해야 합니다. 정확히 6개의 장소를 제공하는 것이 매우 중요합니다.
        중요: 마크다운 형식인 **텍스트**는 사용하지 말고, HTML 태그인 <b>텍스트</b>를 사용하세요.
        중요: 설명이 긴 경우 줄바꿈을 적절히 사용하세요. 특히 종합 의견 부분은 2-3개의 문단으로 나누어 작성하면 가독성이 좋습니다.
        
        다음 형식으로 응답을 작성해주세요:
        
        💡 <b>종합 추천 의견</b>
        [전체적인 추천 장소들의 특징을 비교하며 설명]
        
        [여기에 줄바꿈을 넣어 문단을 나누세요. 종합 의견은 2-3개의 문단으로 작성하는 것이 좋습니다.]
        
        ===== <b>추천 장소 목록</b> =====
        
        1️⃣ <b>[장소명]</b>
        📍 위치: [정확한 주소]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        2️⃣ <b>[장소명]</b>
        📍 위치: [정확한 주소]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        3️⃣ <b>[장소명]</b>
        📍 위치: [정확한 주소]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        4️⃣ <b>[장소명]</b>
        📍 위치: [정확한 주소]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        5️⃣ <b>[장소명]</b>
        📍 위치: [정확한 주소]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        6️⃣ <b>[장소명]</b>
        📍 위치: [정확한 주소]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        ✨ <b>추가 팁:</b> [방문 시 알아두면 좋을 정보나 꿀팁을 공유]
        """
        
        # 이벤트 검색용 프롬프트
        event_user_template = """
        질문: {question}
        
        이벤트 검색 결과:
        {context}
        
        위 정보를 바탕으로 질문자의 요구사항에 맞는 이벤트를 추천해주세요.
        각 이벤트에 대해 다음 형식으로 상세히 설명해주시기 바랍니다:
        중요: 마크다운 형식인 **텍스트**는 사용하지 말고, HTML 태그인 <b>텍스트</b>를 사용하세요.
        중요: 설명이 긴 경우 줄바꿈을 적절히 사용하세요. 특히 종합 의견 부분은 2-3개의 문단으로 나누어 작성하면 가독성이 좋습니다.

        💡 <b>종합 추천 의견</b>
        [전체적인 추천 이벤트의 특징을 설명하고, 질문자의 목적에 가장 적합한 순서대로 설명해주세요.]

        [중간에 줄바꿈을 해가며 너무 글 길이가 길지 않게 해주세요. 종합 의견은 2-3개의 문단으로 작성하는 것이 좋습니다.]

        ===== <b>추천 이벤트 목록</b> =====

        1️⃣ <b>[이벤트명]</b>
        📍 위치: [정확한 주소]
        ⏰ 기간: [진행 기간]
        🏷️ 주요 특징:
        - [특징 1]
        - [특징 2]
        - [특징 3]
        💫 추천 이유: [이 이벤트가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
        🎭 분위기: [이벤트의 분위기]
        👥 추천 관람객: [누구와 함께 가면 좋을지]
        
        참고: 이벤트는 최대 3개까지만 제공하세요. 검색 결과에 따라 1~3개의 이벤트만 추천해도 됩니다.
        """
        
        # 쿼리 타입에 따라 적절한 프롬프트 선택
        user_template = event_user_template if is_event else general_user_template
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", user_template)
        ])
        
        # 응답 생성
        chain = prompt | llm
        
        # 이벤트일 경우 네이버 결과는 무시하고 컨텍스트만 사용
        if is_event:
            response = chain.invoke({
                "context": context,
                "question": question
            })
        else:
            response = chain.invoke({
                "context": context,
                "naver_results": naver_context,
                "question": question
            })
        
        # 실제 응답 내용 추출
        answer = response.content if hasattr(response, 'content') else str(response)
        
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
        return {**state, "answer": f"죄송합니다, 요청을 처리하는 중에 오류가 발생했습니다: {str(e)}"}

    finally:
        print("=== 응답 생성 완료 ===\n") 