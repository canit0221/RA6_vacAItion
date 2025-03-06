from django.urls import path
from . import views

urlpatterns = [
    path('', views.serve_chat, name='chat'),  # 채팅 메인 페이지
    path('<str:room_name>/', views.room, name='room'),  # 채팅방 페이지
    path('get-csrf-token/', views.get_csrf_token, name='get-csrf-token'),
]

