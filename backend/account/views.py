from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import CreateUserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError


# 회원가입
class CreateUserView(APIView):
    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "회원가입이 완료되었습니다.",
                    "username": user.username,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "success": False,
                "message": "회원가입에 실패했습니다.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# 로그인
class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            if serializer.is_valid():
                user = serializer.user  # 로그인 성공 시 유저 객체 접근 가능
                return Response(
                    {
                        "success": True,
                        "message": "로그인 되었습니다.",
                        "username": user.username,
                        "access_token": serializer.validated_data["access"],
                        "refresh_token": serializer.validated_data["refresh"],
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception:
            return Response(
                {
                    "success": False,
                    "message": "로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {
                "success": False,
                "message": "로그인 요청이 올바르지 않습니다. 아이디와 비밀번호를 모두 입력해주세요.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# 로그아웃
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # 인증된 사용자만 접근 가능하도록 설정

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {
                    "success": False,
                    "message": "로그아웃에 실패했습니다. 유효한 리프레시 토큰이 필요합니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            # 유효한 토큰만 블랙리스트에 추가
            if (
                "username" not in token.payload
            ):  # 또는 SIMPLE_JWT["USER_ID_CLAIM"]으로 동적으로 체크
                raise TokenError("Invalid token")

            token.blacklist()

            return Response(
                {"success": True, "message": "로그아웃 되었습니다."},
                status=status.HTTP_200_OK,
            )
        except TokenError:
            return Response(
                {"success": False, "message": "유효하지 않은 토큰입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": f"로그아웃 중 오류가 발생했습니다: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# 회원정보
class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]  # 인증된 사용자만 접근 가능하도록 설정

    # 조회
    def get(self, request, username):
        user = get_object_or_404(
            get_user_model(), username=username
        )  # JWT 토큰으로 인증된 현재 유저 정보 가져오기

        # 자기 자신의 정보만 조회 가능하도록 제한
        if request.user.username != username:
            return Response(
                {"success": False, "message": "자신의 회원 정보만 조회할 수 있습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "success": True,
                "message": "회원 정보를 조회했습니다.",
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
                "user_address": user.user_address,
            },
            status=status.HTTP_200_OK,
        )

    # 수정
    def put(self, request, username):
        user = get_object_or_404(get_user_model(), username=username)

        # 자기 자신의 정보만 수정 가능하도록 제한
        if request.user.username != username:
            return Response(
                {"success": False, "message": "자신의 회원 정보만 수정할 수 있습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 시리얼라이저에서 허용된 필드 목록 가져오기
        serializer = CreateUserSerializer()
        allowed_fields = set(serializer.fields.keys())

        # 요청 데이터에서 허용되지 않은 필드 찾기
        extra_fields = set(request.data.keys()) - allowed_fields
        if extra_fields:
            return Response(
                {
                    "message": f"허용되지 않은 필드가 포함되어 있습니다: {', '.join(extra_fields)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 정상적인 경우만 저장 로직 실행
        serializer = CreateUserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            user = serializer.save()

            return Response(
                {
                    "success": True,
                    "message": "회원 정보가 수정되었습니다.",
                    "username": user.username,
                    "nickname": user.nickname,
                    "email": user.email,
                    "user_address": user.user_address,
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "success": False,
                    "message": "회원 정보 수정에 실패했습니다",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # 탈퇴
    def delete(self, request, username):
        user = get_object_or_404(get_user_model(), username=username)

        # 자기 자신만 탈퇴 가능하도록 제한
        if request.user.username != username:
            return Response(
                {"success": False, "message": "자신의 계정만 탈퇴할 수 있습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.delete()

        return Response(
            {"success": True, "message": "회원 탈퇴에 성공했습니다."},
            status=status.HTTP_200_OK,
        )
