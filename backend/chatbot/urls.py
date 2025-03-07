from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sessions', views.ChatSessionViewSet, basename='chat-session')

urlpatterns = [
    path('', views.chat_view, name='chat'),  # chat_view를 기본 뷰로 설정
    path('api/', include(router.urls)),
    path('api/get-csrf-token/', views.get_csrf_token, name='get-csrf-token'),
    path('api/messages/<str:session_id>/', views.get_chat_messages, name='chat_messages'),
]

