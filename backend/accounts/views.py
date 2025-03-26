from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import CreateUserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model, update_session_auth_hash
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator

# Google 소셜 로그인 관련 import
import os
from django.shortcuts import redirect
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.google import views as google_view
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from django.http import JsonResponse
import requests
from json.decoder import JSONDecodeError

# Google 로그인 기본 설정
BASE_URL = "https://vacaition.life/"  # 실제 배포 시 도메인으로 변경 필요
GOOGLE_CALLBACK_URI = BASE_URL + "accounts/google/callback/"


def google_login(request):
    """
    Google 로그인 요청
    """
    # 프론트엔드에서 전달한 리다이렉트 URI 가져오기 (없으면 기본값 사용)
    redirect_uri = request.GET.get("redirect_uri")

    # 구글에서 사용자 정보 중 이메일 스코프 요청
    scope = "https://www.googleapis.com/auth/userinfo.email"

    # settings.py에서 GOOGLE_CLIENT_ID 가져오기
    client_id = getattr(settings, "GOOGLE_CLIENT_ID")

    # GOOGLE_CALLBACK_URI를 우선 사용하되, redirect_uri가 있으면 state 파라미터에 인코딩
    state = ""
    if redirect_uri:
        import base64

        # 안전하게 인코딩하여 state 파라미터로 전달
        state = f"&state={base64.urlsafe_b64encode(redirect_uri.encode()).decode()}"

    # 구글 로그인 페이지로 리다이렉트
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&response_type=code&redirect_uri={GOOGLE_CALLBACK_URI}&scope={scope}{state}"
    return redirect(google_auth_url)


def google_callback(request):
    """
    Google 로그인 콜백 처리
    """
    # state 파라미터 확인 (프론트엔드 리다이렉트 URI가 있는 경우)
    state = request.GET.get("state")
    custom_redirect_uri = None

    if state:
        import base64

        try:
            # 안전하게 디코딩
            custom_redirect_uri = base64.urlsafe_b64decode(state.encode()).decode()
        except:
            # 디코딩 실패 시 무시
            pass

    # 클라이언트 정보 가져오기
    client_id = getattr(settings, "GOOGLE_CLIENT_ID")
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET")

    # 구글에서 받은 코드
    code = request.GET.get("code")

    # 이 부분에서 HTTP 요청 대신 직접 처리
    try:
        # 구글 로그인 플로우 직접 처리
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
        from allauth.socialaccount.providers.oauth2.client import OAuth2Client
        from dj_rest_auth.registration.views import SocialLoginView

        # 구글에서 얻은 코드로 액세스 토큰 요청
        token_req = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_CALLBACK_URI,
            },
        )
        token_req_json = token_req.json()
        access_token = token_req_json.get("access_token")

        if not access_token:
            return JsonResponse(
                {"success": False, "message": "액세스 토큰을 얻을 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 액세스 토큰으로 이메일 정보 요청
        profile_req = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_json = profile_req.json()
        email = profile_json.get("email")

        if not email:
            return JsonResponse(
                {"success": False, "message": "이메일 정보를 가져올 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        print(f"구글 프로필: {profile_json}")  # 디버깅용

        # 기존 사용자 확인 또는 신규 사용자 생성
        User = get_user_model()
        try:
            user = User.objects.get(email=email)

            # 소셜 계정 확인
            try:
                social_user = SocialAccount.objects.get(user=user)

                # 다른 소셜 계정으로 가입된 경우
                if social_user.provider != "google":
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "다른 소셜 계정으로 가입된 이메일입니다",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            except SocialAccount.DoesNotExist:
                # 일반 계정으로 가입된 이메일인 경우
                return JsonResponse(
                    {
                        "success": False,
                        "message": "해당 이메일로 가입된 일반 계정이 있습니다",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except User.DoesNotExist:
            # 랜덤 사용자 이름 생성 (이메일 주소에서 @ 앞부분 + 랜덤 숫자)
            import uuid

            username = email.split("@")[0] + str(uuid.uuid4())[:8]
            nickname = username  # 기본 닉네임으로 사용자 이름 사용

            # 일단 임시 세션에 필요한 데이터를 저장
            if custom_redirect_uri:
                # 추가 정보 입력 페이지로 리다이렉트 (완전한 사용자 생성은 아직 하지 않음)
                # 필요한 데이터를 안전하게 인코딩하여 전달
                import base64
                import json

                temp_user_data = {
                    "username": username,
                    "email": email,
                    "google_id": profile_json.get("id"),
                    "extra_data": profile_json,
                    "given_name": profile_json.get("given_name", ""),
                    "family_name": profile_json.get("family_name", ""),
                }

                # 추가 정보를 base64로 인코딩하여 전달
                encoded_data = base64.urlsafe_b64encode(
                    json.dumps(temp_user_data).encode()
                ).decode()

                # 추가 정보 입력 페이지로 리다이렉트
                additional_info_url = f"https://ra6vacaition.vercel.app/pages/google-additional-info.html?data={encoded_data}"
                return redirect(additional_info_url)

            # 리다이렉트 URI가 없는 경우 기존 방식대로 사용자 생성
            # 새 사용자 생성
            user = User.objects.create(
                username=username,
                email=email,
                nickname=nickname,
                first_name=profile_json.get("given_name", ""),  # 이름 추가
                last_name=profile_json.get("family_name", ""),  # 성 추가
            )
            user.set_unusable_password()  # 비밀번호 없이 소셜 로그인만 가능하도록 설정
            user.save()

            # 소셜 계정 연결
            SocialAccount.objects.create(
                user=user,
                provider="google",
                uid=profile_json.get("id"),  # Google 사용자 ID
                extra_data=profile_json,
            )

        # JWT 토큰 생성
        refresh = RefreshToken.for_user(user)

        # 커스텀 리다이렉트 URI가 있는 경우 해당 URI로 리다이렉션
        if custom_redirect_uri:
            redirect_url = f"{custom_redirect_uri}?access={str(refresh.access_token)}&refresh={str(refresh)}&username={user.username}"
            return redirect(redirect_url)

        # 그렇지 않으면 JSON 응답 반환
        return JsonResponse(
            {
                "success": True,
                "message": "구글 로그인 성공",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "username": user.username,
            }
        )

    except Exception as e:
        print(f"구글 로그인 처리 오류: {str(e)}")
        return JsonResponse(
            {"success": False, "message": f"구글 로그인 처리 중 오류: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class GoogleLogin(APIView):
    """
    Google 로그인 완료 처리 뷰
    """

    def post(self, request):
        try:
            # 클라이언트에서 받은 액세스 토큰과 코드
            access_token = request.data.get("access_token")
            code = request.data.get("code")

            if not access_token or not code:
                return Response(
                    {"success": False, "message": "액세스 토큰과 코드가 필요합니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 액세스 토큰으로 이메일 정보 요청
            profile_req = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_json = profile_req.json()
            email = profile_json.get("email")

            if not email:
                return Response(
                    {"success": False, "message": "이메일 정보를 가져올 수 없습니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            print(f"구글 프로필: {profile_json}")  # 디버깅용

            # 기존 사용자 확인 또는 신규 사용자 생성
            User = get_user_model()
            try:
                user = User.objects.get(email=email)
                print(f"기존 사용자 발견: {user.username}")

                # 소셜 계정 확인
                try:
                    social_user = SocialAccount.objects.get(user=user)

                    # 다른 소셜 계정으로 가입된 경우
                    if social_user.provider != "google":
                        return Response(
                            {
                                "success": False,
                                "message": "다른 소셜 계정으로 가입된 이메일입니다",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                except SocialAccount.DoesNotExist:
                    # 일반 계정으로 가입된 이메일인 경우
                    return Response(
                        {
                            "success": False,
                            "message": "해당 이메일로 가입된 일반 계정이 있습니다",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            except User.DoesNotExist:
                # 랜덤 사용자 이름 생성 (이메일 주소에서 @ 앞부분 + 랜덤 숫자)
                import uuid
                import base64
                import json

                username = email.split("@")[0] + str(uuid.uuid4())[:8]
                nickname = username  # 기본 닉네임으로 사용자 이름 사용
                print(f"새 사용자 생성 시도: username={username}, nickname={nickname}")

                # 추가 정보 입력 페이지로 리다이렉트하기 위한 데이터 준비
                temp_user_data = {
                    "username": username,
                    "email": email,
                    "google_id": profile_json.get("id"),
                    "extra_data": profile_json,
                    "given_name": profile_json.get("given_name", ""),
                    "family_name": profile_json.get("family_name", ""),
                }

                # 추가 정보를 base64로 인코딩
                encoded_data = base64.urlsafe_b64encode(
                    json.dumps(temp_user_data).encode()
                ).decode()

                # 응답 데이터 구성: 추가 정보 입력이 필요함을 알림
                return Response(
                    {
                        "success": True,
                        "message": "추가 정보 입력이 필요합니다",
                        "need_additional_info": True,
                        "temp_data": encoded_data,
                    },
                    status=status.HTTP_200_OK,
                )

                # 기존 계정 생성 코드는 추가 정보 입력 후에 실행될 것이므로 여기서는 실행하지 않음

            # JWT 토큰 생성
            try:
                refresh = RefreshToken.for_user(user)
            except Exception as e:
                print(f"JWT 토큰 생성 오류: {str(e)}")
                return Response(
                    {"success": False, "message": f"JWT 토큰 생성 중 오류: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 응답 데이터 구성
            response_data = {
                "success": True,
                "message": "구글 로그인 성공",
                "username": user.username,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"전체 처리 오류: {str(e)}")
            return Response(
                {"success": False, "message": f"처리 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # 현재 비밀번호 확인
        if not user.check_password(current_password):
            return Response(
                {"success": False, "message": "현재 비밀번호가 일치하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 새 비밀번호 확인
        if new_password != confirm_password:
            return Response(
                {"success": False, "message": "새 비밀번호가 일치하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 기존 토큰을 블랙리스트에 추가
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # 새 비밀번호 설정
            user.set_password(new_password)
            user.save()

            # 새로운 토큰 발급
            new_refresh = RefreshToken.for_user(user)
            new_access = new_refresh.access_token

            return Response(
                {
                    "success": True,
                    "message": "비밀번호가 성공적으로 변경되었습니다.",
                    "access_token": str(new_access),
                    "refresh_token": str(new_refresh),
                },
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
                    "message": f"비밀번호 변경 중 오류가 발생했습니다: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RequestPasswordResetView(APIView):
    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email")

        try:
            user = get_user_model().objects.get(username=username, email=email)
            # 비밀번호 재설정 토큰 생성
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # 비밀번호 재설정 링크 생성
            reset_url = f"https://ra6vacaition.vercel.app/pages/reset-password.html?uid={uid}&token={token}"

            # 이메일 내용 생성
            email_subject = "[vacAItion] 비밀번호 재설정 안내"
            email_message = f"""
                안녕하세요, {user.nickname}님!
                
                비밀번호 재설정을 요청하셨습니다.
                아래 링크를 클릭하여 새로운 비밀번호를 설정해주세요:
                
                {reset_url}
                
                본인이 요청하지 않았다면 이 이메일을 무시하시면 됩니다.
                링크는 24시간 동안 유효합니다.
                
                감사합니다.
                vacAItion 팀
            """

            # 이메일 발송
            send_mail(
                subject=email_subject,
                message=email_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            return Response(
                {
                    "success": True,
                    "message": "비밀번호 재설정 링크가 이메일로 발송되었습니다.",
                },
                status=status.HTTP_200_OK,
            )

        except get_user_model().DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "입력하신 정보와 일치하는 계정을 찾을 수 없습니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": f"이메일 발송 중 오류가 발생했습니다: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResetPasswordView(APIView):
    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not all([uid, token, new_password]):
            return Response(
                {"success": False, "message": "필수 정보가 누락되었습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # uid 디코딩하여 사용자 찾기
            user_id = force_str(urlsafe_base64_decode(uid))
            user = get_user_model().objects.get(pk=user_id)

            # 토큰 유효성 검사
            if not default_token_generator.check_token(user, token):
                return Response(
                    {"success": False, "message": "유효하지 않거나 만료된 링크입니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 새 비밀번호 설정
            user.set_password(new_password)
            user.save()

            return Response(
                {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."},
                status=status.HTTP_200_OK,
            )

        except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
            return Response(
                {
                    "success": False,
                    "message": "유효하지 않은 비밀번호 재설정 링크입니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class GoogleAdditionalInfoView(APIView):
    """
    구글 로그인 후 추가 정보(닉네임, 주소)를 입력받아 사용자 생성을 완료하는 API
    """

    def post(self, request):
        # 클라이언트로부터 받은 데이터
        encoded_data = request.data.get("encoded_data")
        nickname = request.data.get("nickname")
        user_address = request.data.get("user_address", "")  # 주소는 선택사항

        if not encoded_data or not nickname:
            return Response(
                {"success": False, "message": "필수 정보가 누락되었습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 임시 데이터 디코딩
            import base64
            import json

            temp_user_data = json.loads(
                base64.urlsafe_b64decode(encoded_data.encode()).decode()
            )

            # 닉네임 중복 확인
            User = get_user_model()
            if User.objects.filter(nickname=nickname).exists():
                return Response(
                    {"success": False, "message": "이미 사용 중인 닉네임입니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 사용자 생성
            user = User.objects.create(
                username=temp_user_data.get("username"),
                email=temp_user_data.get("email"),
                nickname=nickname,
                user_address=user_address,
                first_name=temp_user_data.get("given_name", ""),
                last_name=temp_user_data.get("family_name", ""),
            )
            user.set_unusable_password()  # 비밀번호 없이 소셜 로그인만 가능하도록 설정
            user.save()

            # 소셜 계정 연결
            SocialAccount.objects.create(
                user=user,
                provider="google",
                uid=temp_user_data.get("google_id"),
                extra_data=temp_user_data.get("extra_data", {}),
            )

            # JWT 토큰 생성
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "success": True,
                    "message": "회원가입이 완료되었습니다.",
                    "username": user.username,
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": f"사용자 생성 중 오류가 발생했습니다: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
