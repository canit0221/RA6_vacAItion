from rest_framework import serializers
from .models import User

from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueValidator
from django.utils.translation import gettext as _
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class UniqueValidatorWithCustomMessage(UniqueValidator):
    def __init__(self, queryset, message=None):
        if message is None:
            message = _("이미 사용 중인 값입니다.")  # 기본 메시지를 한국어로
        super().__init__(queryset=queryset, message=message)


class CreateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["nickname", "email", "username", "password", "user_address"]
        extra_kwargs = {
            "password": {
                "write_only": True,
                "required": True,
                "error_messages": {
                    "blank": "비밀번호를 입력해 주세요.",
                    "required": "비밀번호는 필수 항목입니다.",
                },
            },
            "email": {
                "error_messages": {
                    "invalid": "올바른 이메일 주소를 입력해 주세요.",
                    "blank": "이메일을 입력해 주세요.",
                    "required": "이메일은 필수 항목입니다.",
                },
                "validators": [
                    UniqueValidatorWithCustomMessage(
                        queryset=User.objects.all(),
                        message="이미 사용 중인 이메일입니다.",
                    )
                ],
            },
            "username": {
                "error_messages": {
                    "blank": "아이디를 입력해 주세요.",
                    "required": "아이디는 필수 항목입니다.",
                },
                "validators": [
                    UniqueValidatorWithCustomMessage(
                        queryset=User.objects.all(),
                        message="이미 사용 중인 아이디입니다.",
                    )
                ],
            },
            "nickname": {
                "error_messages": {
                    "blank": "닉네임을 입력해 주세요.",
                    "required": "닉네임은 필수 항목입니다.",
                },
                "validators": [
                    UniqueValidatorWithCustomMessage(
                        queryset=User.objects.all(),
                        message="이미 사용 중인 닉네임입니다.",
                    )
                ],
            },
        }

    def validate_password(self, value):
        """
        비밀번호 검증을 수행합니다. 길이에 따른 한국어 오류 메시지를 반환합니다.
        """
        if len(value) < 8:
            raise serializers.ValidationError("비밀번호는 최소 8자 이상이어야 합니다.")

        try:
            validate_password(value)
        except ValidationError as e:
            # 영문 오류 메시지를 한국어로 변환
            error_messages = []
            for error in e.error_list:
                if "password is too common" in str(error):
                    error_messages.append("너무 흔한 비밀번호입니다.")
                elif "password is entirely numeric" in str(error):
                    error_messages.append("비밀번호는 숫자로만 구성될 수 없습니다.")
                elif "password is too similar to the" in str(error):
                    error_messages.append("비밀번호가 개인정보와 너무 유사합니다.")
                else:
                    error_messages.append(str(error))

            if error_messages:
                raise serializers.ValidationError(error_messages)

        return value

    def create(self, validated_data):
        user = User(
            nickname=validated_data["nickname"],
            email=validated_data["email"],
            username=validated_data["username"],
            user_address=validated_data["user_address"],
        )
        user.set_password(validated_data["password"])
        user.save()
        return user

    def update(self, instance, validated_data):
        # 비밀번호 외 필드 업데이트
        for attr, value in validated_data.items():
            if attr == "password":
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance
