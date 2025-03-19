import os
import threading
import asyncio
from typing import Dict, List, Annotated, TypedDict, Tuple, Optional, Any, Iterator
from threading import Event
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import pandas as pd
import re
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
import langgraph
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages, MessageGraph
import random
from .graph_modules import (
    GraphState, 
    query_analyzer, 
    hybrid_retriever, 
    naver_search, 
    response_generator
)

# 싱글톤 그래프 인스턴스와 초기화 상태
_graph_instance = None
graph_ready = Event()
_initialization_in_progress = False  # 초기화가 진행 중인지 확인하는 플래그

# 환경 변수 로드
load_dotenv()

# OpenAI API 키 설정
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    os.environ["OPENAI_API_KEY"] = openai_api_key
else:
    print("Warning: OPENAI_API_KEY environment variable is not set")


def get_graph_instance():
    """그래프 인스턴스 반환 - 싱글톤 패턴"""
    global _graph_instance
    
    # 인스턴스가 없고 초기화가 진행 중이지 않으면 초기화 시작
    if _graph_instance is None and not _initialization_in_progress:
        threading.Thread(target=initialize_graph_in_background, daemon=True).start()
        
    return _graph_instance


# 토큰화 함수
def tokenize(text: str) -> List[str]:
    """텍스트를 토큰화하는 함수"""
    return re.findall(r"[\w\d가-힣]+", text.lower())


# 카테고리 및 구 이름 추출 함수
def extract_categories_and_districts(query: str) -> Tuple[Optional[str], Optional[str]]:
    """쿼리에서 카테고리와 구 이름 추출"""
    districts = [
        "서울 종로구", "서울 중구", "서울 용산구", "서울 성동구", "서울 광진구", "서울 동대문구",
        "서울 중랑구", "서울 성북구", "서울 강북구", "서울 도봉구", "서울 노원구", "서울 은평구",
        "서울 서대문구", "서울 마포구", "서울 양천구", "서울 강서구", "서울 구로구", "서울 금천구",
        "서울 영등포구", "서울 동작구", "서울 관악구", "서울 서초구", "서울 강남구", "서울 송파구", "서울 강동구"
    ]
    
    categories = {
        "카페": ["카페", "커피", "브런치", "디저트"],
        "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는"],
        "공연": ["공연", "연극", "뮤지컬", "오페라"],
        "전시": ["전시", "전시회", "갤러리", "미술관"],
        "콘서트": ["콘서트", "공연장", "라이브", "음악"]
    }
    
    # 구 이름 추출
    district = None
    for d in districts:
        if d in query:
            district = d
            break
    
    if not district:
        for d in districts:
            district_name = d.replace("서울 ", "")
            if district_name in query:
                district = d
                break
    
    # 카테고리 추출
    category = None
    query_lower = query.lower()
    for cat, keywords in categories.items():
        if any(keyword in query_lower for keyword in keywords):
            category = cat
            break
    
    return category, district


# 이벤트 검사 함수
def check_query_type(query: str) -> str:
    """쿼리 타입을 확인하는 함수"""
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


# 마이너 키워드 추출 함수
def extract_minor_keywords(query: str) -> List[str]:
    """쿼리에서 마이너 키워드 추출"""
    keyword_groups = {
        "숨은": ["숨은", "숨겨진", "알려지지 않은", "비밀", "히든", "hidden", "secret", "잘 모르는", "남들이 모르는", "나만 아는", "나만 알고 있는", "붐비지 않는", "한적한"],
        "우연": ["우연히", "우연한", "우연히 발견한", "우연히 알게 된", "우연히 찾은", "우연히 방문한", "우연히 가게 된"],
        "로컬": ["로컬", "현지인", "주민", "동네", "단골", "local", "근처", "주변"]
    }
    
    query_lower = query.lower()
    minor_types = []
    
    for minor_type, keywords in keyword_groups.items():
        if any(keyword in query_lower for keyword in keywords):
            minor_types.append(minor_type)
    
    return minor_types


# 데이터 로드 함수
def load_data(query_type: str) -> Tuple[List[Document], Any]:
    """데이터 로드 함수"""
    # 현재 프로젝트 디렉토리 경로 얻기
    current_dir = Path(__file__).resolve().parent.parent.parent  # RA6_vacAItion 디렉토리까지
    
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    
    if query_type == "event":
        # 이벤트 데이터 로드
        event_path = current_dir / "data/event_db/event_data.csv"
        event_vectorstore_path = current_dir / "data/event_db/vectorstore"
        
        if not event_path.exists():
            raise FileNotFoundError(f"이벤트 데이터베이스 파일을 찾을 수 없습니다: {event_path}")
            
        # 이벤트 데이터 로드
        event_df = pd.read_csv(event_path)
        event_df.columns = event_df.columns.str.strip()
        
        # 이벤트 문서 변환
        event_docs = []
        for idx, row in event_df.iterrows():
            try:
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
        
        # 이벤트 벡터스토어 로드 또는 생성
        try:
            event_vectorstore = FAISS.load_local(str(event_vectorstore_path), embeddings, allow_dangerous_deserialization=True)
        except Exception:
            if event_docs:
                event_vectorstore = FAISS.from_documents(event_docs, embeddings)
                event_vectorstore.save_local(str(event_vectorstore_path))
            else:
                raise ValueError("이벤트 문서가 없어 벡터스토어를 생성할 수 없습니다.")
                
        return event_docs, event_vectorstore
        
    else:
        # 일반 데이터 로드
        db_path = current_dir / "data/db/documents.csv"
        vectorstore_path = current_dir / "data/db/vectorstore"
        
        if not db_path.exists():
            raise FileNotFoundError(f"일반 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
            
        # 일반 데이터 로드
        df = pd.read_csv(db_path)
        
        # 일반 문서 변환
        docs = []
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
                            content_parts = url.split("('page_content', '")[1].rsplit("')", 1)
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
                    except Exception:
                        continue
            except Exception:
                continue
                
        # 일반 벡터스토어 로드 또는 생성
        try:
            vectorstore = FAISS.load_local(str(vectorstore_path), embeddings, allow_dangerous_deserialization=True)
        except Exception:
            if docs:
                vectorstore = FAISS.from_documents(docs, embeddings)
                vectorstore.save_local(str(vectorstore_path))
            else:
                raise ValueError("일반 문서가 없어 벡터스토어를 생성할 수 없습니다.")
                
        return docs, vectorstore


# 네이버 검색 결과 형식 변환기
def format_naver_results(places: List[Dict]) -> str:
    """네이버 검색 결과를 텍스트로 포맷팅"""
    if not places:
        return "네이버 검색 결과가 없습니다."
        
    result = "=== 네이버 검색 결과 ===\n"
    for i, place in enumerate(places, 1):
        result += f"""
{i}. {place['title']}
   📍 주소: {place['address']}
   🏷️ 분류: {place['category']}
   🔍 링크: {place.get('link', 'N/A')}
"""
    return result


# 문서 형식 변환기
def format_documents(docs: List[Document]) -> str:
    """문서 목록을 텍스트로 포맷팅"""
    if not docs:
        return "관련 문서를 찾지 못했습니다."
        
    formatted_docs = []
    for doc in docs:
        content = doc.page_content
        url = doc.metadata.get("url", "None")
        formatted_docs.append(f"{content}\nURL: {url}")
    return "\n\n".join(formatted_docs)


def initialize_graph():
    """LangGraph 초기화"""
    global _graph_instance, graph_ready
    
    print("=== LangGraph 초기화 함수 시작 ===")
    
    # 상태 그래프 생성
    workflow = StateGraph(GraphState)
    
    # 노드 추가
    workflow.add_node("query_analyzer", query_analyzer)
    workflow.add_node("hybrid_retriever", hybrid_retriever)
    workflow.add_node("naver_search", naver_search)
    workflow.add_node("response_generator", response_generator)
    
    # 엣지 연결
    workflow.set_entry_point("query_analyzer")
    workflow.add_edge("query_analyzer", "hybrid_retriever")
    workflow.add_edge("hybrid_retriever", "naver_search")
    workflow.add_edge("naver_search", "response_generator")
    workflow.add_edge("response_generator", END)
    
    # 그래프 컴파일
    graph = workflow.compile()
    
    # 싱글톤 인스턴스 설정
    _graph_instance = graph
    
    # 테스트 호출 (확인용)
    try:
        print("=== 테스트 호출 (비어 있는 질문) ===")
        test_result = _graph_instance.invoke({"question": ""})
        print(f"=== 테스트 호출 성공, 결과 키: {test_result.keys()} ===")
    except Exception as e:
        print(f"=== 테스트 호출 실패: {e} ===")
    
    # 준비 완료 알림
    graph_ready.set()
    print("=== LangGraph 초기화 완료, graph_ready 설정됨 ===")
    
    return graph


# 백그라운드에서 그래프 초기화
def initialize_graph_in_background():
    """백그라운드에서 그래프 초기화"""
    global _initialization_in_progress, _graph_instance
    
    # 이미 초기화가 완료된 경우
    if _graph_instance is not None:
        print("=== LangGraph 인스턴스가 이미 초기화되어 있습니다 ===")
        return
        
    # 이미 초기화가 진행 중인 경우
    if _initialization_in_progress:
        print("=== LangGraph 초기화가 이미 진행 중입니다 ===")
        return
    
    # 초기화 진행 중 플래그 설정
    _initialization_in_progress = True
    
    try:
        print("=== LangGraph 초기화 시작 ===")
        initialize_graph()
        print("=== LangGraph 초기화 완료 - 이제 응답 생성이 가능합니다 ===")
    except Exception as e:
        print(f"=== LangGraph 초기화 중 오류 발생: {str(e)} ===")
        # 오류 발생 시 플래그 초기화
        _initialization_in_progress = False


# 모듈 로드 시 자동 초기화 코드는 apps.py에서 관리하므로 여기서는 제거
# 초기화 로직은 ChatbotConfig.ready()에서 호출됩니다.
# if _graph_instance is None and not _initialization_in_progress:
#     print("=== 서버 시작: LangGraph 초기화 시작 ===")
#     threading.Thread(target=initialize_graph_in_background, daemon=True).start() 