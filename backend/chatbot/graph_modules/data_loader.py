import os
from typing import List, Any, Tuple
from pathlib import Path
import pandas as pd
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

def load_data(query_type: str) -> Tuple[List[Document], Any]:
    """데이터 로드 함수
    
    쿼리 타입에 따라 이벤트 데이터 또는 일반 데이터를 로드합니다.
    
    Args:
        query_type: 쿼리 타입 ("event" 또는 "general")
        
    Returns:
        (documents, vectorstore) 튜플
    """
    # 현재 프로젝트 디렉토리 경로 얻기
    current_dir = Path(__file__).resolve().parent.parent.parent.parent  # RA6_vacAItion 디렉토리까지
    
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