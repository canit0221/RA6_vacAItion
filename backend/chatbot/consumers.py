import json
from dotenv import load_dotenv
from channels.generic.websocket import AsyncWebsocketConsumer
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage
from channels.db import database_sync_to_async
from .models import ChatSession, ChatMessage
import os
from django.contrib.auth import get_user_model
from channels.auth import AuthMiddlewareStack
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"WebSocket 연결 시도: {self.scope['path']}")
        
        # 사용자 정보 확인
        self.user = self.scope.get('user', None)
        
        # 사용자가 로그인되어 있는지 확인
        if not self.user or not self.user.is_authenticated:
            logger.warning("인증되지 않은 사용자의 연결 시도가 거부되었습니다.")
            # 연결 거부 (1008: Policy Violation)
            await self.close(code=1008)
            return
        
        logger.info(f"인증된 사용자 연결: {self.user.username}")
        
        # room_name 설정
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        try:
            # 세션 얻기 또는 생성
            self.chat_session = await self.get_or_create_session()
            if not self.chat_session:
                logger.error("채팅 세션을 생성할 수 없습니다. 연결을 닫습니다.")
                await self.close(code=4000)
                return
            
            # 채팅모델 초기화 (API 키 확인)
            openai_api_key = os.environ.get('OPENAI_API_KEY')
            if not openai_api_key:
                logger.error("OpenAI API 키가 없습니다. 연결을 닫습니다.")
                await self.close(code=4001)
                return
            
            self.chat_model = ChatOpenAI(
                api_key=openai_api_key,
                model="gpt-3.5-turbo"
            )
            
            # 채팅 기록 로드
            self.message_history = await self.load_chat_history()
            logger.info(f"채팅 기록 로드됨: {len(self.message_history)} 메시지")
            
            # 그룹에 조인
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            logger.info(f"WebSocket 연결 성공: {self.room_name}")
        except Exception as e:
            logger.error(f"WebSocket 연결 중 오류: {str(e)}")
            await self.close(code=4002)
            return

    @database_sync_to_async
    def load_chat_history(self):
        # 현재 세션의 모든 메시지를 시간순으로 가져옴
        try:
            if not self.chat_session:
                logger.warning("채팅 세션이 없어 메시지를 로드할 수 없습니다.")
                return []
            
            messages = ChatMessage.objects.filter(session=self.chat_session).order_by('created_at')
            
            # ChatGPT 메시지 형식으로 변환
            history = []
            for msg in messages:
                if msg.is_bot:
                    history.append(AIMessage(content=msg.content))
                else:
                    history.append(HumanMessage(content=msg.content))
            return history
        except Exception as e:
            logger.error(f"메시지 로드 중 오류: {str(e)}")
            return []

    async def disconnect(self, close_code):
        # Leave room group
        logger.info(f"WebSocket 연결 종료: 코드 {close_code}")
        try:
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
                logger.info(f"그룹에서 연결 해제: {self.room_group_name}")
            else:
                logger.warning("연결 종료 시 room_group_name이 설정되지 않았습니다.")
        except Exception as e:
            logger.error(f"연결 종료 중 오류: {str(e)}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            
            # 클라이언트에서 보낸 session_id 확인 (옵션)
            session_id = text_data_json.get('session_id', self.room_name)
            if session_id != self.room_name:
                logger.warning(f"클라이언트 세션 ID({session_id})와 서버 세션 ID({self.room_name})가 일치하지 않습니다.")
            
            logger.info(f"메시지 수신: {message[:50]}... (세션: {self.room_name})")
            
            # 메시지 저장
            if await self.save_message(message):
                # 사용자 메시지를 히스토리에 추가
                self.message_history.append(HumanMessage(content=message))
                
                # API 호출 준비
                messages_for_api = []
                for msg in self.message_history:
                    if isinstance(msg, HumanMessage):
                        messages_for_api.append({"role": "user", "content": msg.content})
                    else:
                        messages_for_api.append({"role": "assistant", "content": msg.content})
                
                # 로딩 메시지 전송
                await self.send(text_data=json.dumps({
                    'bot_response': "생각 중...",
                    'is_loading': True
                }))
                
                try:
                    # AI 응답 생성
                    logger.info(f"AI 응답 생성 중... (세션: {self.room_name})")
                    response = await self.chat_model.ainvoke(messages_for_api)
                    bot_response = response.content
                    logger.info(f"AI 응답 생성 완료: {bot_response[:50]}...")
                    
                    # 봇 응답을 히스토리에 추가
                    self.message_history.append(AIMessage(content=bot_response))
                    
                    # 봇 응답 저장
                    await self.save_bot_response(bot_response)
                    
                    # 응답 전송
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'bot_response': bot_response,
                            'is_loading': False
                        }
                    )
                except Exception as e:
                    error_msg = f"AI 응답 생성 중 오류: {str(e)}"
                    logger.error(error_msg)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'bot_response': "죄송합니다. 응답 생성 중 오류가 발생했습니다.",
                            'is_loading': False
                        }
                    )
            else:
                await self.send(text_data=json.dumps({
                    'bot_response': "메시지를 저장할 수 없습니다. 채팅 세션을 확인해주세요.",
                    'is_loading': False
                }))
            
        except json.JSONDecodeError:
            logger.error(f"JSON 디코딩 오류: {text_data}")
            await self.send(text_data=json.dumps({
                'bot_response': "메시지 형식이 올바르지 않습니다.",
                'is_loading': False
            }))
        except KeyError as e:
            logger.error(f"필수 필드 누락: {str(e)}")
            await self.send(text_data=json.dumps({
                'bot_response': "필수 필드가 누락되었습니다.",
                'is_loading': False
            }))
        except Exception as e:
            logger.error(f"메시지 처리 중 예상치 못한 오류: {str(e)}")
            await self.send(text_data=json.dumps({
                'bot_response': "메시지 처리 중 오류가 발생했습니다.",
                'is_loading': False
            }))

    async def chat_message(self, event):
        # 채팅 메시지를 WebSocket으로 전송
        response_data = {
            'bot_response': event.get('bot_response', ''),
            'is_loading': event.get('is_loading', False)
        }
        
        # 이전 형식 지원
        if 'message' in event:
            response_data['message'] = event['message']
            response_data['is_bot'] = event.get('is_bot', True)
        
        logger.info(f"응답 전송: {response_data['bot_response'][:50]}...")
        await self.send(text_data=json.dumps(response_data))

    @database_sync_to_async
    def save_message(self, message):
        try:
            if not self.chat_session:
                logger.warning("채팅 세션이 없어 메시지를 저장할 수 없습니다.")
                return False
            
            # 사용자 메시지 저장
            ChatMessage.objects.create(
                session=self.chat_session,
                content=message,
                is_bot=False
            )
            logger.info("사용자 메시지 저장 성공")
            return True
            
        except Exception as e:
            logger.error(f"메시지 저장 중 오류: {str(e)}")
            return False

    @database_sync_to_async
    def save_bot_response(self, response):
        try:
            if not self.chat_session:
                logger.warning("채팅 세션이 없어 봇 응답을 저장할 수 없습니다.")
                return False
            
            ChatMessage.objects.create(
                session=self.chat_session,
                content=response,
                is_bot=True
            )
            logger.info("봇 응답 저장 성공")
            return True
        except Exception as e:
            logger.error(f"봇 응답 저장 중 오류: {str(e)}")
            return False

    @database_sync_to_async
    def get_or_create_session(self):
        try:
            # 인증된 사용자만 세션 생성 가능
            if not self.user.is_authenticated:
                logger.error("인증되지 않은 사용자는 세션을 생성할 수 없습니다.")
                return None
            
            # 사용자의 세션 생성 또는 조회
            session, created = ChatSession.objects.get_or_create(
                id=self.room_name,
                defaults={
                    'user': self.user,
                    'title': '새 채팅',
                    'session_id': self.room_name
                }
            )
            
            # 사용자 정보와 세션 소유자 일치 여부 확인
            if session.user != self.user:
                logger.warning(f"세션 접근 권한 없음: {self.user.username}은(는) 세션 {self.room_name}의 소유자가 아닙니다.")
                return None
            
            if created:
                logger.info(f"새 세션 생성: {self.room_name} (사용자: {self.user.username})")
            else:
                logger.info(f"기존 세션 찾음: {self.room_name} (사용자: {self.user.username})")
            
            return session
        except Exception as e:
            logger.error(f"세션 생성 중 오류: {str(e)}")
            return None
