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

load_dotenv()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope["user"]

        # ChatGPT 초기화
        self.chat_model = ChatOpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            model="gpt-3.5-turbo"
        )
        
        # 이전 대화 내용 로드
        self.message_history = await self.load_chat_history()

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

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

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        session_id = self.room_name

        # 메시지 저장
        session = await self.save_message_and_get_response(message, session_id)
        if not session:
            await self.send(text_data=json.dumps({
                'bot_response': "Error: Session not found"
            }))
            return

        try:
            # 사용자 메시지를 히스토리에 추가
            self.message_history.append(HumanMessage(content=message))

            # 전체 대화 히스토리를 포함하여 AI 응답 생성
            messages_for_api = []
            for msg in self.message_history:
                if isinstance(msg, HumanMessage):
                    messages_for_api.append({"role": "user", "content": msg.content})
                else:
                    messages_for_api.append({"role": "assistant", "content": msg.content})

            response = await self.chat_model.ainvoke(messages_for_api)
            bot_response = response.content

            # 봇 응답을 히스토리에 추가
            self.message_history.append(AIMessage(content=bot_response))

            # 봇 응답 저장
            await self.save_bot_response(session, bot_response)

            # 응답 전송
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'bot_response': bot_response
                }
            )

        except Exception as e:
            print(f"Error generating AI response: {e}")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'bot_response': "죄송합니다. 응답 생성 중 오류가 발생했습니다."
                }
            )

    async def chat_message(self, event):
        bot_response = event['bot_response']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'bot_response': bot_response
        }))

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
