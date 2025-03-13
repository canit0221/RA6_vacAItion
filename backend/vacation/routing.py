from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from chatbot.routing import websocket_urlpatterns
from channels.security.websocket import AllowedHostsOriginValidator

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})

# WebSocket 타임아웃 설정
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
        "CONFIG": {
            "capacity": 1500,
        },
    },
}

# WebSocket 연결 시간 설정 (60초)
WEBSOCKET_CONNECT_TIMEOUT = 60  # 초 단위
WEBSOCKET_READ_TIMEOUT = 60     # 초 단위 