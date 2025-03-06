import json
from dotenv import load_dotenv
from channels.generic.websocket import AsyncWebsocketConsumer
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage

load_dotenv()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.message_history = []  # 대화 기록을 저장할 리스트

        # ChatGPT 모델 초기화
        self.chat_model = ChatOpenAI(
            model="o3-mini",
        )

        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        user_message = text_data_json['message']

        # ChatGPT로 응답 생성
        response = await self.get_chatgpt_response(user_message)

        # 바로 클라이언트에게 응답 전송
        await self.send(text_data=json.dumps({
            'message': response
        }))

    async def get_chatgpt_response(self, user_message):
        try:
            # 사용자 메시지를 히스토리에 추가
            self.message_history.append(HumanMessage(content=user_message))
            
            # 전체 대화 기록을 포함하여 응답 생성
            response = await self.chat_model.ainvoke(
                self.message_history
            )
            
            # AI 응답을 히스토리에 추가
            self.message_history.append(AIMessage(content=response.content))
            
            return response.content
        except Exception as e:
            return f"죄송합니다. 오류가 발생했습니다: {str(e)}"
