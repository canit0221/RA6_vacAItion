from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, (InvalidToken, TokenError)):
        return Response(
            {"success": False, "message": "인증에 실패했습니다. 토큰을 확인해주세요."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    return response
