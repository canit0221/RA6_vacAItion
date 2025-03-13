import json
from dotenv import load_dotenv
from channels.generic.websocket import AsyncWebsocketConsumer
from openai import AsyncOpenAI
from langchain.schema import AIMessage, HumanMessage
from channels.db import database_sync_to_async
from .models import ChatSession, ChatMessage
import os
from django.contrib.auth import get_user_model
from channels.auth import AuthMiddlewareStack
import asyncio
from account.models import User
import re
from typing import List, Optional
import aiohttp
from urllib.parse import quote, parse_qs
from pathlib import Path
import random
from .RAG_minor_sep import setup_rag
from functools import lru_cache
import weakref
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.contrib.auth.models import AnonymousUser
import jwt
from django.conf import settings
from .apps import get_rag_instance, _rag_ready

# 전역 변수로 RAG 체인 관리
_active_connections = weakref.WeakSet()

# 전역 변수로 RAG 체인 초기화 상태 관리 추가
_rag_initializing = False

load_dotenv()
NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rag_chain = None
        self.stream_handler = None
        # 서울시 구 리스트 추가
        self.districts = [
            "서울 종로구", "서울 중구", "서울 용산구", "서울 성동구", "서울 광진구", 
            "서울 동대문구", "서울 중랑구", "서울 성북구", "서울 강북구", "서울 도봉구", 
            "서울 노원구", "서울 은평구", "서울 서대문구", "서울 마포구", "서울 양천구", 
            "서울 강서구", "서울 구로구", "서울 금천구", "서울 영등포구", "서울 동작구", 
            "서울 관악구", "서울 서초구", "서울 강남구", "서울 송파구", "서울 강동구"
        ]
        
        # 네이버 API 키 초기화
        self.naver_client_id = os.environ.get('NAVER_CLIENT_ID')
        self.naver_client_secret = os.environ.get('NAVER_CLIENT_SECRET')
        self.room_name = None
        self.room_group_name = None
        self.user = None
        self.openai_client = None
        self.message_history = None
        self._active = False

    @classmethod
    async def get_rag_chain(cls):
        """이미 초기화된 RAG 체인 가져오기"""
        # RAG 체인이 초기화될 때까지 대기
        while not _rag_ready.is_set():
            await asyncio.sleep(0.1)
        return get_rag_instance()

    @database_sync_to_async
    def _extract_district(self, query: str) -> Optional[str]:
        """쿼리에서 구 이름을 추출"""
        for district in self.districts:
            if district in query:
                return district

        for district in self.districts:
            district_name = district.replace("서울 ", "")
            if district_name in query:
                return district
        return None

    @database_sync_to_async
    def _extract_category(self, query: str) -> Optional[str]:
        """쿼리에서 카테고리 키워드 추출"""
        categories = {
            "카페": ["카페", "커피", "브런치", "디저트"],
            "맛집": ["맛집", "음식점", "식당", "레스토랑", "맛있는"],
            "공연": ["공연", "연극", "뮤지컬", "오페라"],
            "전시": ["전시", "전시회", "갤러리", "미술관"],
            "콘서트": ["콘서트", "공연장", "라이브", "음악"]
        }
        
        query = query.lower()
        for category, keywords in categories.items():
            if any(keyword in query for keyword in keywords):
                return category
        return None

    async def connect(self):
        try:
            if self._active:
                return
            
            # 토큰 인증 처리
            query_string = self.scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            
            # 토큰 추출 및 검증
            token = query_params.get('token', [None])[0]
            if not token:
                print("WebSocket 연결에 토큰이 없음")
                await self.close()
                return

            try:
                # Bearer 접두사 제거
                if token.startswith('Bearer '):
                    token = token[7:]
                
                # JWT 토큰 디코딩
                decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                username = decoded_token.get('username')
                
                if not username:
                    print("토큰에 username이 없음")
                    print("토큰 내용:", decoded_token)
                    await self.close()
                    return
                
                self.user = await self.get_user_from_username(username)
                if not self.user:
                    print("유효하지 않은 사용자")
                    await self.close()
                    return
                
            except jwt.InvalidTokenError as e:
                print(f"토큰 검증 실패: {e}")
                await self.close()
                return
            except Exception as e:
                print(f"인증 처리 중 오류 발생: {e}")
                await self.close()
                return

            self.room_name = self.scope['url_route']['kwargs']['room_name']
            self.room_group_name = f'chat_{self.room_name}'
            
            # Initialize basic components
            self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            self.message_history = await self.load_chat_history()
            
            # Add to room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # WebSocket 연결 수락
            await self.accept()
            self._active = True
            _active_connections.add(self)
            
        except Exception as e:
            print(f"Connection error: {e}")
            if hasattr(self, 'close'):
                await self.close(code=1011)
            raise

    async def disconnect(self, close_code):
        # Remove from room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        self._active = False
        _active_connections.discard(self)

    async def naver_search(self, query):
        try:
            if not self.naver_client_id or not self.naver_client_secret:
                return []

            headers = {
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret
            }

            district = await self._extract_district(query)
            category = await self._extract_category(query)
            
            # 검색어 구성
            search_terms = []
            if district:
                district_name = district.split()[-1]
                search_terms.append(district_name)
            if category:
                search_terms.append(category)
            
            final_query = " ".join(search_terms) if search_terms else query
            
            print(f"\n=== 네이버 검색 시작 ===")
            print(f"검색어: {final_query}")
            
            # 중복 체크를 위한 세트
            seen_places = set()
            all_places = []
            
            async with aiohttp.ClientSession() as session:
                url = "https://openapi.naver.com/v1/search/local.json"
                params = {
                    "query": final_query,
                    "display": "5",  # 5개 결과만 요청
                    "start": "1",
                    "sort": "comment"  # 리뷰순 정렬
                }
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get('items', []):
                            title = item.get('title', '').replace('<b>', '').replace('</b>', '')
                            address = item.get('address', '')
                            road_address = item.get('roadAddress', '')
                            
                            # 중복 체크를 위한 키 생성
                            place_key = f"{title}_{address}"
                            
                            # 중복되지 않은 장소만 추가
                            if place_key not in seen_places:
                                if not district or (district_name in address or district_name in road_address):
                                    seen_places.add(place_key)
                                    all_places.append({
                                        'title': title,
                                        'address': address,
                                        'roadAddress': road_address,
                                        'category': item.get('category', ''),
                                        'description': item.get('description', ''),
                                        'link': item.get('link', ''),
                                        'mapx': item.get('mapx', ''),
                                        'mapy': item.get('mapy', '')
                                    })
            
            print(f"\n=== 검색된 장소 목록 ({len(all_places)}개) ===")
            for idx, place in enumerate(all_places, 1):
                print(f"\n{idx}. {place['title']}")
                print(f"   주소: {place['roadAddress'] or place['address']}")
                print(f"   분류: {place['category']}")
            
            if not all_places:
                print("검색 결과가 없습니다.")
                return []
            
            # 검색된 장소들 중에서 무작위로 3개 선택
            selected_places = random.sample(all_places, min(3, len(all_places)))
            
            print(f"\n=== 선택된 3개 장소 ===")
            for idx, place in enumerate(selected_places, 1):
                print(f"\n{idx}. {place['title']}")
                print(f"   주소: {place['roadAddress'] or place['address']}")
                print(f"   분류: {place['category']}")
                print(f"   링크: {place['link']}")
            
            return selected_places

        except Exception as e:
            print(f"검색 중 에러 발생: {str(e)}")
            return []

    async def get_ai_response(self, question, places, rag_results):
        try:
            # 네이버 검색 결과 포맷팅
            naver_context = "=== 네이버 검색 결과 ===\n"
            if places:
                selected_places = random.sample(places[:5], min(3, len(places)))
                for i, place in enumerate(selected_places, 1):
                    naver_context += f"""
{i}. {place['title']}
   📍 주소: {place['address']}
   🏷️ 분류: {place['category']}
   🔍 링크: {place.get('link', 'N/A')}
"""

            # RAG 검색 결과 파싱 및 포맷팅
            rag_context = "\n=== RAG 검색 결과 ===\n"
            if rag_results:
                try:
                    rag_content = rag_results.content if hasattr(rag_results, 'content') else str(rag_results)
                    
                    # "추천 장소 목록" 섹션 찾기
                    if "===== 추천 장소 목록 =====" in rag_content:
                        places_section = rag_content.split("===== 추천 장소 목록 =====")[1]
                        
                        # 각 장소 정보 추출 (1️⃣, 2️⃣, 3️⃣ 이모지로 구분)
                        places = places_section.split("\n\n")
                        for place in places[:3]:  # 최대 3개 장소만
                            if any(emoji in place for emoji in ["1️⃣", "2️⃣", "3️⃣"]):
                                # 이미 포맷팅된 정보 그대로 사용
                                rag_context += f"\n{place.strip()}\n"
                    else:
                        print("RAG 결과에서 추천 장소 목록을 찾을 수 없습니다.")
                    
                except Exception as e:
                    print(f"RAG 결과 처리 중 오류: {e}")
                    rag_context += "RAG 결과 처리 중 오류가 발생했습니다.\n"

            # 프롬프트 수정
            prompt = f"""
{question}에 대한 검색 결과입니다:

{naver_context}
{rag_context}

위 정보를 바탕으로 정확히 6곳을 추천해주세요.
네이버 검색 결과에서 3곳, RAG 검색 결과에서 3곳을 선택하여 추천해주세요.

[네이버 지도 기반 추천]
1️⃣ [장소명]
📍 위치: [도로명주소]
🏷️ 분류: [카테고리]
💫 추천 이유: [간단한 이유]
🔍 참고: [URL]

[2️⃣, 3️⃣도 동일한 형식으로 추천]

[데이터베이스 기반 추천]
4️⃣ [성경만두요리전문점 등 RAG에서 제공된 장소 3곳을 이 형식으로 작성]
📍 위치: [도로명주소]
🏷️ 분류: [카테고리]
💫 추천 이유: [간단한 이유]
🔍 참고: [URL]

[5️⃣, 6️⃣도 동일한 형식으로 추천]"""

            # GPT 설정 강화
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo-16k",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 정확히 6개의 장소를 추천해야 합니다. 네이버 검색 결과 3개와 RAG 검색 결과 3개를 반드시 포함하세요. RAG 결과가 부족하더라도 창의적으로 6개의 추천을 완성하세요."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                presence_penalty=0.6,
                frequency_penalty=0.6
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI 응답 생성 중 오류 발생: {e}")
            return f"죄송합니다. 응답 생성 중 오류가 발생했습니다."

    async def receive(self, text_data):
        try:
            print(f"Received message: {text_data}")
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            
            print(f"Parsed message: {message}")
            
            # 진행 상태 메시지 전송
            await self.send(text_data=json.dumps({
                'bot_response': "메시지를 처리하고 있습니다..."
            }))

            # 메시지 저장
            session = await self.save_message_and_get_response(message, self.room_name)
            if not session:
                print("Session not found")
                await self.send(text_data=json.dumps({
                    'bot_response': "Error: Session not found"
                }))
                return

            # 사용자 메시지를 히스토리에 추가
            self.message_history.append(HumanMessage(content=message))

            # 백그라운드 태스크로 처리하여 WebSocket 연결 유지
            asyncio.create_task(self.process_message_in_background(message, session))
            
        except Exception as e:
            print(f"Error in receive method: {e}")
            if self._active:
                await self.send(text_data=json.dumps({
                    'bot_response': "죄송합니다. 메시지 처리 중 오류가 발생했습니다."
                }))

    async def process_message_in_background(self, message, session):
        """백그라운드에서 메시지 처리"""
        try:
            # 주기적으로 진행 상태 메시지 전송
            status_task = asyncio.create_task(self.send_status_updates())
            
            # RAG 체인 가져오기
            if not self.rag_chain:
                self.rag_chain = await self.get_rag_chain()
                if not self.rag_chain:
                    if self._active:
                        await self.send(text_data=json.dumps({
                            'bot_response': "시스템이 초기화 중입니다. 잠시 후 다시 시도해주세요."
                        }))
                    return

            # 네이버 검색과 RAG 검색을 병렬로 실행
            tasks = [
                self.naver_search(message),
                asyncio.to_thread(lambda: self.rag_chain[0].invoke(message))
            ]
            
            places, rag_results = await asyncio.gather(*tasks)
            
            # 상태 업데이트 중지
            status_task.cancel()
            
            # 통합된 응답 생성
            bot_response = await self.get_ai_response(message, places, rag_results)

            # 봇 응답을 히스토리에 추가하고 저장
            self.message_history.append(AIMessage(content=bot_response))
            await self.save_bot_response(session, bot_response)

            # 최종 응답 전송
            if self._active:
                await self.send(text_data=json.dumps({
                    'bot_response': bot_response
                }))

        except Exception as e:
            print(f"Error during background processing: {e}")
            if self._active:
                await self.send(text_data=json.dumps({
                    'bot_response': "죄송합니다. 처리 중 오류가 발생했습니다."
                }))

    async def send_status_updates(self):
        """주기적으로 상태 메시지 전송"""
        status_messages = [
            "데이터를 검색 중입니다...",
            "관련 장소를 찾고 있습니다...",
            "추천 장소를 선별하고 있습니다...",
            "응답을 생성하고 있습니다...",
            "조금만 더 기다려주세요..."
        ]
        
        try:
            i = 0
            while True:
                if self._active:
                    await self.send(text_data=json.dumps({
                        'bot_response': status_messages[i % len(status_messages)]
                    }))
                i += 1
                await asyncio.sleep(3)  # 3초마다 상태 메시지 업데이트
        except asyncio.CancelledError:
            pass  # 태스크가 취소되면 조용히 종료

    @database_sync_to_async
    def load_chat_history(self):
        # 현재 세션의 모든 메시지를 시간순으로 가져옴
        try:
            session = ChatSession.objects.get(id=self.room_name, user=self.user)
            messages = ChatMessage.objects.filter(session=session).order_by('created_at')
            
            # ChatGPT 메시지 형식으로 변환
            history = []
            for msg in messages:
                if msg.is_bot:
                    history.append(AIMessage(content=msg.content))
                else:
                    history.append(HumanMessage(content=msg.content))
            return history
        except ChatSession.DoesNotExist:
            return []

    @database_sync_to_async
    def save_message_and_get_response(self, message, session_id):
        try:
            session = ChatSession.objects.get(id=session_id, user=self.user)
            
            # 사용자 메시지 저장
            ChatMessage.objects.create(
                session=session,
                content=message,
                is_bot=False
            )
            return session
            
        except ChatSession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_bot_response(self, session, response):
        ChatMessage.objects.create(
            session=session,
            content=response,
            is_bot=True
        )

    @database_sync_to_async
    def get_user_from_username(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            print(f"사용자 {username}를 찾을 수 없음")
            return None
        except Exception as e:
            print(f"사용자 조회 실패: {e}")
            return None
