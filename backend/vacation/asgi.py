import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from chatbot.routing import websocket_urlpatterns, TokenAuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vacation.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": TokenAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)

# Daphne 설정
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
        "CONFIG": {
            "capacity": 1000,
        },
    },
}

# WebSocket 타임아웃 설정
WEBSOCKET_TIMEOUT = 300  # 5분
WEBSOCKET_CONNECT_TIMEOUT = 20  # 20초
