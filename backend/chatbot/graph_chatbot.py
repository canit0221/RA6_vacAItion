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