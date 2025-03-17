from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.schema import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import pandas as pd
import time
import faiss
import numpy as np
from pathlib import Path
from rank_bm25 import BM25Okapi
import re
from typing import List, Tuple, Dict
from dotenv import load_dotenv
import os

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

class HybridRetriever:
    def __init__(self, vectorstore, docs, k: int = 3, vector_weight: float = 0.4):
        if not docs:  # 문서가 비어있는 경우
            raise ValueError("문서 리스트가 비어있습니다. 최소 1개 이상의 문서가 필요합니다.")
        
        self.vectorstore = vectorstore
        self.k = k
        self.docs = docs
        self.vector_weight = vector_weight
        self.keyword_weight = 1 - vector_weight

        # BM25를 위한 토큰화된 문서 준비
        self.tokenized_docs = [self._tokenize(doc.page_content) for doc in docs]
        self.bm25 = BM25Okapi(self.tokenized_docs)

        # 서울시 구 리스트
        self.districts = [
            "서울 종로구", "서울 중구", "서울 용산구", "서울 성동구", "서울 광진구", "서울 동대문구",
            "서울 중랑구", "서울 성북구", "서울 강북구", "서울 도봉구", "서울 노원구", "서울 은평구",
            "서울 서대문구", "서울 마포구", "서울 양천구", "서울 강서구", "서울 구로구", "서울 금천구",
            "서울 영등포구", "서울 동작구", "서울 관악구", "서울 서초구", "서울 강남구", "서울 송파구", "서울 강동구"
        ]

        # 카테고리 설정
        self.categories = {
            "카페": ["카페", "커피", "브런치", "디저트"],
            "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는"],
            "공연": ["공연", "연극", "뮤지컬", "오페라"],
            "전시": ["전시", "전시회", "갤러리", "미술관"],
            "콘서트": ["콘서트", "공연장", "라이브", "음악"]
        }

        # 마이너 키워드 그룹 설정
        self.keyword_groups = {
            "숨은": ["숨은", "숨겨진", "알려지지 않은", "비밀", "히든", "hidden", "secret", "잘 모르는", "남들이 모르는", "나만 아는", "나만 알고 있는", "붐비지 않는", "한적한"],
            "우연": ["우연히", "우연한", "우연히 발견한", "우연히 알게 된", "우연히 찾은", "우연히 방문한", "우연히 가게 된"],
            "로컬": ["로컬", "현지인", "주민", "동네", "단골", "local", "근처", "주변"]
        }

    def _tokenize(self, text: str) -> List[str]:
        """텍스트를 토큰화하는 함수"""
        return re.findall(r"[\w\d가-힣]+", text.lower())

    def _extract_district(self, query: str) -> str:
        """쿼리에서 서울시 구 이름을 추출"""
        for district in self.districts:
            if district in query:
                return district

        for district in self.districts:
            district_name = district.replace("서울 ", "")
            if district_name in query:
                return district
        return None

    def _extract_category(self, query: str) -> str:
        """쿼리에서 카테고리 키워드 추출"""
        query = query.lower()
        for category, keywords in self.categories.items():
            if any(keyword in query for keyword in keywords):
                return category
        return None

    def _check_minor_keywords_in_doc(self, doc_content: str) -> float:
        """문서 내용에서 마이너 키워드 존재 여부 확인 및 점수 계산"""
        score = 0.0
        doc_content = doc_content.lower()
        
        for keyword_type, keywords in self.keyword_groups.items():
            if any(keyword in doc_content for keyword in keywords):
                if keyword_type in ["숨은", "우연", "로컬"]:  # 세 가지 키워드 그룹 모두 높은 가중치
                    score += 0.4  # 각 그룹당 0.4의 가중치
        
        return min(score, 1.0)  # 최대 점수는 1.0

    def _calculate_keyword_scores(self, query: str, filtered_docs: List[Document]) -> List[float]:
        """BM25 기반 키워드 매칭 점수 계산"""
        tokenized_query = self._tokenize(query)
        filtered_tokenized_docs = [
            self._tokenize(doc.page_content) for doc in filtered_docs
        ]
        filtered_bm25 = BM25Okapi(filtered_tokenized_docs)

        # 기본 키워드 점수 계산
        base_scores = filtered_bm25.get_scores(tokenized_query)
        
        # 문서 내용의 마이너 키워드 점수 계산
        minor_scores = [
            self._check_minor_keywords_in_doc(doc.page_content)
            for doc in filtered_docs
        ]
        
        # 최종 점수 계산 (BM25 점수 * 0.5 + 마이너 키워드 점수 * 0.5)
        # 마이너 키워드의 중요도를 높이기 위해 비율 조정
        final_scores = [
            base_score * 0.5 + minor_score * 0.5
            for base_score, minor_score in zip(base_scores, minor_scores)
        ]

        # 점수 정규화
        max_score = max(final_scores) + 1e-6
        normalized_scores = [score / max_score for score in final_scores]

        return normalized_scores

    def _calculate_vector_scores(self, query: str, docs: List[Document]) -> List[float]:
        """벡터 유사도 점수 계산"""
        query_embedding = np.array(self.vectorstore.embedding_function.embed_query(query)).reshape(1, -1)
        D, indices = self.vectorstore.index.search(query_embedding, min(len(docs), 500))

        vector_scores = [1 - (d / (np.max(D[0]) + 1e-6)) for d in D[0]]  # 거리 기반 정규화
        return vector_scores

    def _extract_minor_type(self, query: str) -> List[str]:
        """쿼리에서 마이너 추천 타입 추출"""
        query = query.lower()
        minor_types = []
        
        for minor_type, keywords in self.keyword_groups.items():
            if any(keyword in query for keyword in keywords):
                minor_types.append(minor_type)
        
        return minor_types

    def get_relevant_documents(self, query: str) -> List[Document]:
        """최종적으로 검색된 문서들을 키워드 스코어까지 반영하여 정렬"""
        search_start = time.time()
        print("\n=== 검색 프로세스 시작 ===")
        print(f"입력 쿼리: {query}")

        # 1. 쿼리에서 구 이름과 카테고리 추출
        district = self._extract_district(query)
        category = self._extract_category(query)
        minor_types = self._extract_minor_type(query)

        if district:
            print(f"\n1. 구 이름 추출: '{district}' 발견")
            if category:
                print(f"2. 카테고리 추출: '{category}' 발견")
            if minor_types and category not in ["전시", "공연", "콘서트"]:  # 이벤트가 아닐 때만 마이너 키워드 출력
                print(f"3. 마이너 키워드 추출: {', '.join(minor_types)} 발견")
            district_name = district.replace("서울 ", "")

            # 3. 키워드 기반 필터링
            keyword_start = time.time()
            print("\n4. 키워드 기반 필터링 중...")

            # 1단계: 구 이름으로 필터링
            district_filtered_docs = []
            for doc in self.docs:
                content = doc.page_content.lower()
                location = doc.metadata.get("location", "").lower()
                if (district.lower() in content or district_name.lower() in content or
                    district.lower() in location or district_name.lower() in location):
                    district_filtered_docs.append(doc)
            
            print(f"   - 구 이름으로 필터링된 문서 수: {len(district_filtered_docs)}개")

            if len(district_filtered_docs) == 0:
                print("   - 구 관련 문서를 찾지 못했습니다. 일반 벡터 검색을 수행합니다.")
                return self.vectorstore.similarity_search(query, k=self.k)

            # 2단계: 마이너 키워드로 필터링 (이벤트가 아닐 때만)
            filtered_docs = district_filtered_docs
            if category not in ["전시", "공연", "콘서트"]:
                filtered_docs = []
                for doc in district_filtered_docs:
                    content = doc.page_content.lower()
                    has_minor_keyword = False
                    found_keywords = []
                    for keyword_type, keywords in self.keyword_groups.items():
                        if any(keyword in content for keyword in keywords):
                            has_minor_keyword = True
                            found_keywords.append(keyword_type)
                    if has_minor_keyword:
                        filtered_docs.append(doc)
                
                print(f"   - 마이너 키워드로 필터링 후 문서 수: {len(filtered_docs)}개")
                if len(filtered_docs) == 0:
                    print("   - 마이너 키워드가 포함된 문서를 찾지 못했습니다.")
                    filtered_docs = district_filtered_docs  # 마이너 키워드가 없으면 구 기반 필터링 결과 사용

            # 4. 하이브리드 점수 계산
            scoring_start = time.time()
            print("\n5. 하이브리드 점수 계산 중...")

            # 벡터 유사도 점수 계산
            vector_scores = self._calculate_vector_scores(query, filtered_docs)

            # 키워드 매칭 점수 계산
            print("   - 키워드 점수 계산 중...")
            keyword_scores = self._calculate_keyword_scores(query, filtered_docs)

            # 최종 점수 계산 (가중 평균)
            final_scores = [
                (doc, self.vector_weight * vs + self.keyword_weight * ks)
                for doc, vs, ks in zip(filtered_docs, vector_scores, keyword_scores)
            ]

            # 점수 기준 정렬
            final_scores.sort(key=lambda x: x[1], reverse=True)
            top_results = [doc for doc, _ in final_scores[: self.k]]

            # 선택된 문서들의 마이너 키워드 출력 (이벤트가 아닐 때만)
            if category not in ["전시", "공연", "콘서트"]:
                print("\n=== 선택된 문서의 마이너 키워드 ===")
                for i, doc in enumerate(top_results, 1):
                    keywords_found = []
                    doc_content = doc.page_content.lower()
                    print(f"\n문서 {i} 분석:")
                    for group, keywords in self.keyword_groups.items():
                        found_keywords = [kw for kw in keywords if kw in doc_content]
                        if found_keywords:
                            keywords_found.append(group)
                            print(f"   - {group} 키워드 발견: {', '.join(found_keywords)}")
                    if keywords_found:
                        print(f"   => 최종 발견된 키워드 유형: {', '.join(keywords_found)}")
                        # 마이너 키워드가 쿼리와 일치하는 경우 강조
                        matching_types = set(keywords_found) & set(minor_types)
                        if matching_types:
                            print(f"   ⭐ 쿼리와 일치하는 키워드: {', '.join(matching_types)}")
                    else:
                        print("   => 마이너 키워드가 발견되지 않았습니다.")

            scoring_time = time.time() - scoring_start
            total_time = time.time() - search_start

            print(f"\n=== 검색 시간 분석 ===")
            print(f"키워드 필터링 시간: {keyword_start - search_start:.2f}초")
            print(f"하이브리드 점수 계산 시간: {scoring_time:.2f}초")
            print(f"전체 검색 시간: {total_time:.2f}초")
            print(f"   - 최종 검색 결과: {len(top_results)}개 문서")

            return top_results

        print("   - 구 이름이 감지되지 않았습니다. 일반 벡터 검색을 수행합니다.")
        return self.vectorstore.similarity_search(query, k=self.k)


def check_query_type(query: str) -> str:
    """사용자 질문의 카테고리를 확인하는 함수"""
    event_keywords = {
        "전시": ["전시", "전시회", "갤러리", "미술관"],
        "공연": ["공연", "연극", "뮤지컬", "오페라"],
        "콘서트": ["콘서트", "라이브", "공연장"]
    }
    
    query_lower = query.lower()
    for category, keywords in event_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return "event"
            
    general_keywords = {
        "카페": ["카페", "커피", "브런치", "디저트"],
        "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는"]
    }
    
    for category, keywords in general_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return "general"
            
    return "general"  # 기본값은 일반 검색

def setup_rag(query: str):
    # 쿼리 타입 확인
    query_type = check_query_type(query)
    print(f"\n쿼리 타입 확인: {query_type}")

    # 현재 파일의 디렉토리 경로 얻기
    current_dir = Path(__file__).resolve().parent.parent.parent  # RA6_vacAItion-dev 디렉토리까지
    db_path = current_dir / "data/db/documents.csv"  # .pkl 파일로 수정
    event_path = current_dir / "data/event_db/event_data.csv"
    vectorstore_path = current_dir / "data/db/vectorstore"
    event_vectorstore_path = current_dir / "data/event_db/vectorstore"

    print(f"프로젝트 루트 디렉토리: {current_dir}")
    print(f"데이터베이스 경로: {db_path}")
    print(f"이벤트 데이터 경로: {event_path}")

    # 1. 데이터 로드
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")

    # 변수 초기화
    docs = []
    event_docs = []
    vectorstore = None
    event_vectorstore = None
    
    if query_type == "event":
        print("\n이벤트 데이터베이스 로드 중...")
        # 이벤트 데이터 로드
        if not event_path.exists():
            raise FileNotFoundError(f"이벤트 데이터베이스 파일을 찾을 수 없습니다: {event_path}")

        # 이벤트 데이터 로드 - 컬럼 이름의 공백 제거
        event_df = pd.read_csv(event_path)
        event_df.columns = event_df.columns.str.strip()
        print(f"이벤트 CSV 파일에서 {len(event_df)}개의 문서를 로드했습니다.")

        # 이벤트 문서 변환
        for idx, row in event_df.iterrows():
            try:
                # 이벤트 데이터의 실제 구조에 맞게 처리
                address_full = f"{row['location']} {row['address']} {row['address_detail']}"
                page_content = f"{row['title']}\n위치: {address_full}\n시간: {row['time']}\n내용: {row['content']}\n분위기: {row['atmosphere']}\n추천 동반자: {row['companions']}"
                
                doc = Document(
                    page_content=page_content,
                    metadata={
                        "title": row['title'],
                        "url": "None",
                        "date": row['time'],
                        "location": row['location'],
                        "address": row['address'],
                        "address_detail": row['address_detail'],
                        "type": "event",
                        "tag": row['tag']
                    },
                )
                event_docs.append(doc)
            except Exception as e:
                print(f"이벤트 문서 변환 중 오류 발생: {str(e)}")
                continue

        print(f"변환된 이벤트 문서 수: {len(event_docs)}")

        # 이벤트 벡터스토어 로드 또는 생성
        try:
            event_vectorstore = FAISS.load_local(
                str(event_vectorstore_path), embeddings, allow_dangerous_deserialization=True
            )
            print("이벤트 벡터스토어를 로드했습니다.")
        except Exception as e:
            print(f"이벤트 벡터스토어 로드 중 오류 발생: {str(e)}")
            if event_docs:
                print("이벤트 벡터스토어를 새로 생성합니다.")
                event_vectorstore = FAISS.from_documents(event_docs, embeddings)
                event_vectorstore.save_local(str(event_vectorstore_path))
                print("이벤트 벡터스토어를 생성하고 저장했습니다.")
            else:
                raise ValueError("이벤트 문서가 없어 벡터스토어를 생성할 수 없습니다.")
    else:
        print("\n일반 데이터베이스 로드 중...")
        # 일반 데이터 로드
        if not db_path.exists():
            raise FileNotFoundError(f"일반 데이터베이스 파일을 찾을 수 없습니다: {db_path}")

        df = pd.read_csv(db_path)
        print(f"일반 CSV 파일에서 {len(df)}개의 문서를 로드했습니다.")

        # 일반 문서 변환
        for _, row in df.iterrows():
            try:
                content = row["content"]
                if isinstance(content, str):
                    try:
                        metadata_str = content.replace("('metadata', ", "").strip(")")
                        metadata_dict = eval(metadata_str)
                        line_number = metadata_dict.get("line_number", 0)

                        url = row["url"]
                        if isinstance(url, str) and "('page_content', '" in url:
                            content_parts = url.split("('page_content', '")[1].rsplit(
                                "')", 1
                            )
                            if content_parts:
                                page_content = content_parts[0]

                                doc = Document(
                                    page_content=page_content,
                                    metadata={
                                        "title": "None",
                                        "url": url.split("\\t")[0] if "\\t" in url else url,
                                        "date": row["date"],
                                        "line_number": line_number,
                                        "type": "general"
                                    },
                                )
                                docs.append(doc)
                    except Exception as e:
                        continue
            except Exception as e:
                continue

        # 일반 벡터스토어 로드 또는 생성
        try:
            vectorstore = FAISS.load_local(
                str(vectorstore_path), embeddings, allow_dangerous_deserialization=True
            )
            print("일반 벡터스토어를 로드했습니다.")
        except Exception as e:
            print(f"일반 벡터스토어 로드 중 오류 발생: {str(e)}")
            if docs:
                print("일반 벡터스토어를 새로 생성합니다.")
                vectorstore = FAISS.from_documents(docs, embeddings)
                vectorstore.save_local(str(vectorstore_path))
                print("일반 벡터스토어를 생성하고 저장했습니다.")
            else:
                raise ValueError("일반 문서가 없어 벡터스토어를 생성할 수 없습니다.")

    # 2. Retriever 설정
    if query_type == "event":
        retriever = HybridRetriever(event_vectorstore, event_docs, k=3, vector_weight=0.6)
    else:
        retriever = HybridRetriever(vectorstore, docs, k=3, vector_weight=0.6)

    # 3. LLM 설정
    llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)

    # 4. 프롬프트 템플릿
    event_prompt = ChatPromptTemplate.from_template(
        """
    다음은 검색된 이벤트 정보입니다:
    {context}

    위 정보를 바탕으로 질문자의 요구사항에 맞는 이벤트를 추천해주세요.
    각 이벤트에 대해 다음 형식으로 상세히 설명해주시기 바랍니다:

    💡 종합 추천 의견
    [전체적인 추천 이벤트의 특징을 설명하고, 질문자의 목적에 가장 적합한 순서대로 설명해주세요.]

    ===== 추천 이벤트 목록 =====

    [발견된 각 이벤트에 대해]
    🎯 [이벤트명]
    📍 위치: [정확한 주소]
    ⏰ 기간: [진행 기간]
    🏷️ 주요 특징:
    - [특징 1]
    - [특징 2]
    - [특징 3]
    💫 추천 이유: [이 이벤트가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
    🎭 분위기: [이벤트의 분위기]
    👥 추천 관람객: [누구와 함께 가면 좋을지]

    질문: {question}
    """
    )

    general_prompt = ChatPromptTemplate.from_template(
        """
    다음은 검색된 장소들에 대한 정보입니다:
    {context}

    위 정보를 바탕으로 질문자의 요구사항에 맞는 장소 3곳을 추천해주세요.
    각 장소에 대해 다음 형식으로 상세히 설명해주시기 바랍니다:

    💡 종합 추천 의견
    [전체적인 추천 장소들의 특징을 비교하며, 질문자의 목적에 가장 적합한 순서대로 설명해주세요.]

    ===== 추천 장소 목록 =====

    1️⃣ [장소명]
    📍 위치: [정확한 주소]
    🏷️ 주요 특징:
    - [특징 1]
    - [특징 2]
    - [특징 3]
    💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
    🔍 참고 링크: [URL]

    2️⃣ [장소명]
    📍 위치: [정확한 주소]
    🏷️ 주요 특징:
    - [특징 1]
    - [특징 2]
    - [특징 3]
    💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
    🔍 참고 링크: [URL]

    3️⃣ [장소명]
    📍 위치: [정확한 주소]
    🏷️ 주요 특징:
    - [특징 1]
    - [특징 2]
    - [특징 3]
    💫 추천 이유: [이 장소가 질문자의 요구사항과 어떻게 부합하는지 구체적으로 설명]
    🔍 참고 링크: [URL]

    ✨ 추가 팁: [방문 시 알아두면 좋을 정보나 꿀팁을 공유해주세요]  

    질문: {question}
    """
    )

    # 5. Chain 구성
    def format_docs(docs):
        formatted_docs = []
        for doc in docs:
            content = doc.page_content
            url = doc.metadata.get("url", "None")
            formatted_docs.append(f"{content}\nURL: {url}")
        return "\n\n".join(formatted_docs)

    global last_retrieved_docs
    last_retrieved_docs = []

    def retrieve_and_store(query):
        global last_retrieved_docs
        docs = retriever.get_relevant_documents(query)
        last_retrieved_docs = docs
        return {"docs": docs, "is_event": query_type == "event"}

    def format_and_select_prompt(retrieved_data, question):
        docs = retrieved_data["docs"]
        is_event = retrieved_data["is_event"]
        
        formatted_docs = []
        for doc in docs:
            content = doc.page_content
            url = doc.metadata.get("url", "None")
            formatted_docs.append(f"{content}\nURL: {url}")
        context = "\n\n".join(formatted_docs)
        
        if is_event:
            return event_prompt.format(context=context, question=question)
        else:
            return general_prompt.format(context=context, question=question)

    def stream_handler(chunk):
        print(chunk.content, end="", flush=True)

    # rag_chain 수정
    retriever_chain = RunnablePassthrough() | (lambda x: {"retrieved_data": retrieve_and_store(x), "question": x})
    prompt_chain = RunnablePassthrough() | (lambda x: format_and_select_prompt(x["retrieved_data"], x["question"]))
    rag_chain = retriever_chain | prompt_chain | llm

    return rag_chain, stream_handler


def print_retrieved_docs():
    print("\n=== 검색된 관련 문서 ===")
    for i, doc in enumerate(last_retrieved_docs, 1):
        print(f"\n문서 {i}:")
        print(f"내용: {doc.page_content}")
        print(f"메타데이터: {doc.metadata}")


if __name__ == "__main__":
    # 챗봇 실행
    query = "서울 종로구 친구들과 보기 좋은 전시회 추천"
    # query = "서울 종로구 친구들과 가기 좋은 카페 추천"
    
    # RAG 챗봇 설정
    setup_start = time.time()
    rag_chain, stream_handler = setup_rag(query)  # 쿼리를 인자로 전달
    setup_time = time.time() - setup_start
    print(f"챗봇 설정 시간: {setup_time:.2f}초")

    total_start = time.time()

    # 응답 생성 (스트리밍)
    print("\n=== AI 답변 ===")
    for chunk in rag_chain.stream(query):
        stream_handler(chunk)

    # 검색 결과 출력
    print_retrieved_docs()

    # 시간 분석 출력
    total_time = time.time() - total_start
    print(f"\n=== 전체 실행 시간 분석 ===")
    print(f"총 실행 시간: {total_time:.2f}초")
    print(f"응답 생성 시간: {time.time() - total_start:.2f}초")