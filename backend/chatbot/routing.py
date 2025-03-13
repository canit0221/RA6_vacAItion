from django.urls import re_path
from . import consumers
from channels.auth import AuthMiddlewareStack
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.db import close_old_connections
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
import logging

logger = logging.getLogger(__name__)

class TokenAuthMiddleware(BaseMiddleware):
    """
    WebSocket 연결에서 JWT 토큰을 검증하는 미들웨어
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # 데이터베이스 연결 정리
        close_old_connections()
        
        # 쿼리 파라미터에서 토큰 추출
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        token = query_params.get('token', [None])[0]
        
        if token:
            try:
                # 토큰 유효성 검증
                access_token = AccessToken(token)
                # 토큰에 저장된 username 가져오기
                username = access_token.payload.get('username')
                
                logger.info(f"토큰 검사: {access_token.payload}")
                
                if username:
                    User = get_user_model()
                    user = await self.get_user(username)
                    if user:
                        scope['user'] = user
                        logger.info(f"WebSocket 연결에 인증된 사용자: {user.username}")
                    else:
                        logger.warning(f"WebSocket 연결에 사용자를 찾을 수 없음: {username}")
                        scope['user'] = AnonymousUser()
                else:
                    logger.warning("WebSocket 연결에 사용자 이름이 없음")
                    scope['user'] = AnonymousUser()
            except Exception as e:
                logger.exception(f"WebSocket 토큰 인증 중 오류: {str(e)}")
                scope['user'] = AnonymousUser()
        else:
            logger.warning("WebSocket 연결에 토큰이 없음")
            scope['user'] = AnonymousUser()
        
        return await self.inner(scope, receive, send)
    
    @database_sync_to_async
    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(username=user_id)
        except User.DoesNotExist:
            return None

# TokenAuthMiddleware로 래핑된 AuthMiddlewareStack
TokenAuthMiddlewareStack = lambda inner: TokenAuthMiddleware(AuthMiddlewareStack(inner))

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>[\w\-]+)/?', consumers.ChatConsumer.as_asgi()),
]