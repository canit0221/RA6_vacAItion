from django.http import JsonResponse
from django.shortcuts import render
from django.middleware.csrf import get_token

def serve_chat(request):
    return render(request, "chatbot/chat.html")  # vanilla HTML 템플릿 렌더링

def get_csrf_token(request):
    response = JsonResponse({"csrfToken": get_token(request)})
    response.set_cookie("csrftoken", get_token(request), samesite='Lax')  # ✅ CSRF 쿠키 설정 강제
    return response

def index(request):
    # 세션 목록 데이터 (나중에 DB에서 가져오도록 수정 가능)
    sessions = [
        {'id': 3, 'title': 'Session Title 3', 'description': '긴단한 대화 내용(로컬 내용 같이 보여주기)'},
        {'id': 2, 'title': 'Session Title 2', 'description': '긴단한 대화 내용'},
        {'id': 1, 'title': 'Session Title 1', 'description': '긴단한 대화 내용'},
    ]
    return render(request, 'chatbot/index.html', {'sessions': sessions})

def room(request, room_name):
    # 세션 목록도 함께 전달
    sessions = [
        {'id': 3, 'title': 'Session Title 3', 'description': '긴단한 대화 내용(로컬 내용 같이 보여주기)'},
        {'id': 2, 'title': 'Session Title 2', 'description': '긴단한 대화 내용'},
        {'id': 1, 'title': 'Session Title 1', 'description': '긴단한 대화 내용'},
    ]
    return render(request, 'chatbot/room.html', {
        'room_name': room_name,
        'sessions': sessions
    })
