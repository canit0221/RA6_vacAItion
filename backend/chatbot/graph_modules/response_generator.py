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
    try:
        print("\n=== 응답 생성 시작 ===")
        question = state["question"]
        retrieved_docs = state.get("retrieved_docs", [])
        naver_results = state.get("naver_results", [])
        is_event = state.get("is_event", False)
        
        # 검색 결과 디버깅
        print(f"=== 검색된 문서 수: {len(retrieved_docs)} ===")
        print(f"=== 네이버 검색 결과 수: {len(naver_results)} ===")
        
        # 문서 포맷팅
        context = format_documents(retrieved_docs)
        naver_context = format_naver_results(naver_results)
        
        # LLM 설정 (온도를 높여 더 다양한 응답 생성)
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        print("=== LLM 초기화 완료 ===")
        
        # 간소화된 프롬프트 템플릿
        system_message = """
        당신은 한국어로 응답하는 여행 및 맛집 추천 전문가입니다.
        사용자의 질문과 검색 결과를 바탕으로 가장 적합한 장소 또는 이벤트를 추천해주세요.
        각 추천에는 장소 이름, 주소, 특징, 그리고 추천 이유를 포함해주세요.
        모든 응답은 한국어로 작성해야 합니다.
        
        응답 형식은 다음과 같은 규칙을 따라주세요:
        1. 제목이나 중요한 부분은 "**텍스트**" 형식으로 굵게 표시합니다.
        2. 각 항목은 명확히 구분되어야 합니다.
        3. 이모티콘은 적절히 사용하여 시각적 가독성을 높입니다.
        4. 장소 목록은 번호를 붙여 명확히 구분합니다.
        """
        
        user_template = """
        질문: {question}
        
        RAG 검색 결과:
        {context}
        
        네이버 검색 결과:
        {naver_results}
        
        위 정보를 바탕으로 유용하고 상세한 답변을 한국어로 제공해주세요.
        
        중요: 반드시 RAG 검색 결과와 네이버 검색 결과를 모두 활용하여 총 6개의 추천 장소를 제공하세요.
        RAG 검색 결과에서 3개, 네이버 검색 결과에서 3개의 장소를 선택하고, 각각의 정보를 상세히 설명해주세요.
        
        다음 형식으로 응답을 작성해주세요:
        
        **✨ 안녕하세요!** 질문에 대한 답변입니다.
        
        **🔍 종합 추천 의견:**
        (전체적인 추천 장소들의 특징을 비교하며 설명)
        
        **📍 추천 장소 목록:**
        
        **1. [네이버 검색 결과 - 장소명]**
        - 위치: [정확한 주소]
        - 특징:
          • [특징 1]
          • [특징 2]
        - 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        **2. [네이버 검색 결과 - 장소명]**
        - 위치: [정확한 주소]
        - 특징:
          • [특징 1]
          • [특징 2]
        - 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        **3. [네이버 검색 결과 - 장소명]**
        - 위치: [정확한 주소]
        - 특징:
          • [특징 1]
          • [특징 2]
        - 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        **4. [RAG 검색 결과 - 장소명]**
        - 위치: [정확한 주소]
        - 특징:
          • [특징 1]
          • [특징 2]
        - 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        **5. [RAG 검색 결과 - 장소명]**
        - 위치: [정확한 주소]
        - 특징:
          • [특징 1]
          • [특징 2]
        - 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        **6. [RAG 검색 결과 - 장소명]**
        - 위치: [정확한 주소]
        - 특징:
          • [특징 1]
          • [특징 2]
        - 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 설명]
        
        **💡 추가 팁:**
        [방문 시 알아두면 좋을 정보나 꿀팁을 공유]
        
        **마크다운 형식을 사용하세요. 각 항목은 줄바꿈을 통해 구분하고, 굵은 글씨나 목록을 활용하여 가독성을 높이세요.**
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", user_template)
        ])
        
        # 응답 생성
        print("=== 응답 생성 시작 ===")
        chain = prompt | llm
        response = chain.invoke({
            "context": context,
            "naver_results": naver_context,
            "question": question
        })
        
        # 실제 응답 내용 추출
        answer = response.content if hasattr(response, 'content') else str(response)
        print(f"=== 응답 생성 완료: 길이 {len(answer)} ===")
        print(f"=== 응답 미리보기: {answer[:100]}... ===")
        
        # 응답 디버깅
        print(f"=== 생성된 최종 응답 길이: {len(answer)} ===")
        
        # 빈 응답 확인 (완전히 비어있는 경우만 체크)
        if not answer or answer.strip() == "":
            fallback_response = (
                f"죄송합니다, '{question}'에 대한 정보를 찾을 수 없습니다. "
                "다른 질문이나 다른 지역에 대해 물어봐주시겠어요?"
            )
            print(f"=== 응답이 비어있어 대체 응답 사용: {fallback_response} ===")
            return {**state, "answer": fallback_response}
        
        # 상태 업데이트 전에 응답이 문자열인지 확인
        if not isinstance(answer, str):
            answer = str(answer)
            print(f"=== 응답이 문자열이 아니어서 변환했습니다: {type(answer)} ===")
        
        # 상태 업데이트
        print("=== 응답 생성 완료, 상태 업데이트 ===")
        return {**state, "answer": answer}
        
    except Exception as e:
        error_message = f"응답 생성 중 오류 발생: {str(e)}"
        print(f"=== {error_message} ===")
        return {**state, "answer": f"죄송합니다, 요청을 처리하는 중에 오류가 발생했습니다: {str(e)}"} 