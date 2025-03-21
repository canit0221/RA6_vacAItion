from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import ChatSession, ChatMessage
from .serializers import ChatSessionSerializer
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@login_required
def chat_view(request):
    # 사용자의 모든 채팅 세션을 가져옴
    chat_sessions = ChatSession.objects.filter(user=request.user).order_by(
        "-created_at"
    )
    current_session = None
    messages = []

    # 세션이 있는 경우에만 첫 번째 세션의 메시지를 가져옴
    if chat_sessions.exists():
        current_session = chat_sessions[0]
        messages = ChatMessage.objects.filter(session=current_session).order_by(
            "created_at"
        )

    return render(
        request,
        "chatbot/chat.html",
        {
            "chat_sessions": chat_sessions,
            "current_session": current_session,
            "messages": messages,
        },
    )


def get_csrf_token(request):
    response = JsonResponse({"csrfToken": get_token(request)})
    response.set_cookie(
        "csrftoken", get_token(request), samesite="Lax"
    )  # ✅ CSRF 쿠키 설정 강제
    return response


@login_required
def index(request):
    return render(request, "chatbot/index.html")


class ChatSessionViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by(
            "-updated_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


@api_view(["GET"])
@login_required
def get_chat_messages(request, session_id):
    try:
        # 세션이 존재하는지 먼저 확인
        session = ChatSession.objects.get(id=session_id, user=request.user)
        messages = ChatMessage.objects.filter(session=session).order_by("created_at")

        return Response(
            [
                {
                    "content": msg.content,
                    "is_bot": msg.is_bot,
                    "created_at": msg.created_at,
                }
                for msg in messages
            ]
        )
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
