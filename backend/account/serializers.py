from rest_framework import serializers
from .models import User

from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueValidator

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
            "password": {"write_only": True},
            "email": {
                "error_messages": {
                    "invalid": "올바른 이메일 주소를 입력해 주세요.",
                    "blank": "이메일을 입력해 주세요.",
                    "required": "이메일은 필수 항목입니다."
                },
                "validators": [UniqueValidatorWithCustomMessage(queryset=User.objects.all(), message="이미 사용 중인 이메일입니다.")]
            },
            "username": {
                "error_messages": {
                    "blank": "아이디를 입력해 주세요.",
                    "required": "아이디는 필수 항목입니다."
                },
                "validators": [UniqueValidatorWithCustomMessage(queryset=User.objects.all(), message="이미 사용 중인 아이디입니다.")]
            },
            "nickname": {
                "error_messages": {
                    "blank": "닉네임을 입력해 주세요.",
                    "required": "닉네임은 필수 항목입니다."
                },
                "validators": [UniqueValidatorWithCustomMessage(queryset=User.objects.all(), message="이미 사용 중인 닉네임입니다.")]
            },
        }
        

    def create(self, validated_data):
        user = User(nickname=validated_data["nickname"], email=validated_data["email"], username=validated_data["username"], user_address=validated_data["user_address"])
        user.set_password(validated_data["password"])
        user.save()
        return user


